"""
app/routes/credores.py — Rotas de gestão de credores
"""

import re
from flask import Blueprint, request, jsonify
from app.utils.db import get_db
from app.utils.helpers import row_to_dict, normalizar_cnpj, cnpj_valido
from app.utils.pagination import paginate

bp = Blueprint('credores', __name__)


def _credor_payload(data: dict, *, partial: bool = False) -> tuple:
    """Valida e extrai payload de credor."""
    errors = []
    payload = {}

    def has_value(key: str) -> bool:
        return key in data and data.get(key) is not None

    if not partial or has_value('nome'):
        nome = (data.get('nome') or '').strip().upper()
        if not nome:
            errors.append('Campo "nome" é obrigatório')
        elif len(nome) < 3:
            errors.append('Campo "nome" deve ter pelo menos 3 caracteres')
        else:
            payload['nome'] = nome

    if not partial or has_value('descricao'):
        payload['descricao'] = (data.get('descricao') or '').strip().upper()

    if not partial or has_value('departamento'):
        payload['departamento'] = (data.get('departamento') or '').strip().upper()

    if not partial or has_value('tipo_valor'):
        tipo_valor = (data.get('tipo_valor') or 'FIXO').strip().upper()
        if tipo_valor not in {'FIXO', 'VARIÁVEL', 'VARIAVEL'}:
            errors.append('Campo "tipo_valor" deve ser FIXO ou VARIÁVEL')
        else:
            payload['tipo_valor'] = 'VARIÁVEL' if tipo_valor == 'VARIAVEL' else tipo_valor

    if not partial or has_value('valor'):
        try:
            valor = float(data.get('valor') or 0)
            if valor < 0:
                raise ValueError
            payload['valor'] = valor
        except Exception:
            errors.append('Campo "valor" deve ser numérico e maior ou igual a zero')

    if not partial or has_value('cnpj'):
        cnpj = normalizar_cnpj(data.get('cnpj', ''))
        if cnpj:
            if len(cnpj) != 14:
                errors.append('Campo "cnpj" deve conter 14 dígitos')
            elif not cnpj_valido(cnpj):
                errors.append('Campo "cnpj" inválido')
        payload['cnpj'] = cnpj

    if not partial or has_value('email'):
        email = (data.get('email') or '').strip().lower()
        if email and not re.fullmatch(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
            errors.append('Campo "email" inválido')
        payload['email'] = email

    if not partial or has_value('pagamento'):
        pagamento = (data.get('pagamento') or '').strip()
        if pagamento and not re.fullmatch(r'\d{1,3}', pagamento):
            errors.append('Campo "pagamento" deve conter apenas dias em número')
        payload['pagamento'] = pagamento

    if not partial or has_value('solicitacao'):
        payload['solicitacao'] = (data.get('solicitacao') or '').strip()

    if not partial or has_value('validade'):
        validade = (data.get('validade') or '').strip()
        if validade and not re.fullmatch(r'\d{4}-\d{2}-\d{2}', validade):
            errors.append('Campo "validade" deve estar no formato AAAA-MM-DD')
        payload['validade'] = validade

    if not partial or has_value('obs'):
        payload['obs'] = (data.get('obs') or '').strip().upper()

    return payload, errors


def _buscar_credor_duplicado(conn, cnpj: str, *, ignore_id: int = None):
    """Verifica duplicidade por CNPJ."""
    if cnpj:
        row = conn.execute(
            "SELECT id, nome FROM credores WHERE ativo=1 AND cnpj=?" +
            (" AND id<>?" if ignore_id else ""),
            (cnpj, ignore_id) if ignore_id else (cnpj,)
        ).fetchone()
        if row:
            return row, 'Já existe um credor ativo com este CNPJ'
    return None, ''


def _montar_filtros_credores(args):
    search = (args.get('search') or '').strip()
    departamento = (args.get('departamento') or '').strip().upper()
    tipo = (args.get('tipo') or '').strip().upper()
    status_cadastro = (args.get('status_cadastro') or '').strip().lower()
    somente_vencidos = str(args.get('somente_vencidos') or '').strip().lower() in {'1', 'true', 'yes', 'on'}
    vencendo_dias = args.get('vencendo_dias', type=int)
    status = (args.get('status') or '').strip().lower()
    ano = args.get('ano', type=int)
    mes = args.get('mes', type=int)

    clauses = ["ativo=1"]
    params = []

    if search:
        like = f'%{search.lower()}%'
        clauses.append("""(
            LOWER(nome) LIKE ?
            OR LOWER(COALESCE(descricao, '')) LIKE ?
            OR LOWER(COALESCE(cnpj, '')) LIKE ?
            OR LOWER(COALESCE(email, '')) LIKE ?
        )""")
        params.extend([like, like, like, like])

    if departamento:
        clauses.append("COALESCE(departamento, '')=?")
        params.append(departamento)

    if tipo:
        clauses.append("COALESCE(tipo_valor, 'FIXO')=?")
        params.append('VARIÁVEL' if tipo == 'VARIAVEL' else tipo)

    if status_cadastro == 'sem_cnpj':
        clauses.append("COALESCE(cnpj, '')=''")
    elif status_cadastro == 'sem_email':
        clauses.append("COALESCE(email, '')=''")
    elif status_cadastro == 'com_pendencias':
        clauses.append("(COALESCE(cnpj, '')='' OR COALESCE(email, '')='')")

    if somente_vencidos:
        clauses.append("COALESCE(validade, '')<>'' AND date(validade) < date('now','localtime')")
    elif vencendo_dias is not None and vencendo_dias >= 0:
        clauses.append("COALESCE(validade, '')<>'' AND date(validade) >= date('now','localtime') AND date(validade) <= date('now','localtime', ?)")
        params.append(f'+{vencendo_dias} day')

    if status in {'empenhado', 'pendente'} and ano and mes:
        exists_sql = (
            "EXISTS (SELECT 1 FROM empenhos e "
            "WHERE e.credor_id = credores.id AND e.ano=? AND e.mes=?)"
        )
        clauses.append(exists_sql if status == 'empenhado' else f'NOT {exists_sql}')
        params.extend([ano, mes])

    return clauses, params


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

        clauses, params = _montar_filtros_credores(request.args)
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

    payload, errors = _credor_payload(data)
    if errors:
        return jsonify({'errors': errors}), 400

    try:
        conn = get_db()

        if payload.get('cnpj'):
            dup, msg = _buscar_credor_duplicado(conn, payload['cnpj'])
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

        conn.execute("""
            INSERT INTO logs (acao, credor_id, credor_nome, detalhes)
            VALUES (?, ?, ?, ?)
        """, ('CREATE', new_id, payload['nome'], 'Credor criado'))
        conn.commit()

        row = conn.execute("SELECT * FROM credores WHERE id=?", (new_id,)).fetchone()
        return jsonify(row_to_dict(row)), 201

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/credores/<int:cid>', methods=['PUT'])
def atualizar_credor(cid):
    """Atualiza credor existente."""
    data = request.get_json(silent=True) or {}

    payload, errors = _credor_payload(data, partial=True)
    if errors:
        return jsonify({'errors': errors}), 400

    try:
        conn = get_db()

        existing = conn.execute("SELECT * FROM credores WHERE id=?", (cid,)).fetchone()
        if not existing:
            return jsonify({'error': 'Credor não encontrado'}), 404

        if payload.get('cnpj') and payload['cnpj'] != existing['cnpj']:
            dup, msg = _buscar_credor_duplicado(conn, payload['cnpj'], ignore_id=cid)
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

        conn.execute("""
            INSERT INTO logs (acao, credor_id, credor_nome, detalhes)
            VALUES (?, ?, ?, ?)
        """, ('UPDATE', cid, existing['nome'], 'Credor atualizado'))
        conn.commit()

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

        conn.execute("""
            INSERT INTO logs (acao, credor_id, credor_nome, detalhes)
            VALUES (?, ?, ?, ?)
        """, ('DELETE', cid, row['nome'], 'Credor excluído'))
        conn.commit()

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
