import os
import requests
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from bot.config import get_config, logger
from bot.database import db_criar_tarefa
from bot.ai_services import call_local_ai

async def process_voice_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    voice = update.message.voice or update.message.audio
    if not voice: return

    msg = await update.message.reply_text('🎙️ <i>Ouvindo seu áudio e transcrevendo...</i>', parse_mode='HTML')
    await update.message.reply_chat_action('typing')

    try:
        new_file = await context.bot.get_file(voice.file_id)
        # We need the direct OS file path or bytes to send as multipart
        file_bytes = await new_file.download_as_bytearray()
        
        # We'll use the OpenRouter API key but ideally transcription goes to OpenAI/Groq. 
        # OpenAI audio API format:
        api_key = get_config('api_openrouter_key') # O user pode ter colocado openai key aqui ou na cfg certa
        if not api_key:
            await msg.edit_text("⚠️ Chave de API não configurada para transcrição.")
            return

        # Chamada genérica padrão Whisper (OpenAI-compatible)
        # Como OpenRouter não tem endpoint nativo de audio/transcriptions na docs padrão, 
        # assumimos que o servidor vai direcionar (ou usar apiKey da Groq/Openai)
        # Para compatibilidade, tentaremos a api oficial da OpenAI usando a mesma chave, ou Groq caso configurável
        
        url = get_config('api_whisper_url', 'https://api.openai.com/v1/audio/transcriptions')
        
        headers = {
            'Authorization': f'Bearer {api_key}'
        }
        
        files = {
            'file': ('audio.ogg', file_bytes, 'audio/ogg')
        }
        data = {
            'model': 'whisper-1'
        }
        
        # Envia de forma sincrona porem usando run_async idealmente. Mas requests direto:
        resp = requests.post(url, headers=headers, files=files, data=data, timeout=60)
        
        if not resp.ok:
            await msg.edit_text(f"⚠️ Erro na transcrição (verifique se a API do Whisper suporta essa chave): {resp.text}")
            return
            
        transcription = resp.json().get('text', '')
        if not transcription:
            await msg.edit_text("⚠️ Nenhuma voz reconhecida no áudio.")
            return
            
        await msg.edit_text(f'🗣️ <b>Áudio transcrito:</b>\n"<i>{transcription}</i>"\n\n⏳ Processando tarefa...', parse_mode='HTML')
        
        # Agora manda para a IA local organizar em Título e Descrição
        prompt = f"""Você é um assistente da prefeitura. O usuário enviou um áudio ordenando a criação de uma tarefa no sistema Kanban.
Extraia o Título (curto, máx 50 caracteres) e a Descrição (detalhes).
Extraia a prioridade se citada (high, medium, low). Padrão é medium.

Responda APENAS um JSON válido:
{{
  "title": "novo titulo",
  "description": "descrição completa",
  "priority": "medium"
}}

Áudio transcrito: "{transcription}"
"""
        ai_resp = await call_local_ai(prompt)
        
        import json, re
        try:
            json_match = re.search(r'\{[\s\S]*\}', ai_resp)
            task_data = json.loads(json_match.group(0)) if json_match else json.loads(ai_resp)
            
            title = task_data.get('title', 'Tarefa gerada por voz')
            desc = task_data.get('description', transcription)
            prio = task_data.get('priority', 'medium')
            
            # Salvar no DB
            task = await db_criar_tarefa(title, desc, 'todo', prio)
            
            from bot.ui import format_task_created
            
            await msg.edit_text(
                format_task_created(task),
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 Menu', callback_data='cmd_menu')]])
            )
            
        except Exception as e:
            await msg.edit_text(f"⚠️ Erro ao entender o texto para tarefa: {e}\n\nTransição crua:\n{transcription}")

    except Exception as e:
        logger.error(f"Erro no módulo de voz: {e}")
        await msg.edit_text(f"⚠️ Erro inesperado ao processar áudio: {e}")

