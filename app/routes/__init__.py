"""app/routes/__init__.py — Registro de blueprints"""

from app.routes.credores import bp as credores_bp
from app.routes.empenhos import bp as empenhos_bp
from app.routes.rpas import bp as rpas_bp
from app.routes.kanban import bp as kanban_bp
from app.routes.documentos import bp as documentos_bp
from app.routes.autentique import bp as autentique_bp
from app.routes.prazos import bp as prazos_bp
from app.routes.protocolo import bp as protocolo_bp
from app.routes.extratos import bp as extratos_bp
from app.routes.ia import bp as ia_bp
from app.routes.cnpj import bp as cnpj_bp
from app.routes.pdf import bp as pdf_bp
from app.routes.auth import bp as auth_bp
from app.routes.config import bp as config_bp
from app.routes.fornecimento import bp as fornecimento_bp
from app.routes.despesas import bp as despesas_bp
from app.routes.empenho_assistente import bp as empenho_assistente_bp
from app.routes.classificador import bp as classificador_bp
from app.routes.logs import bp as logs_bp

__all__ = [
    'credores_bp',
    'empenhos_bp',
    'rpas_bp',
    'kanban_bp',
    'documentos_bp',
    'autentique_bp',
    'prazos_bp',
    'protocolo_bp',
    'extratos_bp',
    'ia_bp',
    'cnpj_bp',
    'pdf_bp',
    'auth_bp',
    'config_bp',
    'fornecimento_bp',
    'despesas_bp',
    'empenho_assistente_bp',
    'classificador_bp',
    'logs_bp',
]
