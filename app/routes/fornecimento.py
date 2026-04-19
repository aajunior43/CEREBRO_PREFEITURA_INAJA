"""
app/routes/fornecimento.py — Supply requests (migrated from routes/all_routes.py)
"""
import json
from flask import Blueprint, request, jsonify
from app.utils.db import get_db
from app.utils.helpers import row_to_dict

bp = Blueprint("fornecimento", __name__)


def _fornecimento_parse_number(value):
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return 0.0
    text = text.replace("R$", "").replace(" ", "")
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return 0.0


def _sanitize_fornecimento_payload(data):
    payload = data or {}
    solicitante = str(payload.get("solicitante") or "").strip()
    empresa = str(payload.get("empresa") or "").strip()
    data_ref = str(payload.get("data") or "").strip()
    obs = str(payload.get("obs") or "").strip()
    raw_items = payload.get("items") or []

    if not solicitante:
        raise ValueError("Informe o solicitante.")
    if not isinstance(raw_items, list):
        raise ValueError("Lista de itens inválida.")

    items = []
    valor_total = 0.0
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            continue
        item = {
            "nome": str(raw_item.get("nome") or "").strip(),
            "desc": str(raw_item.get("desc") or "").strip(),
            "qtd": str(raw_item.get("qtd") or "").strip(),
            "preco": str(raw_item.get("preco") or "").strip(),
        }
        if not any(item.values()):
            continue
        items.append(item)
        valor_total += _fornecimento_parse_number(item["qtd"]) * _fornecimento_parse_number(
            item["preco"]
        )

    if not items:
        raise ValueError("Adicione pelo menos um item.")

    return {
        "solicitante": solicitante,
        "empresa": empresa,
        "data": data_ref,
        "obs": obs,
        "items": items,
        "total_itens": len(items),
        "valor_total": round(valor_total, 2),
    }


def _serialize_fornecimento_row(row):
    data = row_to_dict(row)
    try:
        data["items"] = json.loads(data.pop("items_json", "[]") or "[]")
    except Exception:
        data["items"] = []
        data.pop("items_json", None)
    return data


def _get_fornecimento_solicitacao(conn, solicitacao_id):
    row = conn.execute(
        "SELECT * FROM fornecimento_solicitacoes WHERE id=?",
        (solicitacao_id,),
    ).fetchone()
    return _serialize_fornecimento_row(row) if row else None


