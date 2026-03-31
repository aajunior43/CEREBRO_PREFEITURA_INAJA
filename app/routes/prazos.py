"""
app/routes/prazos.py — Rotas de gestão de prazos
"""

import time as _time
from flask import Blueprint, request, jsonify
from app.utils.db import get_db
from app.utils.helpers import row_to_dict

bp = Blueprint('prazos', __name__)


@bp.route('/prazos', methods=['GET'])
def listar_prazos():
    """Lista prazos com filtros."""
    try:
        conn = get_db()
        status_f = request.args.get('status', 'ativos')
        categoria = request.args.get('categoria', '')
        
        clauses = []
        params = []
        
        if status_f == 'ativos':
            clauses.append('resolvido=0')
        elif status_f == 'resolvidos':
            clauses.append('resolvido=1')
        
        if categoria:
            clauses.append('categoria=?')
            params.append(categoria)
        
        where = ('WHERE ' + ' AND '.join(clauses)) if clauses else ''
        rows = conn.execute(
            f'SELECT * FROM prazos {where} ORDER BY data_limite ASC',
            params
        ).fetchall()
        
        return jsonify([row_to_dict(r) for r in rows])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/prazos/resumo', methods=['GET'])
def resumo_prazos():
    """Retorna resumo de prazos."""
    try:
        conn = get_db()
        hoje = _time.strftime('%Y-%m-%d')
        em7 = _time.strftime('%Y-%m-%d', _time.localtime(_time.time() + 7*86400))
        em30 = _time.strftime('%Y-%m-%d', _time.localtime(_time.time() + 30*86400))
        
        vencidos = conn.execute("SELECT COUNT(*) FROM prazos WHERE resolvido=0 AND data_limite < ?", (hoje,)).fetchone()[0]
        urgentes = conn.execute("SELECT COUNT(*) FROM prazos WHERE resolvido=0 AND data_limite >= ? AND data_limite <= ?", (hoje, em7)).fetchone()[0]
        atencao = conn.execute("SELECT COUNT(*) FROM prazos WHERE resolvido=0 AND data_limite > ? AND data_limite <= ?", (em7, em30)).fetchone()[0]
        ok = conn.execute("SELECT COUNT(*) FROM prazos WHERE resolvido=0 AND data_limite > ?", (em30,)).fetchone()[0]
        total = conn.execute("SELECT COUNT(*) FROM prazos WHERE resolvido=0").fetchone()[0]
        
        return jsonify({
            'vencidos': vencidos,
            'urgentes': urgentes,
            'atencao': atencao,
            'ok': ok,
            'total': total,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/prazos', methods=['POST'])
def criar_prazo():
    """Cria novo prazo."""
    data = request.get_json(silent=True) or {}
    
    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO prazos (titulo, descricao, data_limite, categoria, resolvido)
            VALUES (?, ?, ?, ?, ?)
        """, (
            data.get('titulo', ''),
            data.get('descricao', ''),
            data.get('data_limite', ''),
            data.get('categoria', 'geral'),
            0,
        ))
        
        new_id = cur.lastrowid
        conn.commit()
        
        row = conn.execute("SELECT * FROM prazos WHERE id=?", (new_id,)).fetchone()
        return jsonify(row_to_dict(row)), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/prazos/<int:pid>', methods=['PUT'])
def atualizar_prazo(pid):
    """Atualiza prazo."""
    data = request.get_json(silent=True) or {}
    
    try:
        conn = get_db()
        
        fields = []
        values = []
        
        for key in ['titulo', 'descricao', 'data_limite', 'categoria', 'resolvido']:
            if key in data:
                fields.append(f"{key}=?")
                values.append(data.get(key))
        
        if fields:
            values.append(pid)
            conn.execute(f"""
                UPDATE prazos SET {','.join(fields)} WHERE id=?
            """, values)
            conn.commit()
        
        row = conn.execute("SELECT * FROM prazos WHERE id=?", (pid,)).fetchone()
        return jsonify(row_to_dict(row))
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/prazos/<int:pid>', methods=['DELETE'])
def excluir_prazo(pid):
    """Exclui prazo."""
    try:
        conn = get_db()
        
        row = conn.execute("SELECT * FROM prazos WHERE id=?", (pid,)).fetchone()
        if not row:
            return jsonify({'error': 'Prazo não encontrado'}), 404
        
        conn.execute("DELETE FROM prazos WHERE id=?", (pid,))
        conn.commit()
        
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
