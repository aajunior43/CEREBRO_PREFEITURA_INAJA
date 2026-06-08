"""Blueprint: Empenho Assistente - IA para auxiliar na criacao de empenhos"""

import json as _json
from flask import Blueprint, request, jsonify
from routes._shared import get_db, _get_openrouter_config, _build_ai_facade, require_login

bp = Blueprint("empenho_assistente", __name__)


def _clean_value(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _normalize_empenho_payload(payload: dict) -> dict:
    data = dict(payload or {})
    return {
        k: _clean_value(data.get(k))
        for k in (
            "secretaria",
            "fornecedor",
            "tipo_despesa",
            "finalidade",
            "valor",
            "competencia",
            "processo",
            "pregao",
            "contrato",
            "nota_fiscal",
            "texto_base",
            "descricao_atual",
            "observacoes",
            "fonte",
            "arquivo_nome",
            "arquivo_tipo",
        )
    }


def _serialize_json(value):
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return "{}"
        try:
            _json.loads(text)
            return text
        except Exception:
            return _json.dumps({"texto": text}, ensure_ascii=False)
    if value is None:
        return "{}"
    try:
        return _json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        return _json.dumps({"texto": str(value)}, ensure_ascii=False)


def _extract_text_from_result(result):
    if isinstance(result, dict):
        return _serialize_json(result)
    if hasattr(result, "content"):
        return result.content or ""
    return str(result) if result else ""


def _save_empenho_assistente_history(
    conn, action: str, payload: dict, result, meta: dict | None = None
) -> int:
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
        extracted = (
            result.get("campos") if isinstance(result.get("campos"), dict) else {}
        )
        checklist = (
            result.get("checklist") if isinstance(result.get("checklist"), dict) else {}
        )
        descricao_base = _clean_value(result.get("descricao_base"))
        descricao_melhorada = _clean_value(result.get("descricao_melhorada"))
        diff = result.get("diff") if isinstance(result.get("diff"), dict) else {}
    elif action == "suggest_options" and isinstance(result, dict):
        extracted = result.get("inferidos") if isinstance(result.get("inferidos"), dict) else {}
    result_payload = (
        serialize_task_result(result) if not isinstance(result, dict) else result
    )
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
            _clean_value(meta.get("model")),
            1 if meta.get("cached") else 0,
        ),
    )
    conn.commit()
    return cur.lastrowid


@bp.route("/api/empenho-assistente", methods=["POST"])
@require_login
def empenho_assistente():
    from services.openrouter_service import AIServiceError

    data = request.get_json(silent=True) or {}
    action = (data.get("action") or "").strip()
    payload = _normalize_empenho_payload(data.get("payload") or {})
    if action == "suggest_options":
        payload["__missing_fields"] = data.get("payload", {}).get("__missing_fields", [])
    conn = get_db()
    api_key, model = _get_openrouter_config(conn)
    if not api_key:
        return jsonify({"error": "Chave do OpenRouter nao configurada."}), 400
    if action not in {
        "extract_fields",
        "generate_description",
        "checklist",
        "improve_description",
        "review_bundle",
        "suggest_options",
    }:
        return jsonify({"error": "Acao invalida."}), 400
    try:
        facade = _build_ai_facade(api_key, model)
        result = facade.gerar_texto_empenho(payload, acao=action)
        meta = {"model": model, "cached": False, "usage": {}}
        if hasattr(result, "model"):
            meta = {
                "model": result.model,
                "cached": result.cached,
                "usage": result.usage,
            }
        history_id = _save_empenho_assistente_history(
            conn, action, payload, result, meta=meta
        )
        if action == "suggest_options":
            return jsonify(
                {
                    "action": action,
                    "resultado": result if isinstance(result, dict) else {},
                    "history_id": history_id,
                    "meta": meta,
                }
            )
        if isinstance(result, dict):
            return jsonify(
                {
                    "action": action,
                    "resultado": result,
                    "history_id": history_id,
                    "meta": meta,
                }
            )
        return jsonify(
            {
                "action": action,
                "resultado": result.content,
                "history_id": history_id,
                "meta": meta,
            }
        )
    except ValueError as err:
        return jsonify({"error": str(err)}), 400
    except AIServiceError as err:
        return jsonify(err.to_response()), err.status_code
    except Exception as err:
        return jsonify({"error": str(err)}), 500


@bp.route("/api/empenho-assistente/historico", methods=["GET"])
@require_login
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
            items.append(
                {
                    "id": row["id"],
                    "action": row["action"],
                    "payload": _json.loads(row["payload_json"] or "{}"),
                    "resultado": _json.loads(row["resultado_json"] or "{}"),
                    "campos": _json.loads(row["campos_json"] or "{}"),
                    "checklist": _json.loads(row["checklist_json"] or "{}"),
                    "descricao_base": row["descricao_base"] or "",
                    "descricao_melhorada": row["descricao_melhorada"] or "",
                    "diff": _json.loads(row["diff_json"] or "{}"),
                    "model": row["model"] or "",
                    "cached": bool(row["cached"]),
                    "criado_em": row["criado_em"],
                }
            )
        return jsonify({"items": items})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
