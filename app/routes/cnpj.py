"""
app/routes/cnpj.py — Rotas de consulta CNPJ
"""

import requests
from flask import Blueprint, request, jsonify
from app.utils.db import get_db
from app.utils.helpers import normalizar_cnpj

bp = Blueprint('cnpj', __name__)


@bp.route('/cnpj/buscar', methods=['POST'])
def buscar_cnpj():
    """Consulta CNPJ na Receita Federal via CNPJá/ReceitaWS."""
    data = request.get_json(silent=True) or {}
    cnpj_raw = data.get('cnpj', '')
    
    if not cnpj_raw:
        return jsonify({'error': 'CNPJ é obrigatório'}), 400
    
    cnpj = normalizar_cnpj(cnpj_raw)
    
    if len(cnpj) != 14:
        return jsonify({'error': 'CNPJ deve ter 14 dígitos'}), 400
    
    try:
        conn = get_db()
        
        # Tentar CNPJá primeiro
        row = conn.execute("SELECT valor FROM configuracoes WHERE chave='api_cnpja_key'").fetchone()
        api_key = row['valor'] if row else ''
        
        if api_key:
            # CNPJá com API key (mais consultas)
            url = f'https://cnpja.com/office/{cnpj}'
            headers = {'X-API-Key': api_key}
        else:
            # CNPJá free (5 consultas/min)
            url = f'https://cnpja.com/office/{cnpj}'
            headers = {}
        
        resp = requests.get(url, headers=headers, timeout=10)
        
        if resp.status_code == 404:
            return jsonify({'error': 'CNPJ não encontrado'}), 404
        
        if resp.status_code == 429:
            return jsonify({'error': 'Limite de consultas atingido. Configure API key.'}), 429
        
        if resp.status_code >= 400:
            return jsonify({'error': f'Erro HTTP {resp.status_code}'}), resp.status_code
        
        dados = resp.json()
        return jsonify({'ok': True, 'dados': dados})
        
    except requests.RequestException as e:
        return jsonify({'error': f'Falha de conexão: {e}'}), 502
    except Exception as e:
        return jsonify({'error': str(e)}), 500
