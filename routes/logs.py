"""Blueprint: Logs do Sistema"""

from flask import Blueprint, request, jsonify
from routes._shared import get_db, row_to_dict

bp = Blueprint("logs", __name__)


@bp.route("/api/logs", methods=["GET"])
def get_logs():
    try:
        conn = get_db()
        limit = min(int(request.args.get("limit", 50)), 200)
        offset = int(request.args.get("offset", 0))
        acao = (request.args.get("acao") or "").strip()
        if acao:
            total = conn.execute(
                "SELECT COUNT(*) FROM logs WHERE acao=?", (acao,)
            ).fetchone()[0]
            rows = conn.execute(
                "SELECT id,acao,credor_id,credor_nome,detalhes,data FROM logs WHERE acao=? ORDER BY data DESC LIMIT ? OFFSET ?",
                (acao, limit, offset),
            ).fetchall()
        else:
            total = conn.execute("SELECT COUNT(*) FROM logs").fetchone()[0]
            rows = conn.execute(
                "SELECT id,acao,credor_id,credor_nome,detalhes,data FROM logs ORDER BY data DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return jsonify({"logs": [row_to_dict(r) for r in rows], "total": total})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
