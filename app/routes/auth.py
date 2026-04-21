""" 
app/routes/auth.py — Rotas de autenticação
Migrado de routes/all_routes.py com rate limiting e init_auth_hash.
"""

from flask import Blueprint, request, jsonify, session
import hashlib
import hmac
import secrets
from app.utils.helpers import rate_limited
from app.utils.audit import log_auth_audit

bp = Blueprint('auth', __name__)

# Usuários permitidos: {usuario: hash_senha}
ALLOWED_USERS = {
    "aleksandro": hashlib.sha256("19991020".encode()).hexdigest(),
    "luanaaiara": hashlib.sha256("luanaaiara".encode()).hexdigest(),
}


def _safe_compare(a: str, b: str) -> bool:
    """Comparação segura contra timing attacks."""
    return hmac.compare_digest(a.encode(), b.encode())


@bp.route('/auth/adm', methods=['POST'])
def autentica_adm():
    """Autentica usuário na área administrativa com rate limiting."""
    ip = request.remote_addr or "unknown"
    if rate_limited(f"auth:{ip}", max_hits=5, window=60):
        return jsonify({'ok': False, 'error': 'Muitas tentativas. Aguarde 1 minuto.'}), 429

    data = request.get_json(silent=True) or {}
    usuario = data.get('usuario', '').strip().lower()
    senha = data.get('senha', '')
    senha_hash = hashlib.sha256(senha.encode()).hexdigest()

    # Verifica se usuário existe e senha está correta
    if usuario in ALLOWED_USERS:
        if _safe_compare(senha_hash, ALLOWED_USERS[usuario]):
            session['adm_autenticado'] = True
            session['adm_token'] = secrets.token_hex(16)
            session['usuario_logado'] = usuario
            session.permanent = True
            log_auth_audit(success=True, ip=ip, details=f'Usuário: {usuario}')
            return jsonify({'ok': True, 'usuario': usuario})
        log_auth_audit(success=False, ip=ip, details=f'Usuário: {usuario} - Senha incorreta')
        return jsonify({'ok': False, 'error': 'Usuário ou senha incorretos'}), 401

    log_auth_audit(success=False, ip=ip, details=f'Usuário não encontrado: {usuario}')
    return jsonify({'ok': False, 'error': 'Usuário ou senha incorretos'}), 401


@bp.route('/auth/verificar', methods=['GET'])
def verificar_auth():
    """Verifica se usuário está autenticado."""
    if session.get('adm_autenticado'):
        return jsonify({
            'autenticado': True,
            'usuario': session.get('usuario_logado', 'admin')
        })
    return jsonify({'autenticado': False})


@bp.route('/auth/sair', methods=['POST'])
def logout():
    """Encerra sessão administrativa."""
    session.clear()
    return jsonify({'ok': True})
