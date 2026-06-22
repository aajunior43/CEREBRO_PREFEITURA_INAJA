"""Blueprint: Extratos — Modelos OpenRouter"""

from flask import Blueprint, request, jsonify
from config import settings
from routes._shared import get_db, _get_openrouter_config, require_login

bp = Blueprint("extratos", __name__)


@bp.route("/api/extratos/modelos-openrouter", methods=["GET", "POST"])
@require_login
def extratos_modelos_openrouter():
    from services.openrouter_service import AIServiceError, listar_modelos

    try:
        data = request.get_json(silent=True) or {}
        conn = get_db()
        api_key, selected_model = _get_openrouter_config(conn)
        if not api_key:
            return jsonify(
                {
                    "error": "Chave do OpenRouter não configurada.",
                    "modelos": [],
                    "models": [],
                    "selected_model": selected_model,
                }
            ), 400
        models = listar_modelos(
            api_key,
            timeout_seconds=settings.openrouter_timeout_seconds,
            referer=settings.openrouter_referer,
            title=settings.openrouter_title,
        )
        normalized = []
        for model in models:
            if not isinstance(model, dict):
                continue
            pricing = model.get("pricing") or {}
            if (
                str(pricing.get("prompt") or "").strip() != "0"
                or str(pricing.get("completion") or "").strip() != "0"
            ):
                continue
            normalized.append(
                {
                    "id": (model.get("id") or "").strip(),
                    "name": (model.get("name") or model.get("id") or "").strip(),
                    "context_length": model.get("context_length"),
                    "pricing": pricing,
                }
            )
        return jsonify(
            {
                "modelos": normalized,
                "models": normalized,
                "selected_model": selected_model,
            }
        )
    except AIServiceError as err:
        return jsonify(
            {"error": err.user_message, "modelos": [], "models": []}
        ), err.status_code
    except Exception as e:
        return jsonify({"error": str(e), "modelos": [], "models": []}), 500
