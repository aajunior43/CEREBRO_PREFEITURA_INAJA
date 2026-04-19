"""
server.py — Servidor Flask modular + SQLite para o Sistema de Empenhos Mensais
Prefeitura Municipal de Inajá

Para iniciar: python server.py
Ou duplo clique em iniciar.bat

Arquitetura:
  server.py          → ponto de entrada, UX terminal, cache estático, startup
  app/__init__.py    → application factory (blueprints, logging, auth)
  app/routes/        → blueprints modulares (credores, empenhos, etc.)
  services/          → lógica de negócio e integrações externas
"""

import gzip as _gzip
import hashlib
import json
import logging
import mimetypes as _mimetypes
import os
import re
import socket
import sqlite3
import sys
import threading
import time as _time
from collections import defaultdict
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import Flask, g, request, Response, send_file, send_from_directory

from config import settings

# ── UTF-8 no terminal Windows ────────────────────────────────
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── Globals ──────────────────────────────────────────────────
BASE_DIR = str(settings.base_dir)
DB_PATH = str(settings.db_path)
DATA_JS = str(settings.data_js_path)
DOCUMENTS_DIR = os.path.join(BASE_DIR, "documentos_centro")
os.makedirs(DOCUMENTS_DIR, exist_ok=True)

# ── Terminal colors ──────────────────────────────────────────
_TERM_COLORS = {
    "reset": "\033[0m",
    "dim": "\033[2m",
    "bold": "\033[1m",
    "cyan": "\033[36m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "red": "\033[31m",
    "magenta": "\033[35m",
}
try:
    if os.name == "nt":
        os.system("")
except Exception:
    pass


def _term_enabled() -> bool:
    return sys.stdout.isatty()


def _color(text: str, name: str) -> str:
    if not _term_enabled():
        return text
    return f"{_TERM_COLORS.get(name, '')}{text}{_TERM_COLORS['reset']}"


def _fmt_bytes(num: int) -> str:
    if num < 1024:
        return f"{num} B"
    if num < 1024 * 1024:
        return f"{num / 1024:.1f} KB"
    return f"{num / (1024 * 1024):.1f} MB"


def _terminal_log(kind: str, message: str, color_name: str = "cyan"):
    ts = _time.strftime("%H:%M:%S")
    print(f"{_color(f'[{ts}] [{kind}]', color_name)} {message}")


def _terminal_request_line(
    method: str, path: str, status_code: int, elapsed_ms: float, client_ip: str = ""
):
    if status_code >= 500:
        tone, icon = "red", "ERR"
    elif status_code >= 400:
        tone, icon = "yellow", "WARN"
    elif elapsed_ms >= 800:
        tone, icon = "magenta", "SLOW"
    else:
        tone, icon = "green", "OK"
    _terminal_log(
        icon,
        f"{client_ip or '-':<15} {method:<6} {status_code:<3} {elapsed_ms:>7.1f} ms  {path}",
        tone,
    )


def _terminal_section(title: str):
    print(_color("─" * 72, "dim"))
    print(_color(title, "bold"))


# ── App Factory (delega para app/__init__.py) ─────────────────
def create_app():
    """
    Cria o app Flask delegando ao factory em app/__init__.py.
    Mantém as funções de terminal e cache de arquivos estáticos do server.py.
    O factory já:
      - registrou todos os blueprints (em /api/ e /api/v1/)
      - configurou logging
      - registrou error handlers
      - chamou init_auth_hash(settings.admin_password)
    """
    # Importar factory (já configura tudo)
    from app import create_app as _create_app
    app = _create_app()

    # ── Database helpers (usam app.utils.db) ─────────────────
    from app.utils.db import get_db

    def init_db():
        conn = get_db()
        cur = conn.cursor()

        def ensure_db_indexes(cur):
            for sql in [
                "CREATE INDEX IF NOT EXISTS idx_credores_cnpj ON credores(cnpj)",
                "CREATE INDEX IF NOT EXISTS idx_credores_nome ON credores(nome)",
                "CREATE INDEX IF NOT EXISTS idx_credores_ativo ON credores(ativo)",
                "CREATE INDEX IF NOT EXISTS idx_empenhos_credor ON empenhos(credor_id)",
                "CREATE INDEX IF NOT EXISTS idx_empenhos_ano_mes ON empenhos(ano, mes)",
                "CREATE INDEX IF NOT EXISTS idx_empenhos_timestamp ON empenhos(timestamp)",
                "CREATE INDEX IF NOT EXISTS idx_logs_data_acao ON logs(data, acao)",
                "CREATE INDEX IF NOT EXISTS idx_logs_credor_data ON logs(credor_id, data)",
                "CREATE INDEX IF NOT EXISTS idx_rpas_periodo_cpf ON rpas(periodo_referencia, cpf_prestador)",
                "CREATE INDEX IF NOT EXISTS idx_rpas_criado_em ON rpas(criado_em)",
                "CREATE INDEX IF NOT EXISTS idx_docs_categoria_criado ON documentos_centro(categoria, criado_em)",
                "CREATE INDEX IF NOT EXISTS idx_docs_referencia_criado ON documentos_centro(referencia, criado_em)",
                "CREATE INDEX IF NOT EXISTS idx_kanban_status_priority ON kanban_tasks(status, priority)",
                "CREATE INDEX IF NOT EXISTS idx_kanban_categoria_vencimento ON kanban_tasks(categoria, data_vencimento)",
                "CREATE INDEX IF NOT EXISTS idx_kanban_responsavel ON kanban_tasks(responsavel)",
                "CREATE INDEX IF NOT EXISTS idx_protocolos_status_data ON protocolos(status, data_protocolo)",
                "CREATE INDEX IF NOT EXISTS idx_protocolos_tipo_direcao ON protocolos(tipo, direcao)",
                "CREATE INDEX IF NOT EXISTS idx_fornecimento_criado_em ON fornecimento_solicitacoes(criado_em)",
                "CREATE INDEX IF NOT EXISTS idx_fornecimento_solicitante ON fornecimento_solicitacoes(solicitante)",
                "CREATE INDEX IF NOT EXISTS idx_despesas_linhas_importacao_id ON despesas_linhas(importacao_id, id)",
                "CREATE INDEX IF NOT EXISTS idx_autentique_envios_status ON autentique_envios(status)",
                "CREATE INDEX IF NOT EXISTS idx_autentique_envios_documento ON autentique_envios(documento_centro_id)",
                "CREATE INDEX IF NOT EXISTS idx_empenho_hist_action_created ON empenho_assistente_historico(action, criado_em)",
                "CREATE INDEX IF NOT EXISTS idx_classificador_item ON classificador_despesa_historico(item)",
                "CREATE INDEX IF NOT EXISTS idx_classificador_codigo ON classificador_despesa_historico(codigo_completo)",
                "CREATE INDEX IF NOT EXISTS idx_classificador_created ON classificador_despesa_historico(criado_em)",
                "CREATE INDEX IF NOT EXISTS idx_protocolo_anexos_protocolo ON protocolo_anexos(protocolo_id)",
            ]:
                cur.execute(sql)

        def _seed_from_data_js(cur):
            with open(DATA_JS, encoding="utf-8") as f:
                content = f.read()
            match = re.search(r"const CREDORES_FIXOS\s*=\s*(\[[\s\S]*?\]);", content)
            if not match:
                print("ATENCAO: Nao foi possivel ler o data.js.")
                return
            data = json.loads(match.group(1))
            for c in data:
                cur.execute(
                    "INSERT INTO credores (nome,valor,descricao,cnpj,email,tipo_valor,solicitacao,pagamento,departamento,obs) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (
                        c.get("NOME", ""),
                        float(c.get("VALOR") or 0),
                        c.get("DESCRICAO", ""),
                        c.get("CNPJ", ""),
                        c.get("EMAIL", ""),
                        c.get("TIPO DE VALOR", "FIXO"),
                        str(c.get("SOLICITACAO", "")),
                        str(c.get("PAGAMENTO", "")),
                        c.get("DEPARTAMENTO", ""),
                        c.get("OBS", ""),
                    ),
                )
            print(f"  {len(data)} credores inseridos.")

        for sql in [
            "CREATE TABLE IF NOT EXISTS credores (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL, valor REAL DEFAULT 0, descricao TEXT, cnpj TEXT, email TEXT, tipo_valor TEXT DEFAULT 'FIXO', solicitacao TEXT, pagamento TEXT, validade TEXT, departamento TEXT, obs TEXT, ativo INTEGER DEFAULT 1)",
            "CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, acao TEXT NOT NULL, credor_id INTEGER, credor_nome TEXT, detalhes TEXT, data TEXT DEFAULT (datetime('now', 'localtime')))",
            "CREATE TABLE IF NOT EXISTS empenhos (id INTEGER PRIMARY KEY AUTOINCREMENT, credor_id INTEGER NOT NULL, ano INTEGER NOT NULL, mes INTEGER NOT NULL, empenhado INTEGER DEFAULT 1, timestamp TEXT, UNIQUE(credor_id, ano, mes), FOREIGN KEY(credor_id) REFERENCES credores(id))",
            "CREATE TABLE IF NOT EXISTS rpas (id INTEGER PRIMARY KEY AUTOINCREMENT, numero_rpa TEXT, nome_prestador TEXT NOT NULL, cpf_prestador TEXT, endereco_prestador TEXT, descricao_servico TEXT, periodo_referencia TEXT, carga_horaria TEXT, local_execucao TEXT, valor_bruto REAL DEFAULT 0, num_dependentes INTEGER DEFAULT 0, pensao_alimenticia REAL DEFAULT 0, inss REAL DEFAULT 0, iss REAL DEFAULT 0, deducao_dependentes REAL DEFAULT 0, base_calculo_irrf REAL DEFAULT 0, aliquota_irrf REAL DEFAULT 0, parcela_deduzir_irrf REAL DEFAULT 0, ir REAL DEFAULT 0, valor_liquido REAL DEFAULT 0, observacoes TEXT, data_emissao TEXT, criado_em TEXT DEFAULT (datetime('now', 'localtime')))",
            "CREATE TABLE IF NOT EXISTS kanban_tasks (id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT DEFAULT '', status TEXT DEFAULT 'todo', priority TEXT DEFAULT 'medium', concluido_em TEXT DEFAULT '', criado_em TEXT DEFAULT (datetime('now', 'localtime')), atualizado_em TEXT DEFAULT (datetime('now', 'localtime')))",
            "CREATE TABLE IF NOT EXISTS kanban_attachments (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL REFERENCES kanban_tasks(id) ON DELETE CASCADE, file_name TEXT NOT NULL, mime_type TEXT DEFAULT 'application/octet-stream', file_size INTEGER DEFAULT 0, content BLOB NOT NULL, criado_em TEXT DEFAULT (datetime('now','localtime')))",
            "CREATE TABLE IF NOT EXISTS fornecimento_dados (id INTEGER PRIMARY KEY AUTOINCREMENT, tipo TEXT NOT NULL, valor TEXT NOT NULL, criado_em TEXT DEFAULT (datetime('now', 'localtime')), UNIQUE(tipo, valor))",
            "CREATE TABLE IF NOT EXISTS fornecimento_solicitacoes (id INTEGER PRIMARY KEY AUTOINCREMENT, solicitante TEXT NOT NULL, empresa TEXT DEFAULT '', data TEXT DEFAULT '', obs TEXT DEFAULT '', items_json TEXT NOT NULL DEFAULT '[]', total_itens INTEGER DEFAULT 0, valor_total REAL DEFAULT 0, criado_em TEXT DEFAULT (datetime('now', 'localtime')), atualizado_em TEXT DEFAULT (datetime('now', 'localtime')))",
            "CREATE TABLE IF NOT EXISTS configuracoes (chave TEXT PRIMARY KEY, valor TEXT NOT NULL DEFAULT '', atualizado_em TEXT DEFAULT (datetime('now', 'localtime')))",
            "CREATE TABLE IF NOT EXISTS documentos_centro (id INTEGER PRIMARY KEY AUTOINCREMENT, nome_original TEXT NOT NULL, nome_arquivo TEXT NOT NULL, categoria TEXT NOT NULL, referencia TEXT DEFAULT '', descricao TEXT DEFAULT '', tamanho INTEGER DEFAULT 0, extensao TEXT DEFAULT '', caminho_relativo TEXT NOT NULL, criado_em TEXT DEFAULT (datetime('now', 'localtime')))",
            "CREATE TABLE IF NOT EXISTS autentique_envios (id INTEGER PRIMARY KEY AUTOINCREMENT, documento_centro_id INTEGER NOT NULL, autentique_document_id TEXT DEFAULT '', autentique_signature_public_id TEXT DEFAULT '', documento_nome TEXT DEFAULT '', signatario_nome TEXT NOT NULL, signatario_phone TEXT NOT NULL, status TEXT DEFAULT 'pendente', delivery_method TEXT DEFAULT 'DELIVERY_METHOD_WHATSAPP', assinatura_link TEXT DEFAULT '', webhook_evento TEXT DEFAULT '', webhook_payload TEXT DEFAULT '', assinado_doc_id INTEGER, assinado_em TEXT DEFAULT '', criado_em TEXT DEFAULT (datetime('now', 'localtime')), atualizado_em TEXT DEFAULT (datetime('now', 'localtime')))",
            "CREATE TABLE IF NOT EXISTS autentique_contatos (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL, phone TEXT NOT NULL UNIQUE, criado_em TEXT DEFAULT (datetime('now', 'localtime')), atualizado_em TEXT DEFAULT (datetime('now', 'localtime')))",
            "CREATE TABLE IF NOT EXISTS empenho_assistente_historico (id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT NOT NULL, payload_json TEXT NOT NULL DEFAULT '{}', resultado_json TEXT NOT NULL DEFAULT '{}', campos_json TEXT NOT NULL DEFAULT '{}', checklist_json TEXT NOT NULL DEFAULT '{}', descricao_base TEXT DEFAULT '', descricao_melhorada TEXT DEFAULT '', diff_json TEXT NOT NULL DEFAULT '{}', model TEXT DEFAULT '', cached INTEGER DEFAULT 0, criado_em TEXT DEFAULT (datetime('now', 'localtime')))",
            "CREATE TABLE IF NOT EXISTS classificador_despesa_historico (id INTEGER PRIMARY KEY AUTOINCREMENT, item TEXT NOT NULL, codigo_completo TEXT NOT NULL DEFAULT '', grupo TEXT DEFAULT '', modalidade TEXT DEFAULT '', elemento TEXT DEFAULT '', subelemento TEXT DEFAULT '', justificativa TEXT DEFAULT '', ponto_atencao TEXT DEFAULT '', confianca REAL DEFAULT 0.0, resultado_json TEXT NOT NULL DEFAULT '{}', model TEXT DEFAULT '', cached INTEGER DEFAULT 0, criado_em TEXT DEFAULT (datetime('now', 'localtime')))",
        ]:
            cur.execute(sql)

        count = cur.execute("SELECT COUNT(*) FROM credores").fetchone()[0]
        if count == 0 and os.path.exists(DATA_JS):
            print("Populando banco com dados do data.js...")
            _seed_from_data_js(cur)
        ensure_db_indexes(cur)
        conn.commit()

    def migrate_db():
        conn = get_db()
        cur = conn.cursor()

        def ensure_db_indexes(cur):
            for sql in [
                "CREATE INDEX IF NOT EXISTS idx_credores_cnpj ON credores(cnpj)",
                "CREATE INDEX IF NOT EXISTS idx_credores_nome ON credores(nome)",
                "CREATE INDEX IF NOT EXISTS idx_credores_ativo ON credores(ativo)",
                "CREATE INDEX IF NOT EXISTS idx_empenhos_credor ON empenhos(credor_id)",
                "CREATE INDEX IF NOT EXISTS idx_empenhos_ano_mes ON empenhos(ano, mes)",
                "CREATE INDEX IF NOT EXISTS idx_empenhos_timestamp ON empenhos(timestamp)",
                "CREATE INDEX IF NOT EXISTS idx_logs_data_acao ON logs(data, acao)",
                "CREATE INDEX IF NOT EXISTS idx_logs_credor_data ON logs(credor_id, data)",
                "CREATE INDEX IF NOT EXISTS idx_rpas_periodo_cpf ON rpas(periodo_referencia, cpf_prestador)",
                "CREATE INDEX IF NOT EXISTS idx_rpas_criado_em ON rpas(criado_em)",
                "CREATE INDEX IF NOT EXISTS idx_docs_categoria_criado ON documentos_centro(categoria, criado_em)",
                "CREATE INDEX IF NOT EXISTS idx_docs_referencia_criado ON documentos_centro(referencia, criado_em)",
                "CREATE INDEX IF NOT EXISTS idx_kanban_status_priority ON kanban_tasks(status, priority)",
                "CREATE INDEX IF NOT EXISTS idx_kanban_categoria_vencimento ON kanban_tasks(categoria, data_vencimento)",
                "CREATE INDEX IF NOT EXISTS idx_kanban_responsavel ON kanban_tasks(responsavel)",
                "CREATE INDEX IF NOT EXISTS idx_protocolos_status_data ON protocolos(status, data_protocolo)",
                "CREATE INDEX IF NOT EXISTS idx_protocolos_tipo_direcao ON protocolos(tipo, direcao)",
                "CREATE INDEX IF NOT EXISTS idx_fornecimento_criado_em ON fornecimento_solicitacoes(criado_em)",
                "CREATE INDEX IF NOT EXISTS idx_fornecimento_solicitante ON fornecimento_solicitacoes(solicitante)",
                "CREATE INDEX IF NOT EXISTS idx_despesas_linhas_importacao_id ON despesas_linhas(importacao_id, id)",
                "CREATE INDEX IF NOT EXISTS idx_autentique_envios_status ON autentique_envios(status)",
                "CREATE INDEX IF NOT EXISTS idx_autentique_envios_documento ON autentique_envios(documento_centro_id)",
                "CREATE INDEX IF NOT EXISTS idx_empenho_hist_action_created ON empenho_assistente_historico(action, criado_em)",
                "CREATE INDEX IF NOT EXISTS idx_classificador_item ON classificador_despesa_historico(item)",
                "CREATE INDEX IF NOT EXISTS idx_classificador_codigo ON classificador_despesa_historico(codigo_completo)",
                "CREATE INDEX IF NOT EXISTS idx_classificador_created ON classificador_despesa_historico(criado_em)",
                "CREATE INDEX IF NOT EXISTS idx_protocolo_anexos_protocolo ON protocolo_anexos(protocolo_id)",
            ]:
                cur.execute(sql)

        for sql in [
            "CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, acao TEXT NOT NULL, credor_id INTEGER, credor_nome TEXT, detalhes TEXT, data TEXT DEFAULT (datetime('now', 'localtime')))",
            "CREATE TABLE IF NOT EXISTS rpas (id INTEGER PRIMARY KEY AUTOINCREMENT, numero_rpa TEXT, nome_prestador TEXT NOT NULL, cpf_prestador TEXT, endereco_prestador TEXT, descricao_servico TEXT, periodo_referencia TEXT, carga_horaria TEXT, local_execucao TEXT, valor_bruto REAL DEFAULT 0, num_dependentes INTEGER DEFAULT 0, pensao_alimenticia REAL DEFAULT 0, inss REAL DEFAULT 0, iss REAL DEFAULT 0, deducao_dependentes REAL DEFAULT 0, base_calculo_irrf REAL DEFAULT 0, aliquota_irrf REAL DEFAULT 0, parcela_deduzir_irrf REAL DEFAULT 0, ir REAL DEFAULT 0, valor_liquido REAL DEFAULT 0, observacoes TEXT, data_emissao TEXT, criado_em TEXT DEFAULT (datetime('now', 'localtime')))",
            "CREATE TABLE IF NOT EXISTS empenhos_importacoes (id INTEGER PRIMARY KEY AUTOINCREMENT, periodo TEXT NOT NULL, descricao TEXT, arquivo TEXT, total_rows INTEGER DEFAULT 0, importado_em TEXT)",
            "CREATE TABLE IF NOT EXISTS empenhos_linhas (id INTEGER PRIMARY KEY AUTOINCREMENT, importacao_id INTEGER NOT NULL REFERENCES empenhos_importacoes(id) ON DELETE CASCADE, dados TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS documentos_centro (id INTEGER PRIMARY KEY AUTOINCREMENT, nome_original TEXT NOT NULL, nome_arquivo TEXT NOT NULL, categoria TEXT NOT NULL, referencia TEXT DEFAULT '', descricao TEXT DEFAULT '', tamanho INTEGER DEFAULT 0, extensao TEXT DEFAULT '', caminho_relativo TEXT NOT NULL, criado_em TEXT DEFAULT (datetime('now', 'localtime')))",
            "CREATE TABLE IF NOT EXISTS autentique_envios (id INTEGER PRIMARY KEY AUTOINCREMENT, documento_centro_id INTEGER NOT NULL, autentique_document_id TEXT DEFAULT '', autentique_signature_public_id TEXT DEFAULT '', documento_nome TEXT DEFAULT '', signatario_nome TEXT NOT NULL, signatario_phone TEXT NOT NULL, status TEXT DEFAULT 'pendente', delivery_method TEXT DEFAULT 'DELIVERY_METHOD_WHATSAPP', assinatura_link TEXT DEFAULT '', webhook_evento TEXT DEFAULT '', webhook_payload TEXT DEFAULT '', assinado_doc_id INTEGER, assinado_em TEXT DEFAULT '', criado_em TEXT DEFAULT (datetime('now', 'localtime')), atualizado_em TEXT DEFAULT (datetime('now', 'localtime')))",
            "CREATE TABLE IF NOT EXISTS autentique_contatos (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL, phone TEXT NOT NULL UNIQUE, criado_em TEXT DEFAULT (datetime('now', 'localtime')), atualizado_em TEXT DEFAULT (datetime('now', 'localtime')))",
            "CREATE TABLE IF NOT EXISTS despesas_importacoes (id INTEGER PRIMARY KEY AUTOINCREMENT, periodo TEXT NOT NULL, descricao TEXT, arquivo TEXT, total_rows INTEGER DEFAULT 0, colunas TEXT, importado_em TEXT)",
            "CREATE TABLE IF NOT EXISTS despesas_linhas (id INTEGER PRIMARY KEY AUTOINCREMENT, importacao_id INTEGER NOT NULL REFERENCES despesas_importacoes(id) ON DELETE CASCADE, dados TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS kanban_attachments (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL REFERENCES kanban_tasks(id) ON DELETE CASCADE, file_name TEXT NOT NULL, mime_type TEXT DEFAULT 'application/octet-stream', file_size INTEGER DEFAULT 0, content BLOB NOT NULL, criado_em TEXT DEFAULT (datetime('now','localtime')))",
            "CREATE TABLE IF NOT EXISTS prazos (id INTEGER PRIMARY KEY AUTOINCREMENT, titulo TEXT NOT NULL, descricao TEXT DEFAULT '', data_limite TEXT NOT NULL, categoria TEXT DEFAULT 'geral', resolvido INTEGER DEFAULT 0, criado_em TEXT DEFAULT (datetime('now','localtime')))",
            "CREATE TABLE IF NOT EXISTS protocolos (id INTEGER PRIMARY KEY AUTOINCREMENT, numero TEXT NOT NULL UNIQUE, tipo TEXT NOT NULL, direcao TEXT DEFAULT 'recebido', origem_destino TEXT DEFAULT '', assunto TEXT NOT NULL, data_protocolo TEXT NOT NULL, prazo_resposta TEXT DEFAULT '', status TEXT DEFAULT 'recebido', observacoes TEXT DEFAULT '', doc_id INTEGER, criado_em TEXT DEFAULT (datetime('now', 'localtime')))",
            "CREATE TABLE IF NOT EXISTS protocolo_anexos (id INTEGER PRIMARY KEY AUTOINCREMENT, protocolo_id INTEGER NOT NULL REFERENCES protocolos(id) ON DELETE CASCADE, file_name TEXT NOT NULL, mime_type TEXT DEFAULT 'application/octet-stream', file_size INTEGER DEFAULT 0, content BLOB NOT NULL, criado_em TEXT DEFAULT (datetime('now','localtime')))",
            "CREATE TABLE IF NOT EXISTS fornecimento_solicitacoes (id INTEGER PRIMARY KEY AUTOINCREMENT, solicitante TEXT NOT NULL, empresa TEXT DEFAULT '', data TEXT DEFAULT '', obs TEXT DEFAULT '', items_json TEXT NOT NULL DEFAULT '[]', total_itens INTEGER DEFAULT 0, valor_total REAL DEFAULT 0, criado_em TEXT DEFAULT (datetime('now', 'localtime')), atualizado_em TEXT DEFAULT (datetime('now', 'localtime')))",
        ]:
            cur.execute(sql)
        ensure_db_indexes(cur)
        for alter in [
            "ALTER TABLE credores ADD COLUMN atualizado_em TEXT DEFAULT (datetime('now','localtime'))",
            "ALTER TABLE kanban_tasks ADD COLUMN categoria TEXT DEFAULT ''",
            "ALTER TABLE kanban_tasks ADD COLUMN data_vencimento TEXT DEFAULT ''",
            "ALTER TABLE kanban_tasks ADD COLUMN responsavel TEXT DEFAULT ''",
            "ALTER TABLE kanban_tasks ADD COLUMN concluido_em TEXT DEFAULT ''",
        ]:
            try:
                cur.execute(alter)
            except Exception:
                pass
        conn.commit()

    # ── Static file cache (brotli+gzip do server.py original) ─
    _COMPRESSIBLE = {
        "text/html", "text/css", "text/javascript", "application/javascript",
        "application/json", "image/svg+xml", "text/plain", "text/xml",
    }
    _SKIP_EXTS = {".db", ".db-shm", ".db-wal", ".pyc", ".pyo", ".log", ".bat"}
    _SKIP_DIRS = {
        "__pycache__", ".git", "DADOS", "renomer", "documentos_centro",
        "PARA IMPLEMENTAR TODO ESSE PROJETO NO PROJETO PRINCIPAL",
    }

    _file_cache: dict = {}
    _gzip_cache: dict = {}
    _brotli_cache: dict = {}
    _etag_cache: dict = {}
    _file_mtime_cache: dict = {}

    try:
        import brotli as _brotli
        _BROTLI_OK = True
    except ImportError:
        _BROTLI_OK = False

    def _url_to_static_path(url: str) -> str:
        rel = (url or "/").lstrip("/")
        if not rel:
            rel = "index.html"
        return os.path.join(BASE_DIR, rel.replace("/", os.sep))

    def _refresh_cached_file(url: str) -> bool:
        path = _url_to_static_path(url)
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
            _file_mtime_cache[url] = os.path.getmtime(path)
            _gzip_cache.pop(url, None)
            _brotli_cache.pop(url, None)
            base_mime = (mime or "").split(";")[0].strip()
            if base_mime in _COMPRESSIBLE and len(data) > 256:
                _gzip_cache[url] = _gzip.compress(data, compresslevel=6)
                if _BROTLI_OK:
                    _brotli_cache[url] = _brotli.compress(data, quality=4)
            return True
        except OSError:
            return False

    def _refresh_debug_cached_file(url: str) -> bool:
        path = _url_to_static_path(url)
        if not os.path.isfile(path):
            return False
        try:
            current_mtime = os.path.getmtime(path)
        except OSError:
            return False
        cached_mtime = _file_mtime_cache.get(url)
        if url not in _file_cache or cached_mtime != current_mtime:
            return _refresh_cached_file(url)
        return True

    def _serve_cached(url, cache_control):
        if settings.debug:
            if not _refresh_debug_cached_file(url):
                return None
        elif url not in _file_cache:
            return None
        entry = _file_cache.get(url)
        if not entry:
            return None
        data, mime = entry
        etag = _etag_cache.get(url)
        if etag and request.headers.get("If-None-Match") == f'"{etag}"':
            return Response(
                status=304,
                headers={"Cache-Control": cache_control, "ETag": f'"{etag}"'},
            )
        headers = {"Cache-Control": cache_control}
        if etag:
            headers["ETag"] = f'"{etag}"'
        accept_enc = request.headers.get("Accept-Encoding", "")
        br = _brotli_cache.get(url)
        gz = _gzip_cache.get(url)
        if br and "br" in accept_enc:
            headers["Content-Encoding"] = "br"
            headers["Vary"] = "Accept-Encoding"
            headers["Content-Length"] = len(br)
            return Response(br, mimetype=mime, headers=headers)
        if gz and "gzip" in accept_enc:
            headers["Content-Encoding"] = "gzip"
            headers["Vary"] = "Accept-Encoding"
            headers["Content-Length"] = len(gz)
            return Response(gz, mimetype=mime, headers=headers)
        headers["Content-Length"] = len(data)
        return Response(data, mimetype=mime, headers=headers)

    def _preload_static_files():
        count, total_kb = 0, 0
        started_at = _time.perf_counter()
        _terminal_log("BOOT", "Pre-carregando arquivos estaticos em RAM...", "cyan")
        for root, dirs, files in os.walk(BASE_DIR):
            dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
            rel_root = os.path.relpath(root, BASE_DIR).replace("\\", "/")
            if rel_root == ".":
                rel_root = ""
            for fname in files:
                ext = os.path.splitext(fname)[1].lower()
                if ext in _SKIP_EXTS:
                    continue
                fpath = os.path.join(root, fname)
                url = ("/" + rel_root + "/" + fname).replace("//", "/")
                try:
                    if _refresh_cached_file(url):
                        data, _ = _file_cache[url]
                        count += 1
                        total_kb += len(data) // 1024
                except OSError:
                    pass
        elapsed_ms = (_time.perf_counter() - started_at) * 1000
        _terminal_log(
            "CACHE",
            f"{count} arquivos carregados em RAM ({_fmt_bytes(total_kb * 1024)})",
            "green",
        )
        enc_count = max(len(_brotli_cache), len(_gzip_cache))
        enc_name = "brotli+gzip" if _BROTLI_OK else "gzip"
        _terminal_log(
            "GZIP",
            f"{enc_count} arquivos com versao {enc_name} prontos em {elapsed_ms:.1f} ms",
            "green",
        )

    return app, _preload_static_files, init_db, migrate_db


