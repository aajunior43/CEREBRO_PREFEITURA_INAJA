"""
app/utils/ai_service_factory.py — Factory centralizado para servicos de IA
Elimina duplicacao de _get_openrouter_config e _build_ai_service nas rotas.
"""

from config import settings


def get_openrouter_config(conn, api_key_override="", model_override=""):
    """Obtem configuracao do OpenRouter do banco ou settings.

    Prioridade: override > banco de dados > env vars > defaults.
    """
    rows = conn.execute(
        "SELECT chave,valor FROM configuracoes WHERE chave IN (?,?)",
        ("api_openrouter_key", "api_openrouter_modelo"),
    ).fetchall()
    cfg = {row["chave"]: (row["valor"] or "").strip() for row in rows}

    api_key = (
        (api_key_override or "").strip()
        or cfg.get("api_openrouter_key", "")
        or (settings.OPENROUTER_API_KEY or "").strip()
    )

    raw_model = (
        (model_override or "").strip()
        or cfg.get("api_openrouter_modelo", "")
        or (settings.OPENROUTER_MODEL or "").strip()
        or settings.openrouter_default_model
    )

    return api_key, raw_model.strip()


def build_ai_service(api_key, model):
    """Construi servico OpenRouter com configuracao padrao."""
    from services.openrouter_service import build_openrouter_service

    return build_openrouter_service(
        api_key=api_key,
        default_model=model or settings.openrouter_default_model,
        referer=settings.openrouter_referer,
        title=settings.openrouter_title,
        logger=None,
        timeout_seconds=settings.openrouter_timeout_seconds,
        max_retries=settings.openrouter_max_retries,
        backoff_base=settings.openrouter_backoff_base,
        cache_ttl_seconds=settings.openrouter_cache_ttl_seconds,
    )


def build_ai_facade(api_key, model):
    """Construi facade de tarefas de IA."""
    from services.ai_tasks import AITaskFacade

    return AITaskFacade(build_ai_service(api_key, model))
