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
from bot.database import db_tarefas_proximas_vencimento


async def check_daily_events(context: ContextTypes.DEFAULT_TYPE):
    chat_ids = get_target_chat_ids()
    if not chat_ids:
        return

    hoje = datetime.date.today()
    eventos = calcular_eventos_mes(hoje.year, hoje.month)

    eventos_hoje = [ev for ev in eventos if ev["data"] == hoje]
    if not eventos_hoje:
        return

    lines = ["🔔 <b>Lembrete do Calendário Financeiro</b>\n"]
    for ev in eventos_hoje:
        lines.append(f"{ev['emoji']} {ev['texto']}")

    msg = "\n".join(lines)

    for cid in chat_ids:
        try:
            await context.bot.send_message(chat_id=cid, text=msg, parse_mode="HTML")
            logger.info(f"Notificação diária enviada para {cid}")
        except Exception as e:
            logger.error(f"Erro ao enviar notificação para {cid}: {e}")


async def check_weekly_summary(context: ContextTypes.DEFAULT_TYPE):
    """Envia resumo semanal toda segunda-feira às 08:00."""
    chat_ids = get_target_chat_ids()
    if not chat_ids:
        return

    hoje = datetime.date.today()
    tarefas = await db_tarefas_proximas_vencimento(dias=14)

    lines = ["📊 <b>Resumo Semanal</b>\n"]
    lines.append(f"📅 {hoje.strftime('%d/%m/%Y')}")
    lines.append("")

    if tarefas:
        lines.append("⚠️ <b>Tarefas com vencimento próximo:</b>")
        for t in tarefas[:10]:
            venc = t.get("data_vencimento", "?")
            title = t.get("title", "?")
            status = t.get("status", "todo")
            status_emoji = {"todo": "📋", "in-progress": "⚡", "done": "✅"}.get(
                status, "📋"
            )
            try:
                venc_date = datetime.date.fromisoformat(venc)
                diff = (venc_date - hoje).days
                if diff < 0:
                    time_label = f"⛔ Vencida há {abs(diff)} dia(s)"
                elif diff == 0:
                    time_label = "🔴 Vence hoje!"
                else:
                    time_label = f"🟡 Vence em {diff} dia(s)"
            except Exception:
                time_label = venc
            lines.append(f"  {status_emoji} {title} — {time_label}")
    else:
        lines.append("✅ Nenhuma tarefa com vencimento próximo.")

    lines.append("")
    lines.append("<i>Use /start para acessar o menu completo.</i>")

    msg = "\n".join(lines)

    for cid in chat_ids:
        try:
            await context.bot.send_message(chat_id=cid, text=msg, parse_mode="HTML")
            logger.info(f"Resumo semanal enviado para {cid}")
        except Exception as e:
            logger.error(f"Erro ao enviar resumo para {cid}: {e}")


def setup_jobs(job_queue):
    if job_queue:
        t = datetime.time(hour=8, minute=0, tzinfo=TZ)
        job_queue.run_daily(check_daily_events, time=t)
        logger.info(
            "JobQueue configurada: Verificação diária de eventos às 08:00 (BRT)."
        )

        # Segunda-feira (monday=0) às 08:00
        job_queue.run_daily(check_weekly_summary, time=t, days=(0,))
        logger.info(
            "JobQueue configurada: Resumo semanal toda segunda-feira às 08:00 (BRT)."
        )
    else:
        logger.warning("JobQueue não está habilitada na aplicação corrente.")
