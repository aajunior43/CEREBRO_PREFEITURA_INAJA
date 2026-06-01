"""Blueprint: IA Chat Proxy"""

from flask import Blueprint, request, jsonify
from routes._shared import get_db, _get_openrouter_config, _build_ai_service, require_login

bp = Blueprint("ia", __name__)


@bp.route("/api/ia/chat", methods=["POST"])
@require_login
def proxy_ia_chat():
    from services.openrouter_service import AIServiceError

    try:
        data = request.get_json(force=True) or {}
        conn = get_db()
        api_key, model = _get_openrouter_config(
            conn,
            api_key_override=(data.get("api_key") or "").strip(),
            model_override=(data.get("model") or "").strip(),
        )
        if not api_key:
            return jsonify({"error": "Chave API OpenRouter não configurada."}), 400
        response = _build_ai_service(api_key, model).chat_by_task(
            task_type="chat",
            messages=data.get("messages", []),
            temperature=data.get("temperature", 0.2),
            max_tokens=data.get("max_tokens", 2000),
            use_cache=bool(data.get("use_cache", False)),
            response_format=data.get("response_format"),
            stream=bool(data.get("stream", False)),
            metadata={"feature": "proxy_ia_chat"},
        )
        return jsonify(response.payload)
    except AIServiceError as err:
        return jsonify(err.to_response()), err.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500
