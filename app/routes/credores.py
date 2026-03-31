"""
app/routes/credores.py — Rotas de gestão de credores
"""

import re
from flask import Blueprint, request, jsonify
from app.utils.db import get_db
from app.utils.helpers import row_to_dict, normalizar_cnpj

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


@bp.route('/credores', methods=['GET'])
def listar_credores():
    """Lista credores com filtros opcionais."""
    try:
        conn = get_db()
        search = (request.args.get('search') or '').strip()
        departamento = (request.args.get('departamento') or '').strip().upper()
        tipo = (request.args.get('tipo') or '').strip().upper()
        
        clauses = ["ativo=1"]
        params = []
        
        if search:
            like = f'%{search.lower()}%'
            clauses.append("""(
                LOWER(nome) LIKE ? OR LOWER(COALESCE(descricao, '')) LIKE ?
            )""")
            params.extend([like, like])
        
        if departamento:
            clauses.append("COALESCE(departamento, '')=?")
            params.append(departamento)
        
        if tipo:
            clauses.append("COALESCE(tipo_valor, 'FIXO')=?")
            params.append('VARIÁVEL' if tipo == 'VARIAVEL' else tipo)
        
        where = ' AND '.join(clauses)
        rows = conn.execute(
            f"SELECT * FROM credores WHERE {where} ORDER BY nome ASC",
            params
        ).fetchall()
        
        return jsonify([row_to_dict(r) for r in rows])
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
        
        # Verificar duplicidade
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
        
        # Log
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
        
        # Verificar se existe
        existing = conn.execute("SELECT * FROM credores WHERE id=?", (cid,)).fetchone()
        if not existing:
            return jsonify({'error': 'Credor não encontrado'}), 404
        
        # Verificar duplicidade de CNPJ
        if payload.get('cnpj') and payload['cnpj'] != existing['cnpj']:
            dup, msg = _buscar_credor_duplicado(conn, payload['cnpj'], ignore_id=cid)
            if dup:
                return jsonify({'error': msg}), 409
        
        # Atualizar
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
        
        # Log
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
        
        # Log
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
