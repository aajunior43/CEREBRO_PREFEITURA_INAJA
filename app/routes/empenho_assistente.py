"""
app/routes/empenho_assistente.py — AI empenho assistant (migrated from routes/all_routes.py)
"""
import json
from flask import Blueprint, request, jsonify
from app.utils.db import get_db
from app.utils.helpers import row_to_dict, clean_value
from config import settings

bp = Blueprint("empenho_assistente", __name__)


def _get_openrouter_config(conn, api_key_override="", model_override=""):
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


def _build_ai_service(api_key, model):
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


def _build_ai_facade(api_key, model):
    from services.ai_tasks import AITaskFacade
    return AITaskFacade(_build_ai_service(api_key, model))


def _normalize_empenho_payload(payload):
    data = dict(payload or {})
    return {
        k: clean_value(data.get(k))
        for k in (
            "secretaria", "fornecedor", "tipo_despesa", "finalidade",
            "valor", "competencia", "processo", "pregao", "contrato",
            "nota_fiscal", "texto_base", "descricao_atual", "observacoes",
            "fonte", "arquivo_nome", "arquivo_tipo",
        )
    }


def _serialize_json(value):
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return "{}"
        try:
            json.loads(text)
            return text
        except Exception:
            return json.dumps({"texto": text}, ensure_ascii=False)
    if value is None:
        return "{}"
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        return json.dumps({"texto": str(value)}, ensure_ascii=False)


def _extract_text_from_result(result):
    if isinstance(result, dict):
        return _serialize_json(result)
    if hasattr(result, "content"):
        return result.content or ""
    return str(result) if result else ""


def _save_empenho_assistente_history(conn, action, payload, result, meta=None):
    from services.ai_tasks import serialize_task_result
    meta = meta or {}
    extracted, checklist, descricao_base, descricao_melhorada, diff = {}, {}, "", "", {}
    if action == "extract_fields" and isinstance(result, dict):
        extracted = result
    elif action == "checklist" and isinstance(result, dict):
        checklist = result
    elif action == "generate_description":
        descricao_base = _extract_text_from_result(result)
    elif action == "improve_description":
        descricao_melhorada = _extract_text_from_result(result)
    elif action == "review_bundle" and isinstance(result, dict):
        extracted = result.get("campos") if isinstance(result.get("campos"), dict) else {}
        checklist = result.get("checklist") if isinstance(result.get("checklist"), dict) else {}
        descricao_base = clean_value(result.get("descricao_base"))
        descricao_melhorada = clean_value(result.get("descricao_melhorada"))
        diff = result.get("diff") if isinstance(result.get("diff"), dict) else {}
    result_payload = serialize_task_result(result) if not isinstance(result, dict) else result
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO empenho_assistente_historico (action,payload_json,resultado_json,campos_json,checklist_json,descricao_base,descricao_melhorada,diff_json,model,cached) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (
            action,
            _serialize_json(payload),
            _serialize_json(result_payload),
            _serialize_json(extracted),
            _serialize_json(checklist),
            descricao_base,
            descricao_melhorada,
            _serialize_json(diff),
            clean_value(meta.get("model")),
            1 if meta.get("cached") else 0,
        ),
    )
    conn.commit()
    return cur.lastrowid


@bp.route("/empenho-assistente", methods=["POST"])
def empenho_assistente():
    from services.openrouter_service import AIServiceError

    data = request.get_json(silent=True) or {}
    action = (data.get("action") or "").strip()
    payload = _normalize_empenho_payload(data.get("payload") or {})
    conn = get_db()
    api_key, model = _get_openrouter_config(conn)
    if not api_key:
        return jsonify({"error": "Chave do OpenRouter não configurada."}), 400
    if action not in {
        "extract_fields", "generate_description", "checklist",
        "improve_description", "review_bundle",
    }:
        return jsonify({"error": "Ação inválida."}), 400
    try:
        facade = _build_ai_facade(api_key, model)
        result = facade.gerar_texto_empenho(payload, acao=action)
        meta = {"model": model, "cached": False, "usage": {}}
        if hasattr(result, "model"):
            meta = {"model": result.model, "cached": result.cached, "usage": result.usage}
        history_id = _save_empenho_assistente_history(conn, action, payload, result, meta=meta)
        if isinstance(result, dict):
            return jsonify({"action": action, "resultado": result, "history_id": history_id, "meta": meta})
        return jsonify({"action": action, "resultado": result.content, "history_id": history_id, "meta": meta})
    except ValueError as err:
        return jsonify({"error": str(err)}), 400
    except AIServiceError as err:
        return jsonify(err.to_response()), err.status_code
    except Exception as err:
        return jsonify({"error": str(err)}), 500


@bp.route("/empenho-assistente/historico", methods=["GET"])
def empenho_assistente_historico():
    try:
        conn = get_db()
        try:
            limit = min(max(int(request.args.get("limit", 12) or 12), 1), 50)
        except (TypeError, ValueError):
            limit = 12
        rows = conn.execute(
            "SELECT id,action,payload_json,resultado_json,campos_json,checklist_json,descricao_base,descricao_melhorada,diff_json,model,cached,criado_em FROM empenho_assistente_historico ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        items = []
        for row in rows:
            items.append({
                "id": row["id"],
                "action": row["action"],
                "payload": json.loads(row["payload_json"] or "{}"),
                "resultado": json.loads(row["resultado_json"] or "{}"),
                "campos": json.loads(row["campos_json"] or "{}"),
                "checklist": json.loads(row["checklist_json"] or "{}"),
                "descricao_base": row["descricao_base"] or "",
                "descricao_melhorada": row["descricao_melhorada"] or "",
                "diff": json.loads(row["diff_json"] or "{}"),
                "model": row["model"] or "",
                "cached": bool(row["cached"]),
                "criado_em": row["criado_em"],
            })
        return jsonify({"items": items})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
