"""Pagination wrapper for API responses."""
from typing import Any, Optional


def paginate(
    items: list[dict[str, Any]],
    page: int = 1,
    per_page: int = 50,
    total: Optional[int] = None,
) -> dict[str, Any]:
    """
    Retorna resposta paginada padrão.

    Se `total` for fornecido, usa-o diretamente (ignorando len(items)),
    pois os items já podem estar fatiados pelo LIMIT/OFFSET.

    Exemplo de resposta:
    {
        "items": [...],
        "total": 124,
        "page": 1,
        "per_page": 50,
        "pages": 3,
        "has_next": true,
        "has_prev": false
    }
    """
    # Se total não foi fornecido, calcula a partir dos items
    if total is None:
        total = len(items)

    total = max(0, total)
    per_page = max(1, per_page)
    pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, pages))

    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": pages,
        "has_next": page < pages,
        "has_prev": page > 1,
    }
