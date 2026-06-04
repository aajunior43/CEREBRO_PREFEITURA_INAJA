"""
Blueprint: Credores
CRUD, lixeira, restaurar, duplicar
"""

import json
import time as _time

from flask import Blueprint, request, jsonify, session

from routes.helpers import (
    credor_payload,
    buscar_credor_duplicado,
    montar_filtros_credores,
    parse_bool,
)
from routes._shared import registrar_auditoria, require_login

bp = Blueprint("credores", __name__)

# Summary cache (TTL 60s)
_summary_cache = {"data": None, "timestamp": 0}


def get_db():
    from flask import g

    return g._get_db()


def row_to_dict(row):
    return dict(row)


def _should_include_summary(args) -> bool:
    raw = (args.get("include_summary") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _invalidate_summary_cache():
    _summary_cache["data"] = None
    _summary_cache["timestamp"] = 0


def _get_summary(conn):
    now = _time.time()
    if _summary_cache["data"] is not None and (now - _summary_cache["timestamp"]) < 60:
        return _summary_cache["data"]
    resumo = conn.execute(
        """SELECT COUNT(*) AS total,
            SUM(CASE WHEN COALESCE(tipo_valor,'FIXO') LIKE 'VAR%' THEN 1 ELSE 0 END) AS variaveis,
            SUM(CASE WHEN COALESCE(tipo_valor,'FIXO') NOT LIKE 'VAR%' THEN 1 ELSE 0 END) AS fixos,
            SUM(CASE WHEN COALESCE(cnpj,'')='' THEN 1 ELSE 0 END) AS sem_cnpj,
            SUM(CASE WHEN COALESCE(email,'')='' THEN 1 ELSE 0 END) AS sem_email,
            SUM(CASE WHEN COALESCE(validade,'')<>'' AND date(validade)<date('now','localtime') THEN 1 ELSE 0 END) AS vencidos,
            SUM(CASE WHEN COALESCE(validade,'')<>'' AND date(validade)>=date('now','localtime') AND date(validade)<=date('now','localtime','+30 day') THEN 1 ELSE 0 END) AS vencendo_30
        FROM credores WHERE ativo=1"""
    ).fetchone()
    _summary_cache["data"] = row_to_dict(resumo)
    _summary_cache["timestamp"] = now
    return _summary_cache["data"]


@bp.route("/api/credores", methods=["GET"])
@require_login
def get_credores():
    try:
        limit = max(1, min(request.args.get("limit", 50, type=int), 1000))
        offset = request.args.get("offset", 0, type=int)
        sort_col = (request.args.get("sort_col") or "departamento").strip().lower()
        sort_dir = (request.args.get("sort_dir") or "asc").strip().lower()
        if sort_dir not in {"asc", "desc"}:
            sort_dir = "asc"
        sort_map = {
            "nome": "nome",
            "departamento": "departamento",
            "valor": "valor",
            "tipo": "tipo_valor",
            "tipo_valor": "tipo_valor",
            "validade": "validade",
        }
        order_by = sort_map.get(sort_col, "departamento")
        clauses, params = montar_filtros_credores(request.args)
        where_sql = " AND ".join(clauses)
        conn = get_db()
        total = conn.execute(
            f"SELECT COUNT(*) AS total FROM credores WHERE {where_sql}", params
        ).fetchone()["total"]
        rows = conn.execute(
            f"SELECT * FROM credores WHERE {where_sql} ORDER BY {order_by} {sort_dir}, nome ASC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
        itens = [row_to_dict(r) for r in rows]
        resumo = None
        if _should_include_summary(request.args):
            resumo = _get_summary(conn)
        return jsonify(
            {
                "items": itens,
                "total": total,
                "limit": limit,
                "offset": offset,
                "summary": row_to_dict(resumo) if resumo else None,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/credores", methods=["POST"])
@require_login
def add_credor():
    data = request.get_json(force=True) or {}
    payload, errors = credor_payload(data, partial=False)
    if errors:
        return jsonify({"error": errors[0], "errors": errors}), 400
    try:
        conn = get_db()
        duplicado, msg = buscar_credor_duplicado(conn, payload.get("cnpj", ""))
        if duplicado:
            return jsonify({"error": msg, "duplicado_id": duplicado["id"]}), 409
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO credores (nome,valor,descricao,cnpj,email,tipo_valor,solicitacao,pagamento,validade,departamento,obs) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                payload.get("nome", ""),
                payload.get("valor", 0),
                payload.get("descricao", ""),
                payload.get("cnpj", ""),
                payload.get("email", ""),
                payload.get("tipo_valor", "FIXO"),
                payload.get("solicitacao", ""),
                payload.get("pagamento", ""),
                payload.get("validade", ""),
                payload.get("departamento", ""),
                payload.get("obs", ""),
            ),
        )
        new_id = cur.lastrowid
        conn.execute(
            "INSERT INTO logs (acao,credor_id,credor_nome,credor_departamento,credor_cnpj,detalhes) VALUES (?,?,?,?,?,?)",
            (
                "CRIAR",
                new_id,
                payload.get("nome", ""),
                payload.get("departamento", ""),
                payload.get("cnpj", ""),
                payload.get("departamento", "") or "Cadastro de credor",
            ),
        )
        row = conn.execute("SELECT * FROM credores WHERE id=?", (new_id,)).fetchone()
        registrar_auditoria(conn, "credores", new_id, "CRIAR", None, row_to_dict(row))
        conn.commit()
        _invalidate_summary_cache()
        return jsonify(row_to_dict(row)), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/credores/<int:cid>", methods=["PUT"])
@require_login
def update_credor(cid):
    from routes.helpers import normalizar_cnpj

    data = request.get_json(force=True) or {}
    payload, errors = credor_payload(data, partial=False)
    if errors:
        return jsonify({"error": errors[0], "errors": errors}), 400
    try:
        conn = get_db()
        atual = conn.execute(
            "SELECT * FROM credores WHERE id=? AND ativo=1", (cid,)
        ).fetchone()
        if not atual:
            return jsonify({"error": "Credor não encontrado"}), 404
        cnpj_atual = normalizar_cnpj(atual["cnpj"] or "")
        cnpj_alterado = payload.get("cnpj", "") != cnpj_atual
        cnpj_verificar = payload.get("cnpj", "") if cnpj_alterado else ""
        duplicado, msg = buscar_credor_duplicado(conn, cnpj_verificar, ignore_id=cid)
        if duplicado:
            return jsonify({"error": msg, "duplicado_id": duplicado["id"]}), 409
        conn.execute(
            "UPDATE credores SET nome=?,valor=?,descricao=?,cnpj=?,email=?,tipo_valor=?,solicitacao=?,pagamento=?,validade=?,departamento=?,obs=? WHERE id=?",
            (
                payload.get("nome", ""),
                payload.get("valor", 0),
                payload.get("descricao", ""),
                payload.get("cnpj", ""),
                payload.get("email", ""),
                payload.get("tipo_valor", "FIXO"),
                payload.get("solicitacao", ""),
                payload.get("pagamento", ""),
                payload.get("validade", ""),
                payload.get("departamento", ""),
                payload.get("obs", ""),
                cid,
            ),
        )
        detalhes = []
        mudancas = {}
        for key, label in (
            ("nome", "Nome"),
            ("departamento", "Departamento"),
            ("valor", "Valor"),
            ("tipo_valor", "Tipo"),
            ("validade", "Validade"),
            ("cnpj", "CNPJ"),
            ("email", "E-mail"),
        ):
            anterior = atual[key] if key in atual.keys() else ""
            novo = payload.get(key, "")
            if str(anterior or "") != str(novo or ""):
                detalhes.append(f"{label}: {anterior or '—'} → {novo or '—'}")
                mudancas[key] = {"antes": str(anterior or ""), "depois": str(novo or "")}
        conn.execute(
            "INSERT INTO logs (acao,credor_id,credor_nome,credor_departamento,credor_cnpj,detalhes,mudancas_json) VALUES (?,?,?,?,?,?,?)",
            (
                "EDITAR",
                cid,
                payload.get("nome", ""),
                payload.get("departamento", ""),
                payload.get("cnpj", ""),
                " | ".join(detalhes) or "Cadastro atualizado",
                json.dumps(mudancas, ensure_ascii=False),
            ),
        )
        row = conn.execute("SELECT * FROM credores WHERE id=?", (cid,)).fetchone()
        registrar_auditoria(conn, "credores", cid, "EDITAR", row_to_dict(atual), row_to_dict(row))
        conn.commit()
        _invalidate_summary_cache()
        return jsonify(row_to_dict(row))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/credores/<int:cid>", methods=["DELETE"])
@require_login
def delete_credor(cid):
    if session.get("usuario_nivel") != "adm":
        return jsonify({"error": "Apenas administradores podem excluir credores."}), 403
    try:
        conn = get_db()
        row = conn.execute(
            "SELECT * FROM credores WHERE id=? AND ativo=1", (cid,)
        ).fetchone()
        if not row:
            return jsonify({"error": "Credor não encontrado"}), 404
        conn.execute("UPDATE credores SET ativo=0 WHERE id=?", (cid,))
        _invalidate_summary_cache()
        conn.execute(
            "INSERT INTO logs (acao,credor_id,credor_nome,credor_departamento,credor_cnpj,detalhes) VALUES (?,?,?,?,?,?)",
            ("EXCLUIR", cid, row["nome"], row["departamento"] or "", row["cnpj"] or "", row["departamento"] or "Exclusão lógica"),
        )
        registrar_auditoria(conn, "credores", cid, "EXCLUIR", row_to_dict(row), None)
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/credores/deletados", methods=["GET"])
@require_login
def listar_deletados():
    try:
        conn = get_db()
        rows = conn.execute(
            "SELECT * FROM credores WHERE ativo=0 ORDER BY atualizado_em DESC"
        ).fetchall()
        return jsonify([row_to_dict(r) for r in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/credores/<int:cid>/restaurar", methods=["PUT"])
@require_login
def restaurar_credor(cid):
    try:
        conn = get_db()
        row = conn.execute(
            "SELECT * FROM credores WHERE id=? AND ativo=0", (cid,)
        ).fetchone()
        if not row:
            return jsonify({"error": "Credor não encontrado na lixeira"}), 404
        conflito = conn.execute(
            "SELECT id FROM credores WHERE ativo=1 AND UPPER(nome)=UPPER(?)",
            (row["nome"],),
        ).fetchone()
        if conflito:
            return jsonify(
                {"error": f'Já existe um credor ativo com o nome "{row["nome"]}"'}
            ), 409
        conn.execute(
            "UPDATE credores SET ativo=1, atualizado_em=datetime('now','localtime') WHERE id=?",
            (cid,),
        )
        _invalidate_summary_cache()
        conn.execute(
            "INSERT INTO logs (acao,credor_id,credor_nome,credor_departamento,credor_cnpj,detalhes) VALUES (?,?,?,?,?,?)",
            (
                "RESTAURAR",
                cid,
                row["nome"],
                row["departamento"] or "",
                row["cnpj"] or "",
                row["departamento"] or "Restaurado da lixeira",
            ),
        )
        registrar_auditoria(conn, "credores", cid, "RESTAURAR", {"ativo": 0}, {"ativo": 1})
        conn.commit()
        row = conn.execute("SELECT * FROM credores WHERE id=?", (cid,)).fetchone()
        return jsonify({"ok": True, "credor": row_to_dict(row)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/credores/<int:cid>/duplicate", methods=["POST"])
@require_login
def duplicate_credor(cid):
    try:
        conn = get_db()
        orig = conn.execute(
            "SELECT * FROM credores WHERE id=? AND ativo=1", (cid,)
        ).fetchone()
        if not orig:
            return jsonify({"error": "Credor original não encontrado"}), 404
        novo_nome_base = f"CÓPIA – {orig['nome']}"
        novo_nome = novo_nome_base
        sufixo = 2
        while conn.execute(
            "SELECT id FROM credores WHERE ativo=1 AND UPPER(nome)=?",
            (novo_nome.upper(),),
        ).fetchone():
            novo_nome = f"{novo_nome_base} ({sufixo})"
            sufixo += 1
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO credores (nome,valor,descricao,cnpj,email,tipo_valor,solicitacao,pagamento,validade,departamento,obs) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                novo_nome,
                orig["valor"],
                orig["descricao"] or "",
                "",
                orig["email"] or "",
                orig["tipo_valor"] or "FIXO",
                orig["solicitacao"] or "",
                orig["pagamento"] or "",
                orig["validade"] or "",
                orig["departamento"] or "",
                orig["obs"] or "",
            ),
        )
        new_id = cur.lastrowid
        conn.execute(
            "INSERT INTO logs (acao,credor_id,credor_nome,credor_departamento,credor_cnpj,detalhes) VALUES (?,?,?,?,?,?)",
            (
                "CRIAR",
                new_id,
                novo_nome,
                orig["departamento"] or "",
                orig["cnpj"] or "",
                f"Duplicado a partir do credor #{cid} ({orig['nome']})",
            ),
        )
        row = conn.execute("SELECT * FROM credores WHERE id=?", (new_id,)).fetchone()
        registrar_auditoria(conn, "credores", new_id, "DUPLICAR",
                            {"origem_id": cid, "origem_nome": orig["nome"]}, row_to_dict(row))
        conn.commit()
        _invalidate_summary_cache()
        return jsonify(row_to_dict(row)), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

