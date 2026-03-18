import io
import json
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.ai_services import call_local_ai, generate_empenho_text
from bot.config import TELEGRAM_TOKEN, logger

import requests

async def start_auditor_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['step'] = 'up_auditor_arquivo'
    text = (
        '🔍 <b>Auditor de Notas Fiscais · IA</b>\n\n'
        'Envie uma <b>Nota Fiscal</b> (PDF, JPG ou PNG) e a IA irá:\n'
        '• Extrair dados do fornecedor, CNPJ e valores\n'
        '• Verificar inconsistências matemáticas\n'
        '• Detectar descrições genéricas e datas suspeitas\n'
        '• Gerar um <b>Escore de Risco (0–100)</b>\n\n'
        '📎 <i>Envie o arquivo agora:</i>'
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton('❌ Cancelar', callback_data='cmd_cancelar')]])
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode='HTML')
    else:
        await update.message.reply_text(text, reply_markup=kb, parse_mode='HTML')

async def process_auditor_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = update.message.document or update.message.photo[-1]
    file_id = file.file_id
    file_name = getattr(file, 'file_name', 'imagem.jpg')
    
    msg = await update.message.reply_text('⏳ <i>Baixando arquivo e analisando com IA…</i>', parse_mode='HTML')
    await update.message.reply_chat_action('typing')

    try:
        new_file = await context.bot.get_file(file_id)
        # We need to download as bytes using python-telegram-bot
        file_bytes = await new_file.download_as_bytearray()
        
        is_pdf = file_name.lower().endswith('.pdf')
        text = ''
        
        if is_pdf:
            try:
                import PyPDF2
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
                text = ''.join((page.extract_text() or '') + '\n' for page in pdf_reader.pages).strip()
            except Exception as e:
                await msg.edit_text(f'⚠️ Erro ao ler PDF: {e}')
                context.user_data.clear()
                return
            if not text:
                await msg.edit_text('⚠️ Não foi possível extrair texto do PDF (imagem escaneada?). Envie apenas PDFs em formato texto no momento.')
                context.user_data.clear()
                return
        else:
            text = "[O auditor atualmente suporta apenas extração nativa de PDFs (texto) no backend adaptado, envie um PDF para resultados precisos.]"
            await msg.edit_text(text)
            context.user_data.clear()
            return
            
        prompt = f"""Você é um Auditor Fiscal Sênior de Prefeitura Municipal Brasileira.
Analise a Nota Fiscal abaixo e responda APENAS com um objeto JSON válido (sem texto extra):
{{
  "supplierName": "string",
  "cnpj": "string",
  "invoiceDate": "string",
  "totalAmount": number,
  "items": [{{"description": "...", "quantity": number, "unitPrice": number, "totalPrice": number}}],
  "anomalies": ["string"],
  "riskScore": number,
  "riskLevel": "BAIXO|MÉDIO|ALTO|CRÍTICO",
  "auditRecommendation": "string",
  "reasoning": "string"
}}

Regras:
- Verifique se Qtd × Preço Unit = Total Item.
- Descrições genéricas são suspeitas -> aumente riskScore.
- O riskScore deve ser de 0 a 100.
- Use ponto decimal em números.

Texto da Nota Fiscal:
---
{text[:8000]}
---"""

        # Call local AI async
        ai_response = await call_local_ai(prompt)

        # Parse JSON
        try:
            json_match = re.search(r'\{[\s\S]*\}', ai_response)
            result = json.loads(json_match.group(0)) if json_match else json.loads(ai_response)
        except Exception:
            await msg.edit_text(f'🤖 <b>Análise da IA:</b>\n\n{ai_response[:3800]}', parse_mode='HTML', 
                                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 Menu', callback_data='cmd_menu')]]))
            context.user_data.clear()
            return

        # Format report
        score = result.get('riskScore', 0)
        level = result.get('riskLevel', '?')
        score_emoji = '🟢' if score < 30 else ('🟡' if score < 60 else ('🟠' if score < 80 else '🔴'))
        
        anomalies = result.get('anomalies', [])
        anomaly_text = '\n'.join(f'  ⚠️ {a}' for a in anomalies) if anomalies else '  ✅ Nenhuma anomalia detectada'
        
        items = result.get('items', [])
        items_text = ''
        for item in items[:5]:
            items_text += f'  • {item.get("description","?")[:35]} — Qtd: {item.get("quantity",0)} × R$ {item.get("unitPrice",0):.2f}\n'
        if len(items) > 5:
            items_text += f'  <i>…e mais {len(items)-5} item(ns)</i>\n'

        report = (
            f'{score_emoji} <b>Relatório de Auditoria</b>\n\n'
            f'🏢 <b>Fornecedor:</b> {result.get("supplierName","—")}\n'
            f'📋 <b>CNPJ:</b> <code>{result.get("cnpj","—")}</code>\n'
            f'📅 <b>Data NF:</b> {result.get("invoiceDate","—")}\n'
            f'💰 <b>Valor Total:</b> R$ {result.get("totalAmount",0):,.2f}\n\n'
            f'🎯 <b>Escore de Risco: {score}/100</b> — {level}\n\n'
            f'<b>📦 Itens:</b>\n{items_text}\n'
            f'<b>⚠️ Anomalias:</b>\n{anomaly_text}\n\n'
            f'<b>🤖 Recomendação:</b>\n<i>{result.get("auditRecommendation","—")}</i>'
        )

        # Truncate if too long (Telegram max 4096)
        if len(report) > 4000:
            report = report[:4000] + '…'

        # NOVO: Salvar o texto da NF e supplierName para usar no Empenho Inteligente
        context.user_data['last_nf_text'] = text[:3000]
        context.user_data['last_nf_supplier'] = result.get("supplierName", "Empresa")

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton('⚡ Gerar Empenho desta NF', callback_data='cmd_empenho_from_auditor')],
            [InlineKeyboardButton('🔍 Auditar outro arquivo', callback_data='cmd_auditor_nf')],
            [InlineKeyboardButton('🔙 Menu', callback_data='cmd_menu')]
        ])

        await msg.edit_text(report, reply_markup=kb, parse_mode='HTML')
        context.user_data['step'] = None

    except Exception as e:
        logger.error(f'Erro no processo auditor: {e}')
        await msg.edit_text(f'⚠️ Erro inesperado na auditoria: {e}')
        context.user_data.clear()

async def generate_empenho_from_auditor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gera o texto do empenho aproveitando o PDF salvo em cache pelo auditor."""
    nf_text = context.user_data.get('last_nf_text')
    if not nf_text:
        await update.callback_query.answer("⚠️ Dados da nota expiraram, envie o arquivo novamente.", show_alert=True)
        return

    await update.callback_query.answer("Gerando Empenho...", show_alert=False)
    
    # Criamos a mensagem de progresso na thread
    msg = await update.callback_query.message.reply_text('⏳ <i>Processando texto da NF para linguagem formal de empenho...</i>', parse_mode='HTML')
    await update.callback_query.message.reply_chat_action('typing')

    try:
        empenho_text = await generate_empenho_text(nf_text)
        await msg.edit_text(
            f'✅ <b>Descrição de Empenho Gerada:</b>\n\n<code>{empenho_text}</code>\n\n<i>Toque no texto para copiar.</i>',
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 Menu', callback_data='cmd_menu')]])
        )
    except Exception as e:
        logger.error(f'Erro gerando empenho IA do auditor: {e}')
        await msg.edit_text(f'⚠️ Falha na geração do Empenho via IA: {e}')
