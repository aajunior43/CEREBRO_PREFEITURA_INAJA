import re
import time as _time

from flask import Blueprint, request, jsonify, current_app
from config import settings
from database import get_db, row_to_dict
from helpers import _parse_bool
from services.empenhos_service import listar_empenhos_mes, listar_historico_credor, persistir_empenho

bp = Blueprint('credores', __name__)


def _normalizar_cnpj(cnpj: str) -> str:
    return re.sub(r'\D', '', (cnpj or '').strip())


def _credor_payload(data: dict, *, partial: bool = False) -> tuple[dict, list[str]]:
    errors: list[str] = []
    payload: dict = {}

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
        cnpj = _normalizar_cnpj(data.get('cnpj', ''))
        if cnpj and len(cnpj) != 14:
            errors.append('Campo "cnpj" deve conter 14 dígitos')
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


def _buscar_credor_duplicado(conn, cnpj: str, *, ignore_id: int | None = None):
    if cnpj:
        row = conn.execute(
            "SELECT id, nome FROM credores WHERE ativo=1 AND cnpj=?"
            + (" AND id<>?" if ignore_id else ""),
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
    somente_vencidos = _parse_bool(args.get('somente_vencidos'))
    vencendo_dias = args.get('vencendo_dias', type=int)

    clauses = ["ativo=1"]
    params: list = []

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

    return clauses, params


def _should_include_credores_summary(args) -> bool:
    raw = (args.get('include_summary') or '').strip().lower()
    return raw in {'1', 'true', 'yes', 'on'}


@bp.route('/credores', methods=['GET'])
def get_credores():
    try:
        limit = max(1, min(request.args.get('limit', 1000, type=int), 1000))
        offset = request.args.get('offset', 0, type=int)
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
        where_sql = ' AND '.join(clauses)
        conn = get_db()
        total = conn.execute(
            f"SELECT COUNT(*) AS total FROM credores WHERE {where_sql}",
            params
        ).fetchone()['total']
        rows = conn.execute(
            f"SELECT * FROM credores WHERE {where_sql} ORDER BY {order_by} {sort_dir}, nome ASC LIMIT ? OFFSET ?",
            (*params, limit, offset)
        ).fetchall()
        itens = [row_to_dict(r) for r in rows]
        resumo = None
        if _should_include_credores_summary(request.args):
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
        return jsonify({
            'items': itens,
            'total': total,
            'limit': limit,
            'offset': offset,
            'summary': row_to_dict(resumo) if resumo else None,
        })
    except Exception as e:
        current_app.logger.error('GET /api/credores: %s', e)
        return jsonify({'error': str(e)}), 500


@bp.route('/credores', methods=['POST'])
def add_credor():
    data = request.get_json(force=True) or {}
    payload, errors = _credor_payload(data, partial=False)
    if errors:
        return jsonify({'error': errors[0], 'errors': errors}), 400
    try:
        conn = get_db()
        duplicado, msg = _buscar_credor_duplicado(conn, payload.get('cnpj', ''))
        if duplicado:
            return jsonify({'error': msg, 'duplicado_id': duplicado['id']}), 409
        cur  = conn.cursor()
        cur.execute("""
            INSERT INTO credores
              (nome, valor, descricao, cnpj, email, tipo_valor, solicitacao, pagamento, validade, departamento, obs)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (
            payload.get('nome', ''),
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
        conn.execute(
            "INSERT INTO logs (acao, credor_id, credor_nome, detalhes) VALUES (?,?,?,?)",
            ('CRIAR', new_id, payload.get('nome', ''), payload.get('departamento', '') or 'Cadastro de credor')
        )
        conn.commit()
        row = conn.execute("SELECT * FROM credores WHERE id=?", (new_id,)).fetchone()
        return jsonify(row_to_dict(row)), 201
    except Exception as e:
        current_app.logger.error('POST /api/credores: %s', e)
        return jsonify({'error': str(e)}), 500


@bp.route('/credores/<int:cid>', methods=['PUT'])
def update_credor(cid):
    data = request.get_json(force=True) or {}
    payload, errors = _credor_payload(data, partial=False)
    if errors:
        return jsonify({'error': errors[0], 'errors': errors}), 400
    try:
        conn = get_db()
        atual = conn.execute("SELECT * FROM credores WHERE id=? AND ativo=1", (cid,)).fetchone()
        if not atual:
            return jsonify({'error': 'Credor não encontrado'}), 404
        cnpj_atual_normalizado = _normalizar_cnpj(atual['cnpj'] or '')
        cnpj_alterado = (payload.get('cnpj', '') != cnpj_atual_normalizado)
        cnpj_para_verificar = payload.get('cnpj', '') if cnpj_alterado else ''

        duplicado, msg = _buscar_credor_duplicado(conn, cnpj_para_verificar, ignore_id=cid)
        if duplicado:
            return jsonify({'error': msg, 'duplicado_id': duplicado['id']}), 409
        conn.execute("""
            UPDATE credores
               SET nome=?, valor=?, descricao=?, cnpj=?, email=?, tipo_valor=?, solicitacao=?, pagamento=?, validade=?, departamento=?, obs=?
             WHERE id=?
        """, (
            payload.get('nome', ''),
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
            cid,
        ))
        detalhes = []
        for key, label in (
            ('nome', 'Nome'),
            ('departamento', 'Departamento'),
            ('valor', 'Valor'),
            ('tipo_valor', 'Tipo'),
            ('validade', 'Validade'),
            ('cnpj', 'CNPJ'),
            ('email', 'E-mail'),
        ):
            anterior = atual[key] if key in atual.keys() else ''
            novo = payload.get(key, '')
            if str(anterior or '') != str(novo or ''):
                detalhes.append(f'{label}: {anterior or "—"} → {novo or "—"}')
        conn.execute(
            "INSERT INTO logs (acao, credor_id, credor_nome, detalhes) VALUES (?,?,?,?)",
            ('EDITAR', cid, payload.get('nome', ''), ' | '.join(detalhes) or 'Cadastro atualizado')
        )
        conn.commit()
        row = conn.execute("SELECT * FROM credores WHERE id=?", (cid,)).fetchone()
        return jsonify(row_to_dict(row))
    except Exception as e:
        current_app.logger.error('PUT /api/credores/%s: %s', cid, e)
        return jsonify({'error': str(e)}), 500


@bp.route('/credores/<int:cid>', methods=['DELETE'])
def delete_credor(cid):
    try:
        conn = get_db()
        row = conn.execute("SELECT * FROM credores WHERE id=? AND ativo=1", (cid,)).fetchone()
        if not row:
            return jsonify({'error': 'Credor não encontrado'}), 404
        conn.execute("UPDATE credores SET ativo=0 WHERE id=?", (cid,))
        conn.execute(
            "INSERT INTO logs (acao, credor_id, credor_nome, detalhes) VALUES (?,?,?,?)",
            ('EXCLUIR', cid, row['nome'], row['departamento'] or 'Exclusão lógica')
        )
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        current_app.logger.error('DELETE /api/credores/%s: %s', cid, e)
        return jsonify({'error': str(e)}), 500


@bp.route('/credores/<int:cid>/duplicate', methods=['POST'])
def duplicate_credor(cid):
    try:
        conn = get_db()
        orig = conn.execute("SELECT * FROM credores WHERE id=? AND ativo=1", (cid,)).fetchone()
        if not orig:
            return jsonify({'error': 'Credor original não encontrado'}), 404
        novo_nome_base = f"CÓPIA – {orig['nome']}"
        novo_nome = novo_nome_base
        sufixo = 2
        while conn.execute(
            "SELECT id FROM credores WHERE ativo=1 AND UPPER(nome)=?", (novo_nome.upper(),)
        ).fetchone():
            novo_nome = f"{novo_nome_base} ({sufixo})"
            sufixo += 1
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO credores
              (nome, valor, descricao, cnpj, email, tipo_valor, solicitacao, pagamento, validade, departamento, obs)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (
            novo_nome,
            orig['valor'],
            orig['descricao'] or '',
            '',
            orig['email'] or '',
            orig['tipo_valor'] or 'FIXO',
            orig['solicitacao'] or '',
            orig['pagamento'] or '',
            orig['validade'] or '',
            orig['departamento'] or '',
            orig['obs'] or '',
        ))
        new_id = cur.lastrowid
        conn.execute(
            "INSERT INTO logs (acao, credor_id, credor_nome, detalhes) VALUES (?,?,?,?)",
            ('CRIAR', new_id, novo_nome, f'Duplicado a partir do credor #{cid} ({orig["nome"]})')
        )
        conn.commit()
        row = conn.execute("SELECT * FROM credores WHERE id=?", (new_id,)).fetchone()
        return jsonify(row_to_dict(row)), 201
    except Exception as e:
        current_app.logger.error('POST /api/credores/%s/duplicate: %s', cid, e)
        return jsonify({'error': str(e)}), 500


@bp.route('/empenhos/<int:ano>/<int:mes>', methods=['GET'])
def get_empenhos(ano, mes):
    try:
        conn = get_db()
        return jsonify(listar_empenhos_mes(conn, ano, mes, row_to_dict))
    except Exception as e:
        current_app.logger.error('GET /api/empenhos/%s/%s: %s', ano, mes, e)
        return jsonify({'error': str(e)}), 500


@bp.route('/empenhos', methods=['POST'])
def toggle_empenho():
    d = request.get_json(force=True) or {}
    credor_id = d.get('credor_id')
    ano = d.get('ano')
    mes = d.get('mes')
    if not credor_id or not ano or not mes:
        return jsonify({'error': 'credor_id, ano e mes são obrigatórios'}), 400
    try:
        conn = get_db()
        result = persistir_empenho(conn, credor_id, ano, mes, _time.strftime('%Y-%m-%d %H:%M:%S'))
        conn.commit()
        return jsonify({'ok': True, 'empenhado': result['empenhado']})
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        current_app.logger.error('POST /api/empenhos: %s', e)
        return jsonify({'error': str(e)}), 500


@bp.route('/empenhos/lote', methods=['POST'])
def empenho_lote():
    d = request.get_json(force=True) or {}
    itens = d.get('itens') or []
    if not itens:
        return jsonify({'error': 'Nenhum item informado'}), 400
    try:
        conn = get_db()
        resultados = []
        for item in itens:
            credor_id = item.get('credor_id')
            ano = item.get('ano')
            mes = item.get('mes')
            if not credor_id or not ano or not mes:
                return jsonify({'error': 'Todos os itens devem conter credor_id, ano e mes'}), 400
            resultados.append(persistir_empenho(conn, credor_id, ano, mes, _time.strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()
        return jsonify({'ok': True, 'resultados': resultados})
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        current_app.logger.error('POST /api/empenhos/lote: %s', e)
        return jsonify({'error': str(e)}), 500


@bp.route('/credores/<int:cid>/historico', methods=['GET'])
def get_historico_credor(cid):
    meses = request.args.get('meses', 6, type=int)
    meses = max(1, min(meses, 24))
    try:
        conn = get_db()
        return jsonify(listar_historico_credor(conn, cid, meses, _time.localtime()))
    except Exception as e:
        current_app.logger.error('GET /api/credores/%s/historico: %s', cid, e)
        return jsonify({'error': str(e)}), 500
