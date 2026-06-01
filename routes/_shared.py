"""Funções compartilhadas entre blueprints."""

import json
import os
import re
from config import settings


def get_db():
    from flask import g
    return g._get_db()


def require_login(fn):
    """Decorator: exige sessao autenticada. Protege endpoints que gastam
    creditos de IA ou recursos do servidor contra acesso anonimo."""
    from functools import wraps

    @wraps(fn)
    def wrapper(*args, **kwargs):
        from flask import session, jsonify
        if "usuario_id" not in session:
            return jsonify({"error": "Nao autorizado"}), 403
        return fn(*args, **kwargs)

    return wrapper


def registrar_auditoria(conn, tabela: str, registro_id, operacao: str,
                        dados_anteriores: dict = None, dados_novos: dict = None):
    """Insere uma entrada no audit_trail para rastrear criações, edições e exclusões."""
    try:
        from flask import request as _req
        ip = _req.remote_addr or ""
    except Exception:
        ip = ""
    conn.execute(
        "INSERT INTO audit_trail (tabela, registro_id, operacao, dados_anteriores, dados_novos, ip)"
        " VALUES (?,?,?,?,?,?)",
        (
            tabela,
            str(registro_id) if registro_id is not None else "",
            operacao,
            json.dumps(dados_anteriores or {}, ensure_ascii=False, default=str),
            json.dumps(dados_novos or {}, ensure_ascii=False, default=str),
            ip,
        ),
    )


def row_to_dict(row):
    return dict(row)


def _get_openrouter_config(conn, api_key_override: str = "", model_override: str = ""):
    rows = conn.execute(
        "SELECT chave,valor FROM configuracoes WHERE chave IN (?,?,?)",
        ("api_openrouter_key", "api_openrouter_modelo", "api_opencode_go_key"),
    ).fetchall()
    cfg = {row["chave"]: (row["valor"] or "").strip() for row in rows}
    raw_model = (
        (model_override or "").strip()
        or cfg.get("api_openrouter_modelo", "")
        or (os.environ.get("OPENROUTER_MODEL") or "").strip()
        or settings.openrouter_default_model
    )
    model = (
        raw_model.strip()
        if not raw_model.endswith(":free") and raw_model != "openrouter/free"
        else raw_model.strip()
    )
    if model.startswith("opencode-go/"):
        api_key = (
            (api_key_override or "").strip()
            or cfg.get("api_opencode_go_key", "")
            or (os.environ.get("OPENCODE_GO_API_KEY") or "").strip()
        )
    else:
        api_key = (
            (api_key_override or "").strip()
            or cfg.get("api_openrouter_key", "")
            or (os.environ.get("OPENROUTER_API_KEY") or "").strip()
        )
    return api_key, model


def _build_ai_service(api_key: str, model: str):
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


def _build_ai_facade(api_key: str, model: str):
    from services.ai_tasks import AITaskFacade

    return AITaskFacade(_build_ai_service(api_key, model))


def _extract_json_block(text: str):
    text = (text or "").strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return json.loads(match.group(1))
    s, e = text.find("{"), text.rfind("}")
    if s != -1 and e != -1 and e > s:
        try:
            return json.loads(text[s : e + 1])
        except Exception:
            pass
    s, e = text.find("["), text.rfind("]")
    if s != -1 and e != -1 and e > s:
        return json.loads(text[s : e + 1])
    raise ValueError("Formato inválido")
