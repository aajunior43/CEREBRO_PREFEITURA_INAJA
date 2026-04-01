import io
import base64
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.ai_services import (
    call_local_ai_json,
    call_local_ai_with_vision,
    generate_empenho_text,
)
from bot.config import TELEGRAM_TOKEN, logger
from bot.telegram_safe import safe_answer_callback, safe_edit_message_text

import requests


async def start_auditor_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["step"] = "up_auditor_arquivo"
    text = (
        "🔍 <b>Auditor de Notas Fiscais · IA</b>\n\n"
        "Envie uma <b>Nota Fiscal</b> (PDF, JPG ou PNG) e a IA irá:\n"
        "• Extrair dados do fornecedor, CNPJ e valores\n"
        "• Verificar inconsistências matemáticas\n"
        "• Detectar descrições genéricas e datas suspeitas\n"
        "• Gerar um <b>Escore de Risco (0–100)</b>\n\n"
        "📎 <i>Envie o arquivo agora:</i>"
    )
    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("❌ Cancelar", callback_data="cmd_cancelar")]]
    )
    if update.callback_query:
        await safe_edit_message_text(
            update.callback_query, text, reply_markup=kb, parse_mode="HTML"
        )
    else:
        await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")


def _extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extrai texto de PDF usando pdfplumber (melhor) ou PyPDF2 (fallback)."""
    try:
        import pdfplumber

        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            pages_text = []
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    pages_text.append(t)
            text = "\n".join(pages_text).strip()
            if text:
                return text
    except Exception as e:
        logger.warning(f"pdfplumber falhou: {e}")

    try:
        import PyPDF2

        pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
        text = "".join(
            (page.extract_text() or "") + "\n" for page in pdf_reader.pages
        ).strip()
        return text
    except Exception as e:
        logger.warning(f"PyPDF2 falhou: {e}")

    return ""


def _pdf_has_text(file_bytes: bytes) -> bool:
    """Verifica se o PDF contém texto selecionável."""
    return bool(_extract_text_from_pdf(file_bytes))


def _pdf_to_images(file_bytes: bytes) -> list:
    """Converte PDF em lista de imagens (para OCR via visão)."""
    try:
        from pdf2image import convert_from_path

        images = convert_from_path(io.BytesIO(file_bytes), dpi=200)
        return images
    except Exception as e:
        logger.warning(f"pdf2image falhou: {e}")

    try:
        from PIL import Image
        import fitz

        doc = fitz.open(stream=io.BytesIO(file_bytes), filetype="pdf")
        images = []
        for page in doc:
            pix = page.get_pixmap(dpi=200)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            images.append(img)
        return images
    except Exception as e:
        logger.warning(f"fitz/pymupdf falhou: {e}")

    return []


def _image_to_base64(image) -> str:
    """Converte PIL Image para base64 string."""
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG", quality=85)
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


def _telegram_photo_to_base64(file_bytes: bytes) -> str:
    """Converte bytes de foto do Telegram para base64."""
    return base64.b64encode(file_bytes).decode("utf-8")


AUDIT_PROMPT = """Você é um Auditor Fiscal Sênior de Prefeitura Municipal Brasileira.
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
{text}
---"""


async def _analyze_with_text(update, context, msg, text: str, file_bytes: bytes):
    """Analisa NF usando texto extraído."""
    prompt = AUDIT_PROMPT.format(text=text[:8000])
    result = await call_local_ai_json(prompt)
    await _format_audit_result(update, context, msg, result, text)


async def _analyze_with_vision(
    update, context, msg, image_base64: str, file_bytes: bytes, is_pdf: bool = False
):
    """Analisa NF usando visão da IA (para imagens/PDFs escaneados)."""
    prompt = (
        "Você é um Auditor Fiscal Sênior de Prefeitura Municipal Brasileira. "
        "Analise esta Nota Fiscal e responda APENAS com um objeto JSON válido:\n\n"
        '{"supplierName": "string", "cnpj": "string", "invoiceDate": "string", '
        '"totalAmount": number, "items": [{"description": "...", "quantity": number, '
        '"unitPrice": number, "totalPrice": number}], "anomalies": ["string"], '
        '"riskScore": number, "riskLevel": "BAIXO|MÉDIO|ALTO|CRÍTICO", '
        '"auditRecommendation": "string", "reasoning": "string"}\n\n'
        "Regras: Verifique se Qtd × Preço Unit = Total Item. "
        "Descrições genéricas são suspeitas. riskScore de 0 a 100."
    )

    result = await call_local_ai_with_vision(prompt, image_base64)

    text_for_empenho = (
        f"[Extraído por visão IA - {('PDF escaneado' if is_pdf else 'Imagem')}]"
    )
    await _format_audit_result(update, context, msg, result, text_for_empenho)


async def _format_audit_result(update, context, msg, result: dict, raw_text: str):
    """Formata e envia o resultado da auditoria."""
    score = result.get("riskScore", 0)
    level = result.get("riskLevel", "?")
    score_emoji = (
        "🟢" if score < 30 else ("🟡" if score < 60 else ("🟠" if score < 80 else "🔴"))
    )

    anomalies = result.get("anomalies", [])
    anomaly_text = (
        "\n".join(f"  ⚠️ {a}" for a in anomalies)
        if anomalies
        else "  ✅ Nenhuma anomalia detectada"
    )

    items = result.get("items", [])
    items_text = ""
    for item in items[:5]:
        items_text += f"  • {item.get('description', '?')[:35]} — Qtd: {item.get('quantity', 0)} × R$ {item.get('unitPrice', 0):.2f}\n"
    if len(items) > 5:
        items_text += f"  <i>…e mais {len(items) - 5} item(ns)</i>\n"

    report = (
        f"{score_emoji} <b>Relatório de Auditoria</b>\n\n"
        f"🏢 <b>Fornecedor:</b> {result.get('supplierName', '—')}\n"
        f"📋 <b>CNPJ:</b> <code>{result.get('cnpj', '—')}</code>\n"
        f"📅 <b>Data NF:</b> {result.get('invoiceDate', '—')}\n"
        f"💰 <b>Valor Total:</b> R$ {result.get('totalAmount', 0):,.2f}\n\n"
        f"🎯 <b>Escore de Risco: {score}/100</b> — {level}\n\n"
        f"<b>📦 Itens:</b>\n{items_text}\n"
        f"<b>⚠️ Anomalias:</b>\n{anomaly_text}\n\n"
        f"<b>🤖 Recomendação:</b>\n<i>{result.get('auditRecommendation', '—')}</i>"
    )

    if len(report) > 4000:
        report = report[:4000] + "…"

    context.user_data["last_nf_text"] = raw_text[:3000]
    context.user_data["last_nf_supplier"] = result.get("supplierName", "Empresa")

    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "⚡ Gerar Empenho desta NF",
                    callback_data="cmd_empenho_from_auditor",
                )
            ],
            [
                InlineKeyboardButton(
                    "🔍 Auditar outro arquivo", callback_data="cmd_auditor_nf"
                )
            ],
            [InlineKeyboardButton("🔙 Menu", callback_data="cmd_menu")],
        ]
    )

    await msg.edit_text(report, reply_markup=kb, parse_mode="HTML")
    context.user_data["step"] = None


async def process_auditor_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = update.message.document or update.message.photo[-1]
    file_id = file.file_id
    file_name = getattr(file, "file_name", "imagem.jpg")

    msg = await update.message.reply_text(
        "⏳ <i>Baixando arquivo e analisando com IA…</i>", parse_mode="HTML"
    )
    await update.message.reply_chat_action("typing")

    try:
        new_file = await context.bot.get_file(file_id)
        file_bytes = await new_file.download_as_bytearray()

        is_pdf = file_name.lower().endswith(".pdf")

        if is_pdf:
            text = _extract_text_from_pdf(file_bytes)

            if text:
                await msg.edit_text(
                    "⏳ <i>Texto extraído. Analisando com IA…</i>", parse_mode="HTML"
                )
                await _analyze_with_text(update, context, msg, text, file_bytes)
                return

            await msg.edit_text(
                "⏳ <i>PDF escaneado detectado. Convertendo para análise visual…</i>",
                parse_mode="HTML",
            )

            images = _pdf_to_images(file_bytes)
            if images:
                img_base64 = _image_to_base64(images[0])
                await _analyze_with_vision(
                    update, context, msg, img_base64, file_bytes, is_pdf=True
                )
                return

            await msg.edit_text(
                "⚠️ Não foi possível extrair conteúdo deste PDF. Tente enviar como imagem."
            )
            context.user_data.clear()
            return
        else:
            await msg.edit_text(
                "⏳ <i>Analisando imagem com IA…</i>", parse_mode="HTML"
            )
            img_base64 = _telegram_photo_to_base64(bytes(file_bytes))
            await _analyze_with_vision(
                update, context, msg, img_base64, bytes(file_bytes), is_pdf=False
            )
            return

    except Exception as e:
        logger.error(f"Erro no processo auditor: {e}")
        await msg.edit_text(f"⚠️ Erro inesperado na auditoria: {e}")
        context.user_data.clear()


async def generate_empenho_from_auditor(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """Gera o texto do empenho aproveitando o PDF salvo em cache pelo auditor."""
    nf_text = context.user_data.get("last_nf_text")
    if not nf_text:
        await safe_answer_callback(
            update.callback_query,
            "⚠️ Dados da nota expiraram, envie o arquivo novamente.",
            show_alert=True,
        )
        return

    await safe_answer_callback(
        update.callback_query, "Gerando Empenho...", show_alert=False
    )

    msg = await update.callback_query.message.reply_text(
        "⏳ <i>Processando texto da NF para linguagem formal de empenho...</i>",
        parse_mode="HTML",
    )
    await update.callback_query.message.reply_chat_action("typing")

    try:
        empenho_text = await generate_empenho_text(nf_text)
        await msg.edit_text(
            f"✅ <b>Descrição de Empenho Gerada:</b>\n\n<code>{empenho_text}</code>\n\n<i>Toque no texto para copiar.</i>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 Menu", callback_data="cmd_menu")]]
            ),
        )
    except Exception as e:
        logger.error(f"Erro gerando empenho IA do auditor: {e}")
        await msg.edit_text(f"⚠️ Falha na geração do Empenho via IA: {e}")
