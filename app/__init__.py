"""
app/__init__.py — Factory do Flask para o Sistema de Empenhos Mensais
Prefeitura Municipal de Inajá
"""

import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, g
from config import settings


def create_app(test_config=None):
    """Application factory para criar o app Flask."""

    app = Flask(__name__, static_folder=str(settings.base_dir))

    # Configurações básicas
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-key-inaja")
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB max upload

    if test_config is not None:
        app.config.update(test_config)

    # ── Logging ───────────────────────────────────────────
    _setup_logging(app)

    # ── Registro de Blueprints ───────────────────────────
    _register_blueprints(app)

    # ── Hooks de Request ─────────────────────────────────
    _register_hooks(app)

    # ── Rotas Estáticas e Especiais ──────────────────────
    _register_static_routes(app)

    return app


def _setup_logging(app):
    """Configura logging rotativo."""
    log_dir = str(settings.log_dir)
    os.makedirs(log_dir, exist_ok=True)

    handler = RotatingFileHandler(
        str(settings.log_file),
        maxBytes=2 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    handler.setLevel(logging.WARNING)
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)


def _register_blueprints(app):
    """Registra todos os blueprints de rotas."""
    from app.routes import (
        credores_bp,
        empenhos_bp,
        rpas_bp,
        kanban_bp,
        documentos_bp,
        autentique_bp,
        prazos_bp,
        protocolo_bp,
        extratos_bp,
        ia_bp,
        cnpj_bp,
        pdf_bp,
        auth_bp,
        config_bp,
    )

    app.register_blueprint(credores_bp, url_prefix="/api")
    app.register_blueprint(empenhos_bp, url_prefix="/api")
    app.register_blueprint(rpas_bp, url_prefix="/api")
    app.register_blueprint(kanban_bp, url_prefix="/api")
    app.register_blueprint(documentos_bp, url_prefix="/api")
    app.register_blueprint(autentique_bp, url_prefix="/api")
    app.register_blueprint(prazos_bp, url_prefix="/api")
    app.register_blueprint(protocolo_bp, url_prefix="/api")
    app.register_blueprint(extratos_bp, url_prefix="/api")
    app.register_blueprint(ia_bp, url_prefix="/api")
    app.register_blueprint(cnpj_bp, url_prefix="/api")
    app.register_blueprint(pdf_bp, url_prefix="/api")
    app.register_blueprint(auth_bp, url_prefix="/api")
    app.register_blueprint(config_bp, url_prefix="/api")


def _register_hooks(app):
    """Registra hooks de request (before/after)."""
    from flask import request
    import time

    @app.before_request
    def mark_request_start():
        g._request_started_at = time.perf_counter()
        g._request_path = request.path
        g._request_full_path = request.full_path.rstrip("?")
        g._request_ip = (
            request.headers.get("X-Forwarded-For", request.remote_addr or "-")
            .split(",")[0]
            .strip()
        )

    @app.after_request
    def compress_response(response):
        started_at = getattr(g, "_request_started_at", None)
        if started_at is not None:
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            response.headers["X-Response-Time-ms"] = f"{elapsed_ms:.1f}"

            if request.path.startswith("/api/") and elapsed_ms >= 250:
                app.logger.warning(
                    "Slow request %.1fms %s %s",
                    elapsed_ms,
                    request.method,
                    request.path,
                )

        if (
            request.method == "GET"
            and request.path.startswith("/api/")
            and response.status_code == 200
            and "Cache-Control" not in response.headers
        ):
            response.headers["Cache-Control"] = "public, max-age=20"

        return response


def _register_static_routes(app):
    """Registra rotas para arquivos estáticos e página inicial."""
    from flask import send_file, request, Response
    import os
    import hashlib
    import gzip as _gzip
    import time as _time

    BASE_DIR = str(settings.base_dir)

    # Cache de arquivos em RAM
    _file_cache = {}
    _etag_cache = {}

    def _refresh_cached_file(url):
        path = os.path.join(BASE_DIR, url.lstrip("/").replace("/", os.sep))
        if not os.path.isfile(path):
            return False
        try:
            with open(path, "rb") as f:
                data = f.read()
            _file_cache[url] = data
            _etag_cache[url] = hashlib.md5(data).hexdigest()[:16]
            return True
        except OSError:
            return False

    @app.route("/")
    def index():
        return send_file(os.path.join(BASE_DIR, "index.html"))

    @app.route("/static/<path:filename>")
    def static_files(filename):
        return send_file(os.path.join(BASE_DIR, "static", filename))

    @app.route("/<path:filename>")
    def catch_all(filename):
        """Serve arquivos HTML da raiz e pages/."""
        # Tenta servir da raiz primeiro
        root_path = os.path.join(BASE_DIR, filename)
        if os.path.isfile(root_path):
            return send_file(root_path)

        # Tenta servir de pages/
        pages_path = os.path.join(BASE_DIR, "pages", filename)
        if os.path.isfile(pages_path):
            return send_file(pages_path)

        return f"Arquivo não encontrado: {filename}", 404


# Import necessário para os hooks
from flask import request
