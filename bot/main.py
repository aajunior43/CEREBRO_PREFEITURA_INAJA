from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from bot.config import TELEGRAM_TOKEN, logger
from bot.handlers import start, cancel, handle_callback, handle_text, handle_document, handle_audio

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
    
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, handle_document))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_audio))

    from bot.features.notificacoes import setup_jobs
    setup_jobs(app.job_queue)

    logger.info("Polling iniciado.")
    app.run_polling()

if __name__ == '__main__':
    main()
