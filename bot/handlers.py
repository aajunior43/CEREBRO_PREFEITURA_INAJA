from telegram import Update
from telegram.ext import ContextTypes
from bot.ui import keyboard_main, menu_text
from bot.database import db_listar_tarefas
from bot.config import TELEGRAM_CHAT_ID, logger
from bot.features.auth import is_authorized_async, handle_login_request, handle_auth_callback

import traceback

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_authorized_async(update.effective_user.id):
        await handle_login_request(update, context)
        return

    todo = len(await db_listar_tarefas('todo'))
    prog = len(await db_listar_tarefas('in-progress'))
    done = len(await db_listar_tarefas('done'))

    await update.message.reply_text(
        text=menu_text(todo, prog, done),
        reply_markup=keyboard_main(),
        parse_mode='HTML'
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Operação cancelada.")
    await start(update, context)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    if not await is_authorized_async(user_id):
        if await handle_auth_callback(update, context): return
        return
        
    if await handle_auth_callback(update, context): return
    
    data = query.data
    if data == 'ignore': return
    
    if data == 'cmd_cancelar':
        context.user_data.clear()
        await query.edit_message_text("❌ Operação cancelada.")
        return
        
    if data == 'cmd_menu':
        context.user_data.clear()
        todo = len(await db_listar_tarefas('todo'))
        prog = len(await db_listar_tarefas('in-progress'))
        done = len(await db_listar_tarefas('done'))
        await query.edit_message_text(menu_text(todo, prog, done), reply_markup=keyboard_main(), parse_mode='HTML')
        return
    
    # Log temporario pra debugging
    logger.info(f"Callback received: {data}")
    
    from bot.features.auditor import start_auditor_flow, generate_empenho_from_auditor
    from bot.features.kanban import cmd_ver_tarefas, handle_pagination_callback
    
    if data == 'cmd_auditor_nf':
        await start_auditor_flow(update, context)
        return
    if data == 'cmd_empenho_from_auditor':
        await generate_empenho_from_auditor(update, context)
        return
    if data == 'cmd_ver_tarefas':
        await cmd_ver_tarefas(update, context)
        return
    if data.startswith('page_tarefas_'):
        await handle_pagination_callback(update, context)
        return

    try:
        # TODO: Implementar todos os sub-arquivos reais
        await query.message.reply_text(f"🚧 O botão <b>{data}</b> foi recebido, mas seus submódulos ainda estão sendo migrados para a nova estrutura assíncrona.", parse_mode='HTML')
    except Exception as e:
        logger.error(f"Erro no callback {data}: {e}")
        await query.message.reply_text(f"⚠️ Erro ao processar comando: {str(e)}")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_authorized_async(update.effective_user.id): return
    
    step = context.user_data.get('step')
    text = update.message.text
    logger.info(f"Text received: {text[:50]} | Step: {step}")
    
    if not step:
        await update.message.reply_text("Escolha uma opção no menu ou digite /start para reiniciar.")
        return
    
    # TODO: Delegação de estado de conversas (Kanban form, RPA form, Prazos)
    await update.message.reply_text(f"🚧 Passo atual registado ({step}), mas a funcionalidade está em migração.")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_authorized_async(update.effective_user.id): return
    
    step = context.user_data.get('step')
    if not step:
        await update.message.reply_text("Por favor, selecione uma ferramenta no menu (/start) primeiro antes de enviar arquivos.")
        return
        
    await update.message.reply_chat_action(action='typing')
    if step == 'up_auditor_arquivo':
        from bot.features.auditor import process_auditor_file
        await process_auditor_file(update, context)
        return
        
    await update.message.reply_text(f"🚧 Recebido documento no passo ({step}). Esta ferramenta está sendo portada.")

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_authorized_async(update.effective_user.id): return
    from bot.features.voice import process_voice_note
    await process_voice_note(update, context)

