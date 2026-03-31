from __future__ import annotations

from telegram.error import BadRequest, TelegramError


async def safe_answer_callback(query, text: str | None = None, show_alert: bool = False) -> bool:
    if not query:
        return False
    try:
        await query.answer(text, show_alert=show_alert)
        return True
    except BadRequest:
        return False
    except TelegramError:
        return False
    except Exception:
        return False


async def safe_edit_message_text(query_or_message, text: str, **kwargs) -> bool:
    if not query_or_message:
        return False
    try:
        await query_or_message.edit_message_text(text, **kwargs)
        return True
    except BadRequest:
        return False
    except TelegramError:
        return False
    except Exception:
        return False
