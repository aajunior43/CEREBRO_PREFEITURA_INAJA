import datetime
try:
    import zoneinfo
    TZ = zoneinfo.ZoneInfo("America/Sao_Paulo")
except ImportError:
    import pytz
    TZ = pytz.timezone("America/Sao_Paulo")

from telegram.ext import ContextTypes
from bot.config import get_target_chat_ids, logger
from bot.features.calendario import calcular_eventos_mes

async def check_daily_events(context: ContextTypes.DEFAULT_TYPE):
    chat_ids = get_target_chat_ids()
    if not chat_ids: return
    
    hoje = datetime.date.today()
    eventos = calcular_eventos_mes(hoje.year, hoje.month)
    
    eventos_hoje = [ev for ev in eventos if ev['data'] == hoje]
    if not eventos_hoje: return
    
    lines = ["🔔 <b>Lembrete do Calendário Financeiro</b>\n"]
    for ev in eventos_hoje:
        lines.append(f"{ev['emoji']} {ev['texto']}")
        
    msg = "\n".join(lines)
    
    for cid in chat_ids:
        try:
            await context.bot.send_message(chat_id=cid, text=msg, parse_mode='HTML')
            logger.info(f"Notificação diária enviada para {cid}")
        except Exception as e:
            logger.error(f"Erro ao enviar notificação para {cid}: {e}")

def setup_jobs(job_queue):
    if job_queue:
        t = datetime.time(hour=8, minute=0, tzinfo=TZ)
        job_queue.run_daily(check_daily_events, time=t)
        logger.info("JobQueue configurada: Verificação diária de eventos às 08:00 (BRT).")
    else:
        logger.warning("JobQueue não está habilitada na aplicação corrente.")
