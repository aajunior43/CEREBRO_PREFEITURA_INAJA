from flask import Blueprint, request, jsonify, session, send_file
import os
from routes._shared import get_db, row_to_dict
from config import settings

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


@bp.route("/api/logs/server-log", methods=["GET"])
def get_server_log():
    if session.get("usuario_nivel") != "admin":
        return jsonify({"error": "Não autorizado"}), 403

    log_path = str(settings.log_file)
    if not os.path.exists(log_path):
        return jsonify({"error": "Arquivo de log não encontrado"}), 404

    if request.args.get("download") == "1":
        return send_file(log_path, as_attachment=True, download_name="server.log")

    lines_to_read = min(int(request.args.get("lines", 500)), 2000)
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
            last_lines = lines[-lines_to_read:]
            return jsonify({
                "lines": last_lines,
                "total_lines": len(lines)
            })
    except Exception as e:
        return jsonify({"error": f"Erro ao ler log: {str(e)}"}), 500