@bp.route("/fornecimento/dados", methods=["GET"])
def get_fornecimento_dados():
    try:
        conn = get_db()
        rows = conn.execute(
            "SELECT tipo,valor FROM fornecimento_dados ORDER BY valor ASC"
        ).fetchall()
        result = {"solicitantes": [], "empresas": [], "observacoes": []}
        for row in rows:
            if row["tipo"] in result:
                result[row["tipo"]].append(row["valor"])
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/fornecimento/dados", methods=["POST"])
def add_fornecimento_dado():
    try:
        data = request.get_json() or {}
        tipo = (data.get("tipo") or "").strip()
        valor = (data.get("valor") or "").strip()
        if not tipo or not valor:
            return jsonify({"error": "tipo e valor são obrigatórios"}), 400
        conn = get_db()
        conn.execute(
            "INSERT OR IGNORE INTO fornecimento_dados (tipo,valor) VALUES (?,?)",
            (tipo, valor),
        )
        conn.commit()
        return jsonify({"ok": True}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/fornecimento/dados", methods=["DELETE"])
def del_fornecimento_dado():
    try:
        data = request.get_json() or {}
        tipo = (data.get("tipo") or "").strip()
        valor = (data.get("valor") or "").strip()
        if not tipo or not valor:
            return jsonify({"error": "tipo e valor são obrigatórios"}), 400
        conn = get_db()
        conn.execute(
            "DELETE FROM fornecimento_dados WHERE tipo=? AND valor=?", (tipo, valor)
        )
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/fornecimento/solicitacoes", methods=["GET"])
def listar_fornecimento_solicitacoes():
    try:
        conn = get_db()
        q = (request.args.get("q") or "").strip()
        params = []
        where = ""
        if q:
            like = f"%{q}%"
            where = "WHERE solicitante LIKE ? OR empresa LIKE ? OR obs LIKE ?"
            params.extend([like, like, like])
        rows = conn.execute(
            f"""
            SELECT * FROM fornecimento_solicitacoes
            {where}
            ORDER BY datetime(atualizado_em) DESC, id DESC
            """,
            params,
        ).fetchall()
        return jsonify([_serialize_fornecimento_row(row) for row in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/fornecimento/solicitacoes", methods=["POST"])
def criar_fornecimento_solicitacao():
    try:
        payload = _sanitize_fornecimento_payload(request.get_json() or {})
        conn = get_db()
        cur = conn.execute(
            """
            INSERT INTO fornecimento_solicitacoes
            (solicitante, empresa, data, obs, items_json, total_itens, valor_total, criado_em, atualizado_em)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'), datetime('now', 'localtime'))
            """,
            (
                payload["solicitante"],
                payload["empresa"],
                payload["data"],
                payload["obs"],
                json.dumps(payload["items"], ensure_ascii=False),
                payload["total_itens"],
                payload["valor_total"],
            ),
        )
        conn.commit()
        saved = _get_fornecimento_solicitacao(conn, cur.lastrowid)
        return jsonify(saved), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/fornecimento/solicitacoes/<int:solicitacao_id>", methods=["PUT"])
def atualizar_fornecimento_solicitacao(solicitacao_id):
    try:
        payload = _sanitize_fornecimento_payload(request.get_json() or {})
        conn = get_db()
        cur = conn.execute(
            """
            UPDATE fornecimento_solicitacoes
            SET solicitante=?, empresa=?, data=?, obs=?, items_json=?, total_itens=?, valor_total=?,
                atualizado_em=datetime('now', 'localtime')
            WHERE id=?
            """,
            (
                payload["solicitante"],
                payload["empresa"],
                payload["data"],
                payload["obs"],
                json.dumps(payload["items"], ensure_ascii=False),
                payload["total_itens"],
                payload["valor_total"],
                solicitacao_id,
            ),
        )
        conn.commit()
        if cur.rowcount == 0:
            return jsonify({"error": "Solicitação não encontrada"}), 404
        return jsonify(_get_fornecimento_solicitacao(conn, solicitacao_id))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/fornecimento/solicitacoes/<int:solicitacao_id>/duplicate", methods=["POST"])
def duplicar_fornecimento_solicitacao(solicitacao_id):
    try:
        conn = get_db()
        original = _get_fornecimento_solicitacao(conn, solicitacao_id)
        if not original:
            return jsonify({"error": "Solicitação não encontrada"}), 404
        cur = conn.execute(
            """
            INSERT INTO fornecimento_solicitacoes
            (solicitante, empresa, data, obs, items_json, total_itens, valor_total, criado_em, atualizado_em)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'), datetime('now', 'localtime'))
            """,
            (
                original["solicitante"],
                original["empresa"],
                original["data"],
                original["obs"],
                json.dumps(original["items"], ensure_ascii=False),
                original["total_itens"],
                original["valor_total"],
            ),
        )
        conn.commit()
        return jsonify(_get_fornecimento_solicitacao(conn, cur.lastrowid)), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/fornecimento/solicitacoes/<int:solicitacao_id>", methods=["DELETE"])
def excluir_fornecimento_solicitacao(solicitacao_id):
    try:
        conn = get_db()
        cur = conn.execute(
            "DELETE FROM fornecimento_solicitacoes WHERE id=?",
            (solicitacao_id,),
        )
        conn.commit()
        if cur.rowcount == 0:
            return jsonify({"error": "Solicitação não encontrada"}), 404
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
