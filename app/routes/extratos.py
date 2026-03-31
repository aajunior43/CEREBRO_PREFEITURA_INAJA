"""
app/routes/extratos.py — Rotas de processamento de extratos
"""

import os
from flask import Blueprint, request, jsonify, current_app
from config import settings
from app.utils.db import get_db
from services.extratos_service import listar_subpastas, processar_extratos, validar_origem_destino

bp = Blueprint('extratos', __name__)


@bp.route('/extratos/modelos-openrouter', methods=['GET'])
def listar_modelos_openrouter():
    """Lista modelos OpenRouter disponíveis."""
    try:
        from services.openrouter_service import listar_modelos
        modelos = listar_modelos()
        return jsonify({'ok': True, 'modelos': modelos})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


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
