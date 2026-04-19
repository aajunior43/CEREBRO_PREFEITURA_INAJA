"""
app/__init__.py — Factory do Flask para o Sistema de Empenhos Mensais
Prefeitura Municipal de Inajá

Arquitetura:
  - app/             → Módulos modulares com blueprints
  - app/routes/      → Blueprints por domínio (credores, empenhos, etc.)
  - app/utils/       → Helpers, DB, paginação, error handlers
  - app/models/      → (Futuro: modelos SQLAlchemy)

API Versionada:
  - /api/            → API atual (compatibilidade)
  - /api/v1/         → API v1 (versionada com paginação)
"""

import os
import logging
import time
import gzip as _gzip
import hashlib
from logging.handlers import RotatingFileHandler
from pathlib import Path
from flask import Flask, g, request, Response, send_file, send_from_directory
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

    # ── Error Handlers Globais ────────────────────────────
    _register_error_handlers(app)

    # ── Registro de Blueprints ────────────────────────────
    _register_blueprints(app, url_prefix="/api")

    # ── Hooks de Request ─────────────────────────────────
    _register_hooks(app)

    # ── Rotas Estáticas e Especiais ──────────────────────
    _register_static_routes(app)

    # ── Inicializar auth hash (migrado de routes/all_routes.py) ──
    from app.routes.auth import init_auth_hash
    init_auth_hash(settings.admin_password)

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


def _register_error_handlers(app):
    """Registra handlers de erro globais."""
    from app.utils.error_handlers import register_error_handlers
    register_error_handlers(app)


def _register_blueprints(app, url_prefix="/api", version=None):
    """
    Registra todos os blueprints de rotas.
    
    Args:
        url_prefix: Prefixo da URL (/api ou /api/v1)
        version: Versão da API (None para atual, 'v1' para versionada)
    """
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
        fornecimento_bp,
        despesas_bp,
        empenho_assistente_bp,
        classificador_bp,
        logs_bp,
    )

    blueprints = [
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
        fornecimento_bp,
        despesas_bp,
        empenho_assistente_bp,
        classificador_bp,
        logs_bp,
    ]

    for bp in blueprints:
        # Para API v1, podemos adicionar middleware de versionamento
        app.register_blueprint(bp, url_prefix=url_prefix)


def _register_hooks(app):
    """Registra hooks de request (before/after)."""
    import time
    from flask import request

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
        # Injeta get_db para blueprints legacy
        try:
            from app.utils.db import get_db
            g._get_db = get_db
        except Exception:
            pass

    @app.after_request
    def add_api_headers(response):
        """Adiciona headers de API: versionamento, timing, cache."""
        started_at = getattr(g, "_request_started_at", None)
        if started_at is not None:
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            response.headers["X-Response-Time-ms"] = f"{elapsed_ms:.1f}"

            # Log de requests lentos
            if request.path.startswith("/api/") and elapsed_ms >= 250:
                app.logger.warning(
                    "Slow request %.1fms %s %s [%d]",
                    elapsed_ms,
                    request.method,
                    request.path,
                    response.status_code,
                )

        # Headers de versão da API
        if request.path.startswith("/api/v1/"):
            response.headers["API-Version"] = "v1"
            response.headers["Deprecation"] = "false"
        
        # Cache para GET requests
        if (
            request.method == "GET"
            and request.path.startswith("/api/")
            and response.status_code == 200
            and "Cache-Control" not in response.headers
        ):
            response.headers["Cache-Control"] = "public, max-age=20"

        # Compressão gzip para responses grandes
        _maybe_compress_response(app, request, response)

        return response


def _maybe_compress_response(app, request, response):
    """Comprime resposta com gzip se aceitável e > 256 bytes."""
    if (
        response.status_code < 200
        or response.status_code >= 300
        or response.direct_passthrough
        or "Content-Encoding" in response.headers
    ):
        return response

    mime = (response.content_type or "").split(";")[0].strip()
    compressible = {
        "text/html", "text/css", "text/javascript", "application/javascript",
        "application/json", "image/svg+xml", "text/plain", "text/xml",
    }

    if mime in compressible and "gzip" in request.headers.get("Accept-Encoding", ""):
        data = response.get_data()
        if len(data) > 256:
            compressed = _gzip.compress(data, compresslevel=4)
            response.set_data(compressed)
            response.headers["Content-Encoding"] = "gzip"
            response.headers["Vary"] = "Accept-Encoding"
            response.headers["Content-Length"] = len(response.get_data())


