"""Blueprint: Fornecimento"""

from flask import Blueprint, request, jsonify

bp = Blueprint("fornecimento", __name__)


def get_db():
    from flask import g
    return g._get_db()


@bp.route("/api/fornecimento/dados", methods=["GET"])
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


@bp.route("/api/fornecimento/dados", methods=["POST"])
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


@bp.route("/api/fornecimento/dados", methods=["DELETE"])
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
