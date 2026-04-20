"""
app/routes/credores.py — Rotas de gestão de credores
"""

from flask import Blueprint, request, jsonify
from app.utils.db import get_db
from app.utils.helpers import (
    row_to_dict,
    credor_payload,
    buscar_credor_duplicado,
    montar_filtros_credores,
    parse_bool,
)
from app.utils.pagination import paginate
from app.utils.audit import log_audit

bp = Blueprint('credores', __name__)


def _should_include_summary(args) -> bool:
    raw = (args.get('include_summary') or '').strip().lower()
    return raw in {'1', 'true', 'yes', 'on'}


@bp.route('/credores', methods=['GET'])
def listar_credores():
    """Lista credores com filtros opcionais, paginação e resumo."""
    try:
        conn = get_db()
        limit = max(1, min(request.args.get('limit', 50, type=int), 1000))
        offset = max(0, request.args.get('offset', 0, type=int))
        sort_col = (request.args.get('sort_col') or 'departamento').strip().lower()
        sort_dir = (request.args.get('sort_dir') or 'asc').strip().lower()
        if sort_dir not in {'asc', 'desc'}:
            sort_dir = 'asc'
        sort_map = {
            'nome': 'nome',
            'departamento': 'departamento',
            'valor': 'valor',
            'tipo': 'tipo_valor',
            'tipo_valor': 'tipo_valor',
            'validade': 'validade',
        }
        order_by = sort_map.get(sort_col, 'departamento')

        clauses, params = montar_filtros_credores(request.args)
        where = ' AND '.join(clauses)

        total = conn.execute(
            f"SELECT COUNT(*) AS total FROM credores WHERE {where}",
            params
        ).fetchone()['total']
        rows = conn.execute(
            f"SELECT * FROM credores WHERE {where} ORDER BY {order_by} {sort_dir}, nome ASC LIMIT ? OFFSET ?",
            (*params, limit, offset)
        ).fetchall()

        resumo = None
        if _should_include_summary(request.args):
            resumo = conn.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN COALESCE(tipo_valor, 'FIXO') LIKE 'VAR%' THEN 1 ELSE 0 END) AS variaveis,
                    SUM(CASE WHEN COALESCE(tipo_valor, 'FIXO') NOT LIKE 'VAR%' THEN 1 ELSE 0 END) AS fixos,
                    SUM(CASE WHEN COALESCE(cnpj, '')='' THEN 1 ELSE 0 END) AS sem_cnpj,
                    SUM(CASE WHEN COALESCE(email, '')='' THEN 1 ELSE 0 END) AS sem_email,
                    SUM(CASE WHEN COALESCE(validade, '')<>'' AND date(validade) < date('now','localtime') THEN 1 ELSE 0 END) AS vencidos,
                    SUM(CASE WHEN COALESCE(validade, '')<>'' AND date(validade) >= date('now','localtime') AND date(validade) <= date('now','localtime', '+30 day') THEN 1 ELSE 0 END) AS vencendo_30
                FROM credores
                WHERE ativo=1
                """
            ).fetchone()

        items = [row_to_dict(r) for r in rows]
        
        # Usar wrapper de paginação
        result = paginate(
            items=items,
            page=(offset // limit) + 1,
            per_page=limit,
            total=total
        )
        
        # Adicionar resumo se solicitado
        if resumo:
            result["summary"] = row_to_dict(resumo)
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/credores', methods=['POST'])
def criar_credor():
    """Cria novo credor."""
    data = request.get_json(silent=True) or {}

    payload, errors = credor_payload(data)
    if errors:
        return jsonify({'errors': errors}), 400

    try:
        conn = get_db()

        if payload.get('cnpj'):
            dup, msg = buscar_credor_duplicado(conn, payload['cnpj'])
            if dup:
                return jsonify({'error': msg}), 409

        cur = conn.cursor()
        cur.execute("""
            INSERT INTO credores (nome, valor, descricao, cnpj, email, tipo_valor,
                                  solicitacao, pagamento, validade, departamento, obs)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (
            payload.get('nome'),
            payload.get('valor', 0),
            payload.get('descricao', ''),
            payload.get('cnpj', ''),
            payload.get('email', ''),
            payload.get('tipo_valor', 'FIXO'),
            payload.get('solicitacao', ''),
            payload.get('pagamento', ''),
            payload.get('validade', ''),
            payload.get('departamento', ''),
            payload.get('obs', ''),
        ))

        new_id = cur.lastrowid
        conn.commit()

        log_audit('CREATE', 'credores', resource_id=new_id,
                  details=f"Credor criado: {payload['nome']}", conn=conn)

        row = conn.execute("SELECT * FROM credores WHERE id=?", (new_id,)).fetchone()
        return jsonify(row_to_dict(row)), 201

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/credores/<int:cid>', methods=['PUT'])
def atualizar_credor(cid):
    """Atualiza credor existente."""
    data = request.get_json(silent=True) or {}

    payload, errors = credor_payload(data, partial=True)
    if errors:
        return jsonify({'errors': errors}), 400

    try:
        conn = get_db()

        existing = conn.execute("SELECT * FROM credores WHERE id=?", (cid,)).fetchone()
        if not existing:
            return jsonify({'error': 'Credor não encontrado'}), 404

        if payload.get('cnpj') and payload['cnpj'] != existing['cnpj']:
            dup, msg = buscar_credor_duplicado(conn, payload['cnpj'], ignore_id=cid)
            if dup:
                return jsonify({'error': msg}), 409

        fields = []
        values = []
        for key, value in payload.items():
            fields.append(f"{key}=?")
            values.append(value)

        if fields:
            values.append(cid)
            conn.execute(f"""
                UPDATE credores SET {','.join(fields)}, obs=COALESCE(?, obs)
                WHERE id=?
            """, values)
            conn.commit()

        log_audit('UPDATE', 'credores', resource_id=cid,
                  details=f"Credor atualizado: {existing['nome']}", conn=conn)

        row = conn.execute("SELECT * FROM credores WHERE id=?", (cid,)).fetchone()
        return jsonify(row_to_dict(row))

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/credores/<int:cid>', methods=['DELETE'])
def excluir_credor(cid):
    """Exclui credor (soft delete)."""
    try:
        conn = get_db()

        row = conn.execute("SELECT * FROM credores WHERE id=?", (cid,)).fetchone()
        if not row:
            return jsonify({'error': 'Credor não encontrado'}), 404

        conn.execute("UPDATE credores SET ativo=0 WHERE id=?", (cid,))
        conn.commit()

        log_audit('DELETE', 'credores', resource_id=cid,
                  details=f"Credor excluído: {row['nome']}", conn=conn)

        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/credores/<int:cid>/historico', methods=['GET'])
def historico_credor(cid):
    """Retorna histórico de empenhos do credor."""
    try:
        conn = get_db()
        rows = conn.execute("""
            SELECT e.*, c.nome as credor_nome
            FROM empenhos e
            JOIN credores c ON c.id = e.credor_id
            WHERE e.credor_id = ?
            ORDER BY e.ano DESC, e.mes DESC
        """, (cid,)).fetchall()

        return jsonify([row_to_dict(r) for r in rows])
    except Exception as e:
        return jsonify({'error': str(e)}), 500
