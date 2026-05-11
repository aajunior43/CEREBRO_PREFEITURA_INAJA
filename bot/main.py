from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from telegram.error import BadRequest, Conflict, TelegramError
from bot.config import TELEGRAM_TOKEN, get_target_chat_ids, logger
from bot.handlers import start, cancel, link, handle_callback, handle_text, handle_document, handle_audio

async def send_tunnel_link(app):
    """Envia o link do tunnel Cloudflare para os administradores após o bot iniciar."""
    import asyncio
    from bot.cloudflare_tunnel import get_tunnel_url
    
    url = None
    for _ in range(15):
        url = get_tunnel_url()
        if url:
            break
        await asyncio.sleep(2)

    if not url:
        logger.info("Nenhum link de tunnel encontrado para enviar")
        return
    
    chat_ids = get_target_chat_ids()
    if not chat_ids:
        logger.info("Nenhum chat de destino do Telegram disponível para enviar link")
        return

    
    message = (
        f"🌐 <b>Link de Acesso Externo Disponível!</b>\n\n"
        f"O sistema foi iniciado e está acessível publicamente:\n\n"
        f"🔗 <a href=\"{url}\">{url}</a>\n\n"
        f"📋 <b>Funcionalidades disponíveis:</b>\n"
        f"• Kanban de Tarefas\n"
        f"• Auditor de Notas Fiscais\n"
        f"• Calendário Financeiro\n"
        f"• Gerador de Empenhos\n"
        f"• E muito mais...\n\n"
        f"⚠️ <i>Este link é temporário e será válido enquanto o servidor estiver rodando.</i>"
    )
    
    for chat_id in chat_ids:
        try:
            await app.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode='HTML',
                disable_web_page_preview=True
            )
            logger.info(f"Link do tunnel enviado para {chat_id}")
        except Exception as e:
            logger.error(f"Erro ao enviar link para {chat_id}: {e}")


async def handle_error(update, context):
    error = context.error
    if isinstance(error, BadRequest):
        message = str(error)
        if "Query is too old" in message or "query id is invalid" in message:
            logger.info(f"Ignorando callback expirado: {message}")
            return
    if isinstance(error, Conflict):
        logger.warning(f"Conflito do Telegram ignorado: {error}")
        return
    if isinstance(error, TelegramError):
        logger.error(f"Erro do Telegram: {error}")
        return
    tb = getattr(error, "__traceback__", None)
    if tb is not None:
        logger.error("Erro inesperado no bot: %s", error, exc_info=(type(error), error, tb))
    else:
        logger.error("Erro inesperado no bot: %s", error)

def get_public_base_url() -> str:
    """Retorna a URL pública preferida para compartilhar links do sistema."""
    import os
    from bot.cloudflare_tunnel import get_tunnel_url

    return (
        get_tunnel_url()
        or os.environ.get('SERVER_URL', '').strip().rstrip('/')
        or 'http://localhost:5000'
    )

def main():
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN não configurado!")
        return
        
    import asyncio
    from bot.database import db_init_users_table
    asyncio.run(db_init_users_table())

    logger.info("Inicializando bot com python-telegram-bot (Assíncrono)...")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('cancelar', cancel))
    app.add_handler(CommandHandler('link', link))
    
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, handle_document))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_audio))
    app.add_error_handler(handle_error)

    from bot.features.notificacoes import setup_jobs
    setup_jobs(app.job_queue)

    # Agenda envio do link do tunnel após o bot iniciar
    app.job_queue.run_once(send_tunnel_link, when=5)

    logger.info("Polling iniciado.")
    app.run_polling()

if __name__ == '__main__':
    main()
