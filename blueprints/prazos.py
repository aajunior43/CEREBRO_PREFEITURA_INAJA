import time as _time

from flask import Blueprint, request, jsonify
from database import get_db

bp = Blueprint('prazos', __name__)


@bp.route('/prazos', methods=['GET'])
def prazos_listar():
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
        rows = conn.execute(f'SELECT * FROM prazos {where} ORDER BY data_limite ASC', params).fetchall()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/prazos/resumo', methods=['GET'])
def prazos_resumo():
    try:
        conn = get_db()
        hoje = _time.strftime('%Y-%m-%d')
        em7 = _time.strftime('%Y-%m-%d', _time.localtime(_time.time() + 7*86400))
        em30 = _time.strftime('%Y-%m-%d', _time.localtime(_time.time() + 30*86400))
        vencidos = conn.execute("SELECT COUNT(*) FROM prazos WHERE resolvido=0 AND data_limite < ?", (hoje,)).fetchone()[0]
        urgentes = conn.execute("SELECT COUNT(*) FROM prazos WHERE resolvido=0 AND data_limite >= ? AND data_limite <= ?", (hoje, em7)).fetchone()[0]
        atencao  = conn.execute("SELECT COUNT(*) FROM prazos WHERE resolvido=0 AND data_limite > ? AND data_limite <= ?", (em7, em30)).fetchone()[0]
        ok       = conn.execute("SELECT COUNT(*) FROM prazos WHERE resolvido=0 AND data_limite > ?", (em30,)).fetchone()[0]
        total    = conn.execute("SELECT COUNT(*) FROM prazos WHERE resolvido=0").fetchone()[0]
        return jsonify({'vencidos': vencidos, 'urgentes': urgentes, 'atencao': atencao, 'ok': ok, 'total': total})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/prazos', methods=['POST'])
def prazos_criar():
    try:
        data = request.get_json(force=True) or {}
        titulo = (data.get('titulo') or '').strip()
        data_limite = (data.get('data_limite') or '').strip()
        if not titulo:
            return jsonify({'error': 'Campo "titulo" é obrigatório'}), 400
        if not data_limite:
            return jsonify({'error': 'Campo "data_limite" é obrigatório'}), 400
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO prazos (titulo, descricao, data_limite, categoria) VALUES (?,?,?,?)",
            (titulo, (data.get('descricao') or '').strip(), data_limite, (data.get('categoria') or 'geral').strip())
        )
        conn.commit()
        row = conn.execute("SELECT * FROM prazos WHERE id=?", (cur.lastrowid,)).fetchone()
        return jsonify(dict(row)), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/prazos/<int:prazo_id>', methods=['PUT'])
def prazos_atualizar(prazo_id):
    try:
        data = request.get_json(force=True) or {}
        conn = get_db()
        row = conn.execute("SELECT * FROM prazos WHERE id=?", (prazo_id,)).fetchone()
        if not row:
            return jsonify({'error': 'Prazo não encontrado'}), 404
        fields = {}
        for k in ('titulo', 'descricao', 'data_limite', 'categoria'):
            if k in data:
                fields[k] = (data[k] or '').strip()
        if 'resolvido' in data:
            fields['resolvido'] = 1 if data['resolvido'] else 0
        if not fields:
            return jsonify(dict(row))
        set_clause = ', '.join(f'{k}=?' for k in fields)
        conn.execute(f'UPDATE prazos SET {set_clause} WHERE id=?', list(fields.values()) + [prazo_id])
        conn.commit()
        row = conn.execute("SELECT * FROM prazos WHERE id=?", (prazo_id,)).fetchone()
        return jsonify(dict(row))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/prazos/<int:prazo_id>', methods=['DELETE'])
def prazos_excluir(prazo_id):
    try:
        conn = get_db()
        r = conn.execute("SELECT id FROM prazos WHERE id=?", (prazo_id,)).fetchone()
        if not r:
            return jsonify({'error': 'Prazo não encontrado'}), 404
        conn.execute("DELETE FROM prazos WHERE id=?", (prazo_id,))
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
