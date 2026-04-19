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
    
    Exemplo de resposta:
    {
        "data": [...],
        "pagination": {
            "page": 1,
            "per_page": 50,
            "total": 124,
            "pages": 3,
            "has_next": true,
            "has_prev": false
        }
    }
    """
    if total is None:
        total = len(items)
    
    pages = max(1, (total + per_page - 1) // per_page)
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": pages,
        "has_next": page < pages,
        "has_prev": page > 1,
    }
