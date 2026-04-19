"""
app/routes/auth.py — Rotas de autenticação
Migrado de routes/all_routes.py com rate limiting e init_auth_hash.
"""

from flask import Blueprint, request, jsonify, session
from config import settings
import hashlib
import secrets
from app.utils.helpers import rate_limited

bp = Blueprint('auth', __name__)

_ADM_HASH = ""


def init_auth_hash(admin_password: str):
    """Inicializa hash da senha admin (chamado por app/__init__.py create_app)."""
    global _ADM_HASH
    _ADM_HASH = (
        hashlib.sha256(admin_password.encode()).hexdigest() if admin_password else ""
    )


@bp.route('/auth/adm', methods=['POST'])
def autentica_adm():
    """Autentica usuário na área administrativa com rate limiting."""
    ip = request.remote_addr or "unknown"
    if rate_limited(f"auth:{ip}", max_hits=5, window=60):
        return jsonify({'ok': False, 'error': 'Muitas tentativas. Aguarde 1 minuto.'}), 429

    data = request.get_json(silent=True) or {}
    senha = data.get('senha', '')
    senha_hash = hashlib.sha256(senha.encode()).hexdigest()

    # Se _ADM_HASH foi inicializado (via init_auth_hash), usa-o
    if _ADM_HASH:
        if senha_hash == _ADM_HASH:
            session['adm_autenticado'] = True
            session['adm_token'] = secrets.token_hex(16)
            return jsonify({'ok': True})
        return jsonify({'ok': False, 'error': 'Senha incorreta'}), 401

    # Fallback: usar settings.admin_password diretamente
    senha_admin_hash = hashlib.sha256(settings.admin_password.encode()).hexdigest()
    if senha_hash == senha_admin_hash:
        session['adm_autenticado'] = True
        session['adm_token'] = secrets.token_hex(16)
        return jsonify({'ok': True})

    return jsonify({'ok': False, 'error': 'Senha incorreta'}), 401


@bp.route('/auth/verificar', methods=['GET'])
def verificar_auth():
    """Verifica se usuário está autenticado."""
    if session.get('adm_autenticado'):
        return jsonify({'autenticado': True})
    return jsonify({'autenticado': False})


@bp.route('/auth/sair', methods=['POST'])
def logout():
    """Encerra sessão administrativa."""
    session.clear()
    return jsonify({'ok': True})
