"""
app/routes/logs.py — Audit log endpoint (migrated from routes/all_routes.py)
"""
from flask import Blueprint, request, jsonify
from app.utils.db import get_db
from app.utils.helpers import row_to_dict

bp = Blueprint("logs", __name__)


@bp.route("/logs", methods=["GET"])
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
