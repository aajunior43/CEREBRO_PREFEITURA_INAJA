"""
app/routes/protocolo.py — Rotas de gestão de protocolo
"""

import os
from flask import Blueprint, request, jsonify
from app.utils.db import get_db
from app.utils.helpers import row_to_dict

bp = Blueprint('protocolo', __name__)


@bp.route('/protocolo', methods=['GET'])
def listar_protocolos():
    """Lista protocolos."""
    try:
        conn = get_db()
        rows = conn.execute("""
            SELECT * FROM protocolos ORDER BY criado_em DESC LIMIT 200
        """).fetchall()
        return jsonify([row_to_dict(r) for r in rows])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/protocolo', methods=['POST'])
def criar_protocolo():
    """Cria novo protocolo."""
    data = request.get_json(silent=True) or {}
    
    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO protocolos 
            (numero, tipo, direcao, origem_destino, assunto, data_protocolo, prazo_resposta, status, observacoes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get('numero', ''),
            data.get('tipo', ''),
            data.get('direcao', 'recebido'),
            data.get('origem_destino', ''),
            data.get('assunto', ''),
            data.get('data_protocolo', ''),
            data.get('prazo_resposta', ''),
            data.get('status', 'recebido'),
            data.get('observacoes', ''),
        ))
        
        new_id = cur.lastrowid
        conn.commit()
        
        row = conn.execute("SELECT * FROM protocolos WHERE id=?", (new_id,)).fetchone()
        return jsonify(row_to_dict(row)), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/protocolo/<int:pid>', methods=['PUT'])
def atualizar_protocolo(pid):
    """Atualiza protocolo."""
    data = request.get_json(silent=True) or {}
    
    try:
        conn = get_db()
        
        fields = []
        values = []
        
        for key in ['tipo', 'direcao', 'origem_destino', 'assunto', 'data_protocolo', 
                    'prazo_resposta', 'status', 'observacoes']:
            if key in data:
                fields.append(f"{key}=?")
                values.append(data.get(key))
        
        if fields:
            values.append(pid)
            conn.execute(f"UPDATE protocolos SET {','.join(fields)} WHERE id=?", values)
            conn.commit()
        
        row = conn.execute("SELECT * FROM protocolos WHERE id=?", (pid,)).fetchone()
        return jsonify(row_to_dict(row))
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/protocolo/<int:pid>', methods=['DELETE'])
def excluir_protocolo(pid):
    """Exclui protocolo."""
    try:
        conn = get_db()
        
        row = conn.execute("SELECT * FROM protocolos WHERE id=?", (pid,)).fetchone()
        if not row:
            return jsonify({'error': 'Protocolo não encontrado'}), 404
        
        conn.execute("DELETE FROM protocolos WHERE id=?", (pid,))
        conn.commit()
        
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