def _register_static_routes(app):
    """Registra rotas para arquivos estáticos e página inicial."""
    import os
    import hashlib
    import time as _time
    from flask import request, Response

    BASE_DIR = str(settings.base_dir)

    # Cache de arquivos em RAM
    _file_cache: dict[str, tuple[bytes, str]] = {}
    _gzip_cache: dict[str, bytes] = {}
    _etag_cache: dict[str, str] = {}

    import mimetypes as _mimetypes
    _COMPRESSIBLE = {
        "text/html", "text/css", "text/javascript", "application/javascript",
        "application/json", "image/svg+xml", "text/plain", "text/xml",
    }
    _SKIP_EXTS = {".db", ".db-shm", ".db-wal", ".pyc", ".pyo", ".log", ".bat"}
    _SKIP_DIRS = {
        "__pycache__", ".git", "DADOS", "renomer", "documentos_centro",
        "PARA IMPLEMENTAR TODO ESSE PROJETO NO PROJETO PRINCIPAL", "migrations",
    }

    def _refresh_cached_file(url: str) -> bool:
        path = os.path.join(BASE_DIR, url.lstrip("/").replace("/", os.sep))
        if not os.path.isfile(path):
            return False
        mime, _ = _mimetypes.guess_type(path)
        if mime is None:
            mime = "application/octet-stream"
        try:
            with open(path, "rb") as f:
                data = f.read()
            _file_cache[url] = (data, mime)
            _etag_cache[url] = hashlib.md5(data).hexdigest()[:16]
            
            # Pre-compress
            base_mime = (mime or "").split(";")[0].strip()
            if base_mime in _COMPRESSIBLE and len(data) > 256:
                _gzip_cache[url] = _gzip.compress(data, compresslevel=6)
            return True
        except OSError:
            return False

    def _serve_cached(url, cache_control):
        if url not in _file_cache:
            if not _refresh_cached_file(url):
                return None
        
        entry = _file_cache.get(url)
        if not entry:
            return None
        
        data, mime = entry
        etag = _etag_cache.get(url)
        
        # Check If-None-Match
        if etag and request.headers.get("If-None-Match") == f'"{etag}"':
            return Response(
                status=304,
                headers={"Cache-Control": cache_control, "ETag": f'"{etag}"'},
            )
        
        headers = {"Cache-Control": cache_control}
        if etag:
            headers["ETag"] = f'"{etag}"'
        
        # CheckAccept-Encoding
        accept_enc = request.headers.get("Accept-Encoding", "")
        gz = _gzip_cache.get(url)
        if gz and "gzip" in accept_enc:
            headers["Content-Encoding"] = "gzip"
            headers["Vary"] = "Accept-Encoding"
            headers["Content-Length"] = len(gz)
            return Response(gz, mimetype=mime, headers=headers)
        
        headers["Content-Length"] = len(data)
        return Response(data, mimetype=mime, headers=headers)

    @app.route("/")
    def index():
        resp = _serve_cached("/index.html", "no-cache, no-store, must-revalidate")
        if resp:
            return resp
        return send_file(os.path.join(BASE_DIR, "index.html"))

    @app.route("/static/<path:filename>")
    def static_cached(filename):
        url = "/static/" + filename
        ext = os.path.splitext(filename)[1].lower()
        if ext in {".js", ".css", ".html"}:
            cc = "no-cache, must-revalidate"
        elif ext in {".woff2", ".woff", ".ttf", ".otf", ".eot"}:
            cc = "public, max-age=31536000, immutable"
        else:
            cc = "public, max-age=86400"
        
        resp = _serve_cached(url, cc)
        if resp:
            return resp
        return send_from_directory(os.path.join(BASE_DIR, "static"), filename)

    @app.route("/<path:filename>")
    def catch_all(filename):
        """Serve arquivos HTML da raiz e pages/."""
        # Ignorar rotas API
        if filename.startswith("api/"):
            from flask import jsonify
            return jsonify({"error": f"Rota não encontrada: {filename}"}), 404
        
        # Tenta servir da raiz primeiro
        root_path = os.path.join(BASE_DIR, filename)
        if os.path.isfile(root_path):
            ext = os.path.splitext(filename)[1].lower()
            cc = (
                "no-cache, must-revalidate"
                if ext in {".js", ".css", ".html"}
                else "public, max-age=86400"
            )
            resp = _serve_cached(f"/{filename}", cc)
            if resp:
                return resp
            return send_file(root_path)

        # Tenta servir de pages/
        pages_path = os.path.join(BASE_DIR, "pages", filename)
        if os.path.isfile(pages_path):
            return send_file(pages_path)

        from flask import jsonify
        return jsonify({"error": f"Arquivo não encontrado: {filename}"}), 404


# Necessário para hooks
from flask import request