# ── MAIN ─────────────────────────────────────────────────────
if __name__ == "__main__":
    import socket

    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    boot_started_at = _time.perf_counter()

    app, _preload_static_files, init_db, migrate_db = create_app()

    _terminal_section("Sistema de Empenhos - Prefeitura Municipal de Inaja")
    _terminal_log("BOOT", "Iniciando servidor Flask...", "cyan")
    init_db()
    _terminal_log("BOOT", "Estrutura principal do banco verificada", "green")
    migrate_db()
    _terminal_log("BOOT", "Migracoes do banco aplicadas", "green")
    _preload_static_files()

    try:
        from werkzeug.serving import WSGIRequestHandler
        WSGIRequestHandler.address_string = lambda self: self.client_address[0]
        WSGIRequestHandler.protocol_version = "HTTP/1.1"
    except Exception:
        pass

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except OSError:
        local_ip = "127.0.0.1"

    boot_elapsed_ms = (_time.perf_counter() - boot_started_at) * 1000
    _terminal_section("Servidor pronto")
    _terminal_log("LOCAL", f"http://localhost:{settings.port}", "green")
    _terminal_log("REDE", f"http://{local_ip}:{settings.port}", "green")
    _terminal_log(
        "INFO",
        f"Modo debug: {'ligado' if settings.debug else 'desligado'} | Host: {settings.host}",
        "yellow",
    )
    _terminal_log("TIME", f"Startup concluido em {boot_elapsed_ms:.1f} ms", "magenta")
    _terminal_log(
        "INFO", "Para encerrar: feche esta janela ou pressione Ctrl+C", "cyan"
    )

    app.run(
        host=settings.host,
        port=settings.port,
        debug=settings.debug,
        use_reloader=settings.reloader,
        threaded=True,
    )