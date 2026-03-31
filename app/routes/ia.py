"""
app/routes/ia.py — Rotas de inteligência artificial (OpenRouter)
"""

from flask import Blueprint, request, jsonify, current_app
from app.utils.db import get_db
from services.openrouter_service import chat_completion, listar_modelos, AIServiceError, parse_http_error

bp = Blueprint('ia', __name__)


@bp.route('/ia/modelos', methods=['GET'])
def listar_modelos_ia():
    """Lista modelos de IA disponíveis."""
    try:
        conn = get_db()
        row = conn.execute("SELECT valor FROM configuracoes WHERE chave='api_openrouter_key'").fetchone()
        api_key = row['valor'] if row else ''
        
        if not api_key:
            return jsonify({'error': 'Chave API não configurada'}), 400
        
        modelos = listar_modelos(api_key)
        return jsonify({'ok': True, 'modelos': modelos})
    except AIServiceError as e:
        return jsonify({'error': str(e)}), e.status_code if hasattr(e, 'status_code') else 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/ia/chat', methods=['POST'])
def chat_ia():
    """Endpoint de chat com IA."""
    data = request.get_json(silent=True) or {}
    mensagem = data.get('mensagem', '')
    modelo = data.get('modelo', '')
    sistema = data.get('sistema', '')
    
    if not mensagem:
        return jsonify({'error': 'Mensagem é obrigatória'}), 400
    
    try:
        conn = get_db()
        
        # Obter chave API
        row = conn.execute("SELECT valor FROM configuracoes WHERE chave='api_openrouter_key'").fetchone()
        api_key = row['valor'] if row else ''
        
        if not api_key:
            return jsonify({'error': 'Chave API não configurada'}), 400
        
        # Obter modelo padrão se não fornecido
        if not modelo:
            row = conn.execute("SELECT valor FROM configuracoes WHERE chave='api_openrouter_modelo'").fetchone()
            modelo = row['valor'] if row else 'meta-llama/llama-3.2-3b-instruct:free'
        
        # Construir messages
        messages = []
        if sistema:
            messages.append({'role': 'system', 'content': sistema})
        messages.append({'role': 'user', 'content': mensagem})
        
        resposta = chat_completion(
            api_key=api_key,
            messages=messages,
            model=modelo,
        )
        
        return jsonify({'ok': True, 'resposta': resposta})
        
    except AIServiceError as e:
        error_data = parse_http_error(e)
        return jsonify({'error': error_data.get('message', str(e))}), e.status_code if hasattr(e, 'status_code') else 500
    except Exception as e:
        current_app.logger.error('Erro no chat IA: %s', e)
        return jsonify({'error': str(e)}), 500


@bp.route('/ia/organizar-extratos', methods=['POST'])
def organizar_extratos_ia():
    """Organiza extratos usando IA."""
    data = request.get_json(silent=True) or {}
    texto_extrato = data.get('texto', '')
    
    if not texto_extrato:
        return jsonify({'error': 'Texto do extrato é obrigatório'}), 400
    
    try:
        conn = get_db()
        
        row = conn.execute("SELECT valor FROM configuracoes WHERE chave='api_openrouter_key'").fetchone()
        api_key = row['valor'] if row else ''
        
        if not api_key:
            return jsonify({'error': 'Chave API não configurada'}), 400
        
        row = conn.execute("SELECT valor FROM configuracoes WHERE chave='api_openrouter_modelo'").fetchone()
        modelo = row['valor'] if row else 'openai/gpt-4o-mini'
        
        # Prompt para organizar extratos
        prompt = """Você é um assistente especializado em organizar extratos bancários.
Analise o extrato e categorize as transações.

EXTRATO:
""" + texto_extrato
        
        messages = [
            {'role': 'system', 'content': 'Você é um assistente especializado em organizar extratos bancários.'},
            {'role': 'user', 'content': prompt}
        ]
        
        resposta = chat_completion(
            api_key=api_key,
            messages=messages,
            model=modelo,
        )
        
        return jsonify({'ok': True, 'resposta': resposta})
        
    except AIServiceError as e:
        return jsonify({'error': str(e)}), e.status_code if hasattr(e, 'status_code') else 500
    except Exception as e:
        current_app.logger.error('Erro ao organizar extratos: %s', e)
        return jsonify({'error': str(e)}), 500
