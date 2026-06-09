"""
Compatibilidade: re-exporta todos os blueprints dos módulos extraídos.
Este arquivo pode ser removido no futuro — importe diretamente dos módulos individuais.
"""

from routes._shared import (
    get_db,
    row_to_dict,
    _get_openrouter_config,
    _build_ai_service,
    _build_ai_facade,
    _extract_json_block,
)

from routes.prazos import bp as bp_prazos
from routes.protocolos import bp as bp_protocolos
from routes.rpas import bp as bp_rpas
from routes.fornecimento import bp as bp_fornecimento
from routes.pdf import bp as bp_pdf
from routes.despesas import bp as bp_despesas
from routes.cnpj import bp as bp_cnpj
from routes.ia import bp as bp_ia
from routes.config import bp as bp_config
from routes.logs import bp as bp_logs
from routes.auth import bp as bp_auth, init_auth_hash
from routes.extratos import bp as bp_extratos
from routes.empenho_assistente import bp as bp_empenho_assistente
from routes.classificador import bp as bp_classificador
