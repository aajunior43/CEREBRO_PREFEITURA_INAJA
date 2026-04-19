"""
app/routes/extratos.py — Rotas de processamento de extratos
"""

import os
from flask import Blueprint, request, jsonify, current_app
from config import settings
from app.utils.db import get_db
from services.extratos_service import listar_subpastas, processar_extratos, validar_origem_destino

bp = Blueprint('extratos', __name__)


@bp.route('/extratos/modelos-openrouter', methods=['GET', 'POST'])
def listar_modelos_openrouter():
    """Lista modelos OpenRouter gratuitos disponíveis (migrado de routes/all_routes.py)."""
    from services.openrouter_service import AIServiceError, listar_modelos

    try:
        data = request.get_json(silent=True) or {}
        conn = get_db()

        # Build config from DB
        rows = conn.execute(
            "SELECT chave,valor FROM configuracoes WHERE chave IN (?,?)",
            ("api_openrouter_key", "api_openrouter_modelo"),
        ).fetchall()
        cfg = {row["chave"]: (row["valor"] or "").strip() for row in rows}
        api_key = (
            (data.get("api_key") or request.args.get("api_key") or "").strip()
            or cfg.get("api_openrouter_key", "")
            or (settings.OPENROUTER_API_KEY or "").strip()
        )
        raw_model = (
            (data.get("model") or request.args.get("model") or "").strip()
            or cfg.get("api_openrouter_modelo", "")
            or (settings.OPENROUTER_MODEL or "").strip()
            or settings.openrouter_default_model
        )

        if not api_key:
            return jsonify({
                "error": "Chave do OpenRouter não configurada.",
                "modelos": [],
                "models": [],
                "selected_model": raw_model,
            }), 400

        models = listar_modelos(
            api_key,
            timeout_seconds=settings.openrouter_timeout_seconds,
            referer=settings.openrouter_referer,
            title=settings.openrouter_title,
        )

        # Filter to free models only (pricing = 0)
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
            normalized.append({
                "id": (model.get("id") or "").strip(),
                "name": (model.get("name") or model.get("id") or "").strip(),
                "context_length": model.get("context_length"),
                "pricing": pricing,
            })

        return jsonify({
            "modelos": normalized,
            "models": normalized,
            "selected_model": raw_model,
        })
    except AIServiceError as err:
        return jsonify({"error": err.user_message, "modelos": [], "models": []}), err.status_code
    except Exception as e:
        return jsonify({"error": str(e), "modelos": [], "models": []}), 500


@bp.route('/extratos/subpastas', methods=['GET'])
def listar_subpastas_extratos():
    """Lista subpastas de extratos."""
    try:
        extratos_dir = os.path.join(str(settings.base_dir), 'DADOS', 'extratos')
        
        if not os.path.exists(extratos_dir):
            return jsonify([])
        
        subpastas = listar_subpastas(extratos_dir)
        return jsonify(subpastas)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/extratos/validar', methods=['POST'])
def validar_extratos():
    """Valida configuração de origem/destino de extratos."""
    data = request.get_json(silent=True) or {}
    
    try:
        resultado = validar_origem_destino(
            data.get('origem', ''),
            data.get('destino', ''),
        )
        return jsonify(resultado)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/extratos/processar', methods=['POST'])
def processar_extratos_route():
    """Processa extratos bancários."""
    try:
        data = request.get_json(silent=True) or {}
        resultado = processar_extratos(
            origem=data.get('origem', ''),
            destino=data.get('destino', ''),
            modelo=data.get('modelo', ''),
            dry_run=data.get('dry_run', False),
        )
        
        return jsonify(resultado)
    except Exception as e:
        current_app.logger.error('Erro ao processar extratos: %s', e)
        return jsonify({'error': str(e)}), 500
