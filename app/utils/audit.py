"""
app/utils/audit.py — Logging de auditoria para operacoes criticas
"""

import logging
from flask import request

# Logger dedicado para auditoria
audit_logger = logging.getLogger("audit")


def log_audit(action: str, resource: str, resource_id=None, details: str = "", conn=None):
    """Registra auditoria no banco (tabela logs) e no logger.

    Args:
        action: CREATE, UPDATE, DELETE, LOGIN, etc.
        resource: Nome do recurso (credores, kanban, auth, etc.)
        resource_id: ID do recurso afetado (opcional)
        details: Descricao detalhada da operacao
        conn: Conexao DB para registro na tabela logs (opcional)
    """
    ip = getattr(request, 'remote_addr', 'system') or 'system'
    user_agent = getattr(request, 'user_agent', '')
    if hasattr(user_agent, 'string'):
        user_agent = user_agent.string
    user_agent = str(user_agent)[:200] if user_agent else ''

    message = f"[{action}] {resource}"
    if resource_id is not None:
        message += f" (id={resource_id})"
    if details:
        message += f" — {details}"

    # Logger de auditoria (arquivo)
    audit_logger.info("%s | IP=%s | UA=%s", message, ip, user_agent)

    # Registro na tabela logs (se conexao fornecida)
    if conn and action in {"CREATE", "UPDATE", "DELETE"}:
        try:
            conn.execute(
                """INSERT INTO logs (acao, credor_id, credor_nome, detalhes)
                   VALUES (?, ?, ?, ?)""",
                (action, resource_id, resource, message)
            )
            conn.commit()
        except Exception:
            # Falha no log nao deve quebrar a operacao principal
            audit_logger.error("Falha ao registrar log no DB: %s", message)


def log_auth_audit(success: bool, ip: str = "", details: str = ""):
    """Registra tentativa de autenticacao."""
    action = "LOGIN_SUCCESS" if success else "LOGIN_FAILED"
    message = f"[{action}] Autenticacao administrativa"
    if ip:
        message += f" | IP={ip}"
    if details:
        message += f" — {details}"

    if success:
        audit_logger.info(message)
    else:
        audit_logger.warning(message)
