"""Blueprint: Autenticação"""

import hashlib
from flask import Blueprint, request, jsonify
from routes._shared import get_db
from routes.helpers import rate_limited

bp = Blueprint("auth", __name__)

_ADM_HASH = ""


def init_auth_hash(admin_password: str):
    global _ADM_HASH
    _ADM_HASH = (
        hashlib.sha256(admin_password.encode()).hexdigest() if admin_password else ""
    )


@bp.route("/api/auth/adm", methods=["POST"])
def auth_adm():
    if not _ADM_HASH:
        return jsonify(
            {"ok": False, "error": "Senha administrativa não configurada."}
        ), 503
    ip = request.remote_addr or "unknown"
    if rate_limited(f"auth:{ip}", max_hits=5, window=60):
        return jsonify(
            {"ok": False, "error": "Muitas tentativas. Aguarde 1 minuto."}
        ), 429
    d = request.get_json(force=True) or {}
    if hashlib.sha256(d.get("senha", "").encode()).hexdigest() == _ADM_HASH:
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "Senha incorreta"}), 401


@bp.route("/api/auth/verificar", methods=["GET"])
def verificar_auth():
    return jsonify({"autenticado": True})


@bp.route("/api/auth/sair", methods=["POST"])
def logout_auth():
    return jsonify({"ok": True})


@bp.route("/api/ping", methods=["GET"])
def ping():
    return jsonify({"ok": True})


@bp.route("/api/health", methods=["GET"])
def health():
    try:
        get_db().execute("SELECT 1").fetchone()
        db_ok = True
    except Exception:
        db_ok = False
    return jsonify({"status": "ok" if db_ok else "degraded", "db": db_ok})
