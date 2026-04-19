"""App utilities."""
from app.utils.db import get_db, init_db, ensure_db_indexes
from app.utils.helpers import (
    row_to_dict,
    cnpj_valido,
    normalizar_cnpj,
    parse_bool,
    slugify,
    normalize_phone_br,
)
from app.utils.pagination import paginate
from app.utils.error_handlers import register_error_handlers

__all__ = [
    "get_db",
    "init_db",
    "ensure_db_indexes",
    "row_to_dict",
    "cnpj_valido",
    "normalizar_cnpj",
    "parse_bool",
    "slugify",
    "normalize_phone_br",
    "paginate",
    "register_error_handlers",
]
