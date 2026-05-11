"""
app/routes/auth.py — Rotas de autenticação
"""

from flask import Blueprint, request, jsonify, session, make_response
from config import settings
import hashlib
import secrets

bp = Blueprint('auth', __name__)


@bp.route('/auth/adm', methods=['POST'])
def autentica_adm():
    """Autentica usuário na área administrativa."""
    data = request.get_json(silent=True) or {}
    senha = data.get('senha', '')
    
    # Hash da senha fornecida
    senha_hash = hashlib.sha256(senha.encode()).hexdigest()
    senha_admin_hash = hashlib.sha256(settings.admin_password.encode()).hexdigest()
    
    if senha_hash == senha_admin_hash:
        session['adm_autenticado'] = True
        session['adm_token'] = secrets.token_hex(16)
        return jsonify({'ok': True, 'mensagem': 'Autenticação bem-sucedida'})
    
    return jsonify({'error': 'Senha inválida'}), 401


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
