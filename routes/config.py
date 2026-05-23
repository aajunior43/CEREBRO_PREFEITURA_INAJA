"""Blueprint: Configurações do Sistema"""

from flask import Blueprint, request, jsonify
from config import settings
from routes._shared import get_db, row_to_dict

bp = Blueprint("config", __name__)

ALLOWED_CONFIG_KEYS = {
    "api_openrouter_key",
    "api_openrouter_modelo",
    "api_opencode_go_key",
    "api_cnpja_key",
    "api_autentique_key",
    "api_tavily_key",
}


@bp.route("/api/config", methods=["GET"])
def config_get():
    try:
        conn = get_db()
        rows = conn.execute("SELECT chave,valor FROM configuracoes").fetchall()
        return jsonify(
            {r["chave"]: r["valor"] for r in rows if r["chave"] in ALLOWED_CONFIG_KEYS}
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/config", methods=["POST"])
def config_set():
    d = request.get_json(force=True)
    try:
        conn = get_db()
        for chave, valor in d.items():
            if chave in ALLOWED_CONFIG_KEYS:
                conn.execute(
                    "INSERT INTO configuracoes (chave,valor,atualizado_em) VALUES (?,?,datetime('now','localtime')) ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor,atualizado_em=excluded.atualizado_em",
                    (chave, str(valor)),
                )
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/admin/summary", methods=["GET"])
def admin_summary():
    try:
        conn = get_db()
        rows = conn.execute(
            "SELECT chave,valor,atualizado_em FROM configuracoes WHERE chave IN (?,?,?,?,?)",
            (
                "api_openrouter_key",
                "api_openrouter_modelo",
                "api_opencode_go_key",
                "api_cnpja_key",
                "api_autentique_key",
            ),
        ).fetchall()
        cfg = {row["chave"]: row_to_dict(row) for row in rows}

        def _parse_aut_keys(value: str) -> list[str]:
            text = (value or "").replace("\r", "\n")
            raw_items = []
            for chunk in text.split("\n"):
                raw_items.extend(part.strip() for part in chunk.split(","))
            keys = [item for item in raw_items if item]
            seen = set()
            unique = []
            for item in keys:
                if item in seen:
                    continue
                seen.add(item)
                unique.append(item)
            return unique

        return jsonify(
            {
                "overview": {
                    "credores_ativos": conn.execute(
                        "SELECT COUNT(*) AS total FROM credores WHERE ativo=1"
                    ).fetchone()["total"],
                    "rpas_total": conn.execute(
                        "SELECT COUNT(*) AS total FROM rpas"
                    ).fetchone()["total"],
                    "kanban_total": conn.execute(
                        "SELECT COUNT(*) AS total FROM kanban_tasks"
                    ).fetchone()["total"],
                    "importacoes_total": conn.execute(
                        "SELECT COUNT(*) AS total FROM empenhos_importacoes"
                    ).fetchone()["total"],
                    "logs_total": conn.execute(
                        "SELECT COUNT(*) AS total FROM logs"
                    ).fetchone()["total"],
                },
                "health": {
                    "status": "ok",
                    "db": True,
                    "uptime_s": 0,
                    "cache_files": 0,
                    "cache_gzip": 0,
                },
                "config_status": {
                    "openrouter_key_configured": bool(
                        cfg.get("api_openrouter_key", {}).get("valor", "").strip()
                        or cfg.get("api_opencode_go_key", {}).get("valor", "").strip()
                    ),
                    "openrouter_model": cfg.get("api_openrouter_modelo", {}).get(
                        "valor", settings.openrouter_default_model
                    )
                    or settings.openrouter_default_model,
                    "openrouter_updated_at": cfg.get("api_openrouter_key", {}).get(
                        "atualizado_em"
                    )
                    or cfg.get("api_openrouter_modelo", {}).get("atualizado_em"),
                    "cnpja_key_configured": bool(
                        cfg.get("api_cnpja_key", {}).get("valor", "").strip()
                    ),
                    "cnpja_updated_at": cfg.get("api_cnpja_key", {}).get(
                        "atualizado_em"
                    ),
                    "autentique_key_configured": bool(
                        _parse_aut_keys(
                            cfg.get("api_autentique_key", {}).get("valor", "")
                        )
                    ),
                    "autentique_key_count": len(
                        _parse_aut_keys(
                            cfg.get("api_autentique_key", {}).get("valor", "")
                        )
                    ),
                    "autentique_updated_at": cfg.get("api_autentique_key", {}).get(
                        "atualizado_em"
                    ),
                },
                "recent_logs": [
                    row_to_dict(row)
                    for row in conn.execute(
                        "SELECT id,acao,credor_id,credor_nome,detalhes,data FROM logs ORDER BY data DESC LIMIT 8"
                    ).fetchall()
                ],
                "technical": {
                    "host": settings.host,
                    "port": settings.port,
                    "debug": settings.debug,
                    "db_path": str(settings.db_path),
                    "log_file": str(settings.log_file),
                    "base_dir": str(settings.base_dir),
                },
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500
