"""
app/routes/autentique.py — Rotas de integração Autentique
"""

import requests
import json
import mimetypes
import os
from flask import Blueprint, request, jsonify
from config import settings
from app.utils.db import get_db
from app.utils.helpers import row_to_dict, normalize_phone_br

bp = Blueprint('autentique', __name__)

DOCUMENTS_DIR = os.path.join(str(settings.base_dir), 'documentos_centro')


def _get_autentique_key(conn):
    """Obtém chave API da Autentique."""
    row = conn.execute("SELECT valor FROM configuracoes WHERE chave='api_autentique_key'").fetchone()
    return row['valor'] if row else ''


@bp.route('/autentique/testar', methods=['POST'])
def testar_autentique():
    """Testa conexão com Autentique."""
    try:
        conn = get_db()
        api_key = _get_autentique_key(conn)
        
        if not api_key:
            return jsonify({'error': 'Chave API não configurada'}), 400
        
        query = """
{
  me {
    id
    name
    email
  }
}
""".strip()
        
        resp = requests.post(
            'https://api.autentique.com.br/v2/graphql',
            headers={'Authorization': f'Bearer {api_key}'},
            json={'query': query},
            timeout=10,
        )
        
        if resp.status_code >= 400:
            return jsonify({'error': f'Erro HTTP {resp.status_code}'}), resp.status_code
        
        data = resp.json()
        if data.get('errors'):
            return jsonify({'error': data['errors'][0].get('message', 'Erro desconhecido')}), 400
        
        return jsonify({'ok': True, 'user': data.get('data', {}).get('me')})
        
    except requests.RequestException as e:
        return jsonify({'error': f'Falha de conexão: {e}'}), 502
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/autentique/saldo', methods=['GET'])
def saldo_autentique():
    """Consulta saldo Autentique."""
    try:
        conn = get_db()
        api_key = _get_autentique_key(conn)
        
        if not api_key:
            return jsonify({'error': 'Chave API não configurada'}), 400
        
        query = """
{
  me {
    credits
    documents {
      total
    }
  }
}
""".strip()
        
        resp = requests.post(
            'https://api.autentique.com.br/v2/graphql',
            headers={'Authorization': f'Bearer {api_key}'},
            json={'query': query},
            timeout=10,
        )
        
        if resp.status_code >= 400:
            return jsonify({'error': f'Erro HTTP {resp.status_code}'}), resp.status_code
        
        data = resp.json()
        return jsonify({'ok': True, 'data': data.get('data', {})})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/autentique/envios', methods=['GET'])
def listar_envios():
    """Lista envios Autentique."""
    try:
        conn = get_db()
        rows = conn.execute("""
            SELECT e.*,
                   d.nome_original AS documento_origem_nome,
                   d.categoria AS documento_origem_categoria
            FROM autentique_envios e
            LEFT JOIN documentos_centro d ON d.id = e.documento_centro_id
            ORDER BY e.id DESC
            LIMIT 200
        """).fetchall()
        
        return jsonify([row_to_dict(r) for r in rows])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/autentique/contatos', methods=['GET'])
def listar_contatos():
    """Lista contatos Autentique."""
    try:
        conn = get_db()
        rows = conn.execute("SELECT * FROM autentique_contatos ORDER BY nome COLLATE NOCASE ASC").fetchall()
        return jsonify([row_to_dict(r) for r in rows])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/autentique/contatos', methods=['POST'])
def salvar_contato():
    """Salva contato Autentique."""
    data = request.get_json(silent=True) or {}
    nome = (data.get('nome') or '').strip()
    phone_raw = (data.get('phone') or '').strip()
    
    if not nome:
        return jsonify({'error': 'Nome é obrigatório'}), 400
    if not phone_raw:
        return jsonify({'error': 'WhatsApp é obrigatório'}), 400
    
    phone = normalize_phone_br(phone_raw)
    
    try:
        conn = get_db()
        
        existing = conn.execute("SELECT * FROM autentique_contatos WHERE phone=?", (phone,)).fetchone()
        
        if existing:
            conn.execute(
                "UPDATE autentique_contatos SET nome=?, atualizado_em=datetime('now','localtime') WHERE id=?",
                (nome, existing['id'])
            )
            conn.commit()
            row = conn.execute("SELECT * FROM autentique_contatos WHERE id=?", (existing['id'],)).fetchone()
            return jsonify(row_to_dict(row))
        
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO autentique_contatos (nome, phone, criado_em, atualizado_em) VALUES (?, ?, datetime('now','localtime'), datetime('now','localtime'))",
            (nome, phone)
        )
        new_id = cur.lastrowid
        conn.commit()
        
        row = conn.execute("SELECT * FROM autentique_contatos WHERE id=?", (new_id,)).fetchone()
        return jsonify(row_to_dict(row)), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/autentique/contatos/<int:contato_id>', methods=['DELETE'])
def excluir_contato(contato_id):
    """Exclui contato."""
    try:
        conn = get_db()
        
        row = conn.execute("SELECT * FROM autentique_contatos WHERE id=?", (contato_id,)).fetchone()
        if not row:
            return jsonify({'error': 'Contato não encontrado'}), 404
        
        conn.execute("DELETE FROM autentique_contatos WHERE id=?", (contato_id,))
        conn.commit()
        
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/autentique/envios/<int:envio_id>', methods=['DELETE'])
def excluir_envio(envio_id):
    """Exclui envio."""
    try:
        conn = get_db()
        
        row = conn.execute("SELECT * FROM autentique_envios WHERE id=?", (envio_id,)).fetchone()
        if not row:
            return jsonify({'error': 'Envio não encontrado'}), 404
        
        conn.execute("DELETE FROM autentique_envios WHERE id=?", (envio_id,))
        conn.commit()
        
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
