"""
server.py — Servidor Flask modular + SQLite para o Sistema de Empenhos Mensais
Prefeitura Municipal de Inajá

Para iniciar: python server.py
Ou duplo clique em iniciar.bat

Arquitetura:
  server.py          → app factory, DB, cache estático, middlewares, startup
  routes/credores.py → CRUD credores, lixeira
  routes/empenhos.py → empenhos mensais, histórico
  routes/kanban.py   → tarefas, IA, anexos
  routes/documentos.py → centro de documentos, autentique
  routes/all_routes.py → prazos, protocolos, RPAs, PDF, CNPJ, IA, config, logs, auth, etc.
  services/          → lógica de negócio e integrações externas
"""

# gevent monkey-patch must be first — before any stdlib imports — to enable SSE streaming
try:
    from gevent import monkey as _gmonkey
    _gmonkey.patch_all(thread=True, socket=True)
    _GEVENT_AVAILABLE = True
except ImportError:
    _GEVENT_AVAILABLE = False

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

from flask import Flask, g, request, Response, jsonify, send_file, send_from_directory

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

# ── Startup & Environment Logging ────────────────────────────
_startup_logger = None

def _setup_startup_logger():
    global _startup_logger
    if _startup_logger is not None:
        return _startup_logger
    
    import platform
    log_dir = settings.log_dir
    os.makedirs(str(log_dir), exist_ok=True)
    startup_log_path = log_dir / "startup.log"
    
    logger = logging.getLogger("startup")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    
    if not logger.handlers:
        handler = RotatingFileHandler(
            str(startup_log_path),
            maxBytes=1024 * 1024,
            backupCount=2,
            encoding="utf-8"
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        )
        logger.addHandler(handler)
        
        # Log system info on initial configuration
        logger.info("=" * 80)
        logger.info("INICIANDO BOOT DO SERVIDOR CÉREBRO MUNICIPAL")
        logger.info("=" * 80)
        logger.info(f"Python: {sys.version}")
        logger.info(f"S.O.: {platform.platform()}")
        logger.info(f"Diretório Base: {BASE_DIR}")
        logger.info(f"Host: {settings.host} | Porta: {settings.port} | Debug: {settings.debug}")
        
        def check_env(var):
            val = os.environ.get(var)
            if val:
                return f"CONFIGURADO (tamanho: {len(val)})"
            return "NÃO CONFIGURADO"
            
        logger.info(f"Chave ADM_PASSWORD: {'CONFIGURADA' if settings.admin_password else 'NÃO CONFIGURADA (usando padrão)'}")
        logger.info(f"Chave OPENROUTER_API_KEY: {check_env('OPENROUTER_API_KEY')}")
        logger.info(f"Chave OPENCODE_GO_API_KEY: {check_env('OPENCODE_GO_API_KEY')}")
        logger.info(f"Chave TAVILY_API_KEY: {check_env('TAVILY_API_KEY')}")
        logger.info(f"gevent disponível: {_GEVENT_AVAILABLE}")
        
    _startup_logger = logger
    return logger

def _log_startup(message: str, level: str = "INFO"):
    logger = _setup_startup_logger()
    if level == "INFO":
        logger.info(message)
    elif level == "WARNING":
        logger.warning(message)
    elif level == "ERROR":
        logger.error(message)
    elif level == "CRITICAL":
        logger.critical(message)

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


# ── App Factory ──────────────────────────────────────────────
def create_app() -> Flask:
    app = Flask(__name__, static_folder=BASE_DIR)

    # ── Session ─────────────────────────────────
    if settings.admin_password:
        _base = settings.admin_password
        import hashlib as _hl
        app.secret_key = _hl.sha256(f"inaja::sessao::{_base}".encode()).hexdigest()
    else:
        # Fallback dinâmico seguro persistido localmente para evitar chaves previsíveis
        secret_file = settings.base_dir / ".session_secret"
        if secret_file.exists():
            try:
                app.secret_key = secret_file.read_text(encoding="utf-8").strip()
            except Exception:
                import secrets
                app.secret_key = secrets.token_hex(32)
        else:
            import secrets
            generated_key = secrets.token_hex(32)
            try:
                secret_file.write_text(generated_key, encoding="utf-8")
            except Exception:
                pass
            app.secret_key = generated_key

    app.config["SESSION_COOKIE_NAME"] = "inaja_sid"
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["MAX_CONTENT_LENGTH"] = 15 * 1024 * 1024  # 15 MB — cobre uploads de anexos do Mural

# ── Logging ──────────────────────────────────────────────
    os.makedirs(str(settings.log_dir), exist_ok=True)
    _log_handler = RotatingFileHandler(
        str(settings.log_file),
        maxBytes=2 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    _log_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    )
    _log_handler.setLevel(logging.WARNING)
    app.logger.addHandler(_log_handler)

    # ── Database ─────────────────────────────────────────────
    _db_local = threading.local()

    def get_db():
        db = getattr(_db_local, "conn", None)
        if db is None:
            db = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10.0)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA synchronous=NORMAL")
            db.execute("PRAGMA cache_size=-8000")
            db.execute("PRAGMA temp_store=MEMORY")
            db.execute("PRAGMA mmap_size=0")
            db.execute("PRAGMA auto_vacuum=INCREMENTAL")
            _db_local.conn = db
        return db

    def _get_db_for_g():
        return get_db()

    @app.teardown_appcontext
    def close_db(exception):
        conn = getattr(_db_local, "conn", None)
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
            _db_local.conn = None

    def ensure_db_indexes(cur):
        for sql in [
            "CREATE INDEX IF NOT EXISTS idx_empenhos_credor ON empenhos(credor_id)",
            "CREATE INDEX IF NOT EXISTS idx_empenhos_ano_mes ON empenhos(ano, mes)",
            "CREATE INDEX IF NOT EXISTS idx_empenhos_ano_mes_empenhado ON empenhos(ano, mes, empenhado)",
            "CREATE INDEX IF NOT EXISTS idx_empenhos_credor_ano_mes ON empenhos(credor_id, ano, mes)",
            "CREATE INDEX IF NOT EXISTS idx_credores_departamento ON credores(departamento)",
            "CREATE INDEX IF NOT EXISTS idx_credores_nome ON credores(nome)",
            "CREATE INDEX IF NOT EXISTS idx_credores_ativo ON credores(ativo)",
            "CREATE INDEX IF NOT EXISTS idx_credores_tipo_valor ON credores(tipo_valor)",
            "CREATE INDEX IF NOT EXISTS idx_credores_validade ON credores(validade)",
            "CREATE INDEX IF NOT EXISTS idx_credores_cnpj ON credores(cnpj)",
            "CREATE INDEX IF NOT EXISTS idx_credores_email ON credores(email)",
            "CREATE INDEX IF NOT EXISTS idx_logs_acao ON logs(acao)",
            "CREATE INDEX IF NOT EXISTS idx_logs_data ON logs(data)",
            "CREATE INDEX IF NOT EXISTS idx_rpas_cpf ON rpas(cpf_prestador)",
            "CREATE INDEX IF NOT EXISTS idx_rpas_periodo ON rpas(periodo_referencia)",
            "CREATE INDEX IF NOT EXISTS idx_rpas_data_emissao ON rpas(data_emissao)",
            "CREATE INDEX IF NOT EXISTS idx_docs_categoria ON documentos_centro(categoria)",
            "CREATE INDEX IF NOT EXISTS idx_docs_referencia ON documentos_centro(referencia)",
            "CREATE INDEX IF NOT EXISTS idx_docs_criado_em ON documentos_centro(criado_em)",
            "CREATE INDEX IF NOT EXISTS idx_docs_categoria_ref ON documentos_centro(categoria, referencia)",
            "CREATE INDEX IF NOT EXISTS idx_empenho_hist_action ON empenho_assistente_historico(action)",
            "CREATE INDEX IF NOT EXISTS idx_empenho_hist_created ON empenho_assistente_historico(criado_em)",
            "CREATE INDEX IF NOT EXISTS idx_despesas_importacoes_periodo ON despesas_importacoes(periodo)",
            "CREATE INDEX IF NOT EXISTS idx_despesas_linhas_importacao ON despesas_linhas(importacao_id)",
            "CREATE INDEX IF NOT EXISTS idx_empenhos_importacoes_periodo ON empenhos_importacoes(periodo)",
            "CREATE INDEX IF NOT EXISTS idx_empenhos_linhas_importacao ON empenhos_linhas(importacao_id)",
            "CREATE INDEX IF NOT EXISTS idx_kanban_attach_task ON kanban_attachments(task_id)",
            "CREATE INDEX IF NOT EXISTS idx_mural_attach_recado ON mural_anexos(recado_id)",
            "CREATE INDEX IF NOT EXISTS idx_mural_comentarios_recado ON mural_comentarios(recado_id)",
            "CREATE INDEX IF NOT EXISTS idx_mural_recados_credor ON mural_recados(credor_id)",
            "CREATE INDEX IF NOT EXISTS idx_kanban_tasks_dates ON kanban_tasks(atualizado_em, criado_em)",
            "CREATE INDEX IF NOT EXISTS idx_protocolos_status ON protocolos(status)",
            "CREATE INDEX IF NOT EXISTS idx_protocolos_tipo ON protocolos(tipo)",
            "CREATE INDEX IF NOT EXISTS idx_protocolos_direcao ON protocolos(direcao)",
            "CREATE INDEX IF NOT EXISTS idx_prazos_filtro ON prazos(resolvido, data_limite)",
            "CREATE INDEX IF NOT EXISTS idx_prazos_data_limite ON prazos(data_limite)",
            "CREATE INDEX IF NOT EXISTS idx_classificador_despesa_item ON classificador_despesa_historico(item)",
            "CREATE INDEX IF NOT EXISTS idx_classificador_despesa_created ON classificador_despesa_historico(criado_em)",
            "CREATE INDEX IF NOT EXISTS idx_autentique_envios_signature ON autentique_envios(autentique_signature_public_id)",
            "CREATE INDEX IF NOT EXISTS idx_autentique_envios_doc_id ON autentique_envios(autentique_document_id)",
            "CREATE INDEX IF NOT EXISTS idx_protocolo_anexos_protocolo ON protocolo_anexos(protocolo_id)",
            "CREATE INDEX IF NOT EXISTS idx_credores_ativo_depto_nome ON credores(ativo, departamento, nome)",
            "CREATE INDEX IF NOT EXISTS idx_credores_ativo_tipo ON credores(ativo, tipo_valor)",
            "CREATE INDEX IF NOT EXISTS idx_kanban_attach_task_order ON kanban_attachments(task_id, criado_em, id)",
            "CREATE INDEX IF NOT EXISTS idx_logs_acao_data ON logs(acao, data DESC)",
            "CREATE INDEX IF NOT EXISTS idx_rpas_criado_em ON rpas(criado_em)",
            "CREATE INDEX IF NOT EXISTS idx_credores_nome_upper ON credores(UPPER(nome))",
            "CREATE INDEX IF NOT EXISTS idx_autentique_contatos_nome ON autentique_contatos(nome COLLATE NOCASE)",
            "CREATE INDEX IF NOT EXISTS idx_usuarios_login ON usuarios(login)",
            "CREATE INDEX IF NOT EXISTS idx_usuarios_nivel ON usuarios(nivel)",
            "CREATE INDEX IF NOT EXISTS idx_audit_trail_tabela ON audit_trail(tabela)",
            "CREATE INDEX IF NOT EXISTS idx_audit_trail_operacao ON audit_trail(operacao)",
            "CREATE INDEX IF NOT EXISTS idx_audit_trail_timestamp ON audit_trail(timestamp DESC)",
            "CREATE INDEX IF NOT EXISTS idx_audit_trail_tabela_registro ON audit_trail(tabela, registro_id)",
        ]:
            try:
                cur.execute(sql)
            except Exception:
                pass

    def migrate_db():
        _log_startup("Iniciando migrações do banco de dados (migrate_db)...")
        conn = get_db()
        cur = conn.cursor()
        
        # 1. Base Table Creation (without _contents tables)
        _log_startup("Verificando/criando tabelas base...")
        for sql in [
            "CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, acao TEXT NOT NULL, credor_id INTEGER, credor_nome TEXT, credor_departamento TEXT DEFAULT '', credor_cnpj TEXT DEFAULT '', detalhes TEXT, data TEXT DEFAULT (datetime('now', 'localtime')), FOREIGN KEY(credor_id) REFERENCES credores(id) ON DELETE SET NULL)",
            "CREATE TABLE IF NOT EXISTS rpas (id INTEGER PRIMARY KEY AUTOINCREMENT, numero_rpa TEXT, nome_prestador TEXT NOT NULL, cpf_prestador TEXT NOT NULL DEFAULT '', endereco_prestador TEXT, descricao_servico TEXT, periodo_referencia TEXT, carga_horaria TEXT, local_execucao TEXT, valor_bruto REAL DEFAULT 0 CHECK (valor_bruto >= 0), num_dependentes INTEGER DEFAULT 0, pensao_alimenticia REAL DEFAULT 0, inss REAL DEFAULT 0, iss REAL DEFAULT 0, deducao_dependentes REAL DEFAULT 0, base_calculo_irrf REAL DEFAULT 0, aliquota_irrf REAL DEFAULT 0, parcela_deduzir_irrf REAL DEFAULT 0, ir REAL DEFAULT 0, valor_liquido REAL DEFAULT 0 CHECK (valor_liquido >= 0), observacoes TEXT, data_emissao TEXT, criado_em TEXT DEFAULT (datetime('now', 'localtime')))",
            "CREATE TABLE IF NOT EXISTS empenhos_importacoes (id INTEGER PRIMARY KEY AUTOINCREMENT, periodo TEXT NOT NULL, descricao TEXT, arquivo TEXT, total_rows INTEGER DEFAULT 0, importado_em TEXT)",
            "CREATE TABLE IF NOT EXISTS empenhos_linhas (id INTEGER PRIMARY KEY AUTOINCREMENT, importacao_id INTEGER NOT NULL REFERENCES empenhos_importacoes(id) ON DELETE CASCADE, dados TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS documentos_centro (id INTEGER PRIMARY KEY AUTOINCREMENT, nome_original TEXT NOT NULL, nome_arquivo TEXT NOT NULL, categoria TEXT NOT NULL, referencia TEXT DEFAULT '', descricao TEXT DEFAULT '', tamanho INTEGER DEFAULT 0, extensao TEXT DEFAULT '', caminho_relativo TEXT NOT NULL, criado_em TEXT DEFAULT (datetime('now', 'localtime')))",
            "CREATE TABLE IF NOT EXISTS autentique_envios (id INTEGER PRIMARY KEY AUTOINCREMENT, documento_centro_id INTEGER NOT NULL, autentique_document_id TEXT DEFAULT '', autentique_signature_public_id TEXT DEFAULT '', documento_nome TEXT DEFAULT '', signatario_nome TEXT NOT NULL, signatario_phone TEXT NOT NULL, status TEXT DEFAULT 'pendente', delivery_method TEXT DEFAULT 'DELIVERY_METHOD_WHATSAPP', assinatura_link TEXT DEFAULT '', webhook_evento TEXT DEFAULT '', webhook_payload TEXT DEFAULT '', assinado_doc_id INTEGER, assinado_em TEXT DEFAULT '', criado_em TEXT DEFAULT (datetime('now', 'localtime')), atualizado_em TEXT DEFAULT (datetime('now', 'localtime')), FOREIGN KEY(documento_centro_id) REFERENCES documentos_centro(id) ON DELETE CASCADE, FOREIGN KEY(assinado_doc_id) REFERENCES documentos_centro(id) ON DELETE SET NULL)",
            "CREATE TABLE IF NOT EXISTS autentique_contatos (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL, phone TEXT NOT NULL UNIQUE, criado_em TEXT DEFAULT (datetime('now', 'localtime')), atualizado_em TEXT DEFAULT (datetime('now', 'localtime')))",
            "CREATE TABLE IF NOT EXISTS despesas_importacoes (id INTEGER PRIMARY KEY AUTOINCREMENT, periodo TEXT NOT NULL, descricao TEXT, arquivo TEXT, total_rows INTEGER DEFAULT 0, colunas TEXT, importado_em TEXT)",
            "CREATE TABLE IF NOT EXISTS despesas_linhas (id INTEGER PRIMARY KEY AUTOINCREMENT, importacao_id INTEGER NOT NULL REFERENCES despesas_importacoes(id) ON DELETE CASCADE, dados TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS kanban_attachments (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL REFERENCES kanban_tasks(id) ON DELETE CASCADE, file_name TEXT NOT NULL, mime_type TEXT DEFAULT 'application/octet-stream', file_size INTEGER DEFAULT 0, criado_em TEXT DEFAULT (datetime('now','localtime')))",
            "CREATE TABLE IF NOT EXISTS prazos (id INTEGER PRIMARY KEY AUTOINCREMENT, titulo TEXT NOT NULL, descricao TEXT DEFAULT '', data_limite TEXT NOT NULL CHECK (data_limite GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'), categoria TEXT DEFAULT 'geral', resolvido INTEGER DEFAULT 0 CHECK (resolvido IN (0,1)), criado_em TEXT DEFAULT (datetime('now','localtime')))",
            "CREATE TABLE IF NOT EXISTS protocolos (id INTEGER PRIMARY KEY AUTOINCREMENT, numero TEXT NOT NULL UNIQUE, tipo TEXT NOT NULL, direcao TEXT DEFAULT 'recebido' CHECK (direcao IN ('recebido','enviado')), origem_destino TEXT DEFAULT '', assunto TEXT NOT NULL, data_protocolo TEXT NOT NULL CHECK (data_protocolo GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'), prazo_resposta TEXT DEFAULT '', status TEXT DEFAULT 'recebido', observacoes TEXT DEFAULT '', doc_id INTEGER, criado_em TEXT DEFAULT (datetime('now','localtime')), FOREIGN KEY(doc_id) REFERENCES documentos_centro(id) ON DELETE SET NULL)",
            "CREATE TABLE IF NOT EXISTS protocolo_anexos (id INTEGER PRIMARY KEY AUTOINCREMENT, protocolo_id INTEGER NOT NULL REFERENCES protocolos(id) ON DELETE CASCADE, file_name TEXT NOT NULL, mime_type TEXT DEFAULT 'application/octet-stream', file_size INTEGER DEFAULT 0, criado_em TEXT DEFAULT (datetime('now','localtime')))", "CREATE TABLE IF NOT EXISTS mural_recados (id INTEGER PRIMARY KEY AUTOINCREMENT, titulo TEXT NOT NULL, conteudo TEXT NOT NULL, autor TEXT NOT NULL, destinatario TEXT DEFAULT 'Todos', prioridade TEXT DEFAULT 'media', categoria TEXT DEFAULT 'tarefa', status TEXT DEFAULT 'a_fazer', cor TEXT DEFAULT 'yellow', concluido_por TEXT DEFAULT '', concluido_em TEXT DEFAULT '', valor REAL DEFAULT 0.0, credor_id INTEGER REFERENCES credores(id) ON DELETE SET NULL, criado_em TEXT DEFAULT (datetime('now', 'localtime')), atualizado_em TEXT DEFAULT (datetime('now', 'localtime')))",
            "CREATE TABLE IF NOT EXISTS mural_anexos (id INTEGER PRIMARY KEY AUTOINCREMENT, recado_id INTEGER NOT NULL REFERENCES mural_recados(id) ON DELETE CASCADE, file_name TEXT NOT NULL, mime_type TEXT DEFAULT 'application/octet-stream', file_size INTEGER DEFAULT 0, criado_em TEXT DEFAULT (datetime('now','localtime')))",
            "CREATE TABLE IF NOT EXISTS mural_anexo_contents (attachment_id INTEGER PRIMARY KEY REFERENCES mural_anexos(id) ON DELETE CASCADE, content BLOB NOT NULL)",
            "CREATE TABLE IF NOT EXISTS mural_comentarios (id INTEGER PRIMARY KEY AUTOINCREMENT, recado_id INTEGER NOT NULL REFERENCES mural_recados(id) ON DELETE CASCADE, autor TEXT NOT NULL, texto TEXT NOT NULL, criado_em TEXT DEFAULT (datetime('now', 'localtime')))",
            "CREATE TABLE IF NOT EXISTS calendario_eventos (id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT NOT NULL, tipo TEXT NOT NULL CHECK (tipo IN ('PAYMENT','COMMITMENT','HOLIDAY','NOTE')), texto TEXT NOT NULL, criado_em TEXT DEFAULT (datetime('now','localtime')))",
            "CREATE TABLE IF NOT EXISTS calendario_overrides (data TEXT PRIMARY KEY, criado_em TEXT DEFAULT (datetime('now','localtime')))",
            "CREATE TABLE IF NOT EXISTS calendario_regras (chave TEXT PRIMARY KEY, valor TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS mural_config (chave TEXT PRIMARY KEY, valor TEXT NOT NULL DEFAULT '')",

            "CREATE TABLE IF NOT EXISTS audit_trail (id INTEGER PRIMARY KEY AUTOINCREMENT, tabela TEXT NOT NULL, registro_id TEXT DEFAULT '', operacao TEXT NOT NULL, dados_anteriores TEXT DEFAULT '{}', dados_novos TEXT DEFAULT '{}', ip TEXT DEFAULT '', timestamp TEXT DEFAULT (datetime('now', 'localtime')))",
        ]:
            cur.execute(sql)
        _log_startup("Tabelas base verificadas/criadas.")

        # Helper for migrating foreign keys
        def migrate_table_foreign_keys(table_name, create_sql, check_key_column=None, expected_on_delete=None):
            cur.execute(f"PRAGMA foreign_key_list({table_name})")
            fks = [dict(r) for r in cur.fetchall()]
            
            needs_migration = False
            if not fks:
                needs_migration = True
            elif check_key_column and expected_on_delete:
                fk_match = [f for f in fks if f['from'] == check_key_column]
                if not fk_match or fk_match[0]['on_delete'] != expected_on_delete:
                    needs_migration = True
                    
            if needs_migration:
                _log_startup(f"Tabela '{table_name}' precisa de migração de foreign key. Executando...")
                cur.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
                if cur.fetchone():
                    try:
                        cur.execute(f"ALTER TABLE {table_name} RENAME TO {table_name}_old")
                        cur.execute(create_sql)
                        cur.execute(f"PRAGMA table_info({table_name}_old)")
                        old_cols = [r["name"] for r in cur.fetchall()]
                        cols_str = ", ".join(old_cols)
                        cur.execute(f"INSERT INTO {table_name} ({cols_str}) SELECT {cols_str} FROM {table_name}_old")
                        cur.execute(f"DROP TABLE {table_name}_old")
                        _log_startup(f"Migração de foreign key para '{table_name}' realizada com sucesso.")
                    except Exception as e:
                        app.logger.warning(f"Erro ao migrar foreign keys da tabela {table_name}: {e}")
                        _log_startup(f"Erro ao migrar foreign keys da tabela '{table_name}': {e}", "WARNING")

        # Migrate empenhos (ON DELETE CASCADE)
        migrate_table_foreign_keys(
            "empenhos",
            "CREATE TABLE empenhos (id INTEGER PRIMARY KEY AUTOINCREMENT, credor_id INTEGER NOT NULL, ano INTEGER NOT NULL, mes INTEGER NOT NULL, empenhado INTEGER DEFAULT 1, timestamp TEXT, UNIQUE(credor_id, ano, mes), FOREIGN KEY(credor_id) REFERENCES credores(id) ON DELETE CASCADE)",
            "credor_id",
            "CASCADE"
        )

        # Migrate autentique_envios (referential integrity)
        migrate_table_foreign_keys(
            "autentique_envios",
            "CREATE TABLE autentique_envios (id INTEGER PRIMARY KEY AUTOINCREMENT, documento_centro_id INTEGER NOT NULL, autentique_document_id TEXT DEFAULT '', autentique_signature_public_id TEXT DEFAULT '', documento_nome TEXT DEFAULT '', signatario_nome TEXT NOT NULL, signatario_phone TEXT NOT NULL, status TEXT DEFAULT 'pendente', delivery_method TEXT DEFAULT 'DELIVERY_METHOD_WHATSAPP', assinatura_link TEXT DEFAULT '', webhook_evento TEXT DEFAULT '', webhook_payload TEXT DEFAULT '', assinado_doc_id INTEGER, assinado_em TEXT DEFAULT '', criado_em TEXT DEFAULT (datetime('now', 'localtime')), atualizado_em TEXT DEFAULT (datetime('now', 'localtime')), FOREIGN KEY(documento_centro_id) REFERENCES documentos_centro(id) ON DELETE CASCADE, FOREIGN KEY(assinado_doc_id) REFERENCES documentos_centro(id) ON DELETE SET NULL)",
            "documento_centro_id",
            "CASCADE"
        )

        # Migrate protocolos (referential integrity)
        migrate_table_foreign_keys(
            "protocolos",
            "CREATE TABLE protocolos (id INTEGER PRIMARY KEY AUTOINCREMENT, numero TEXT NOT NULL UNIQUE, tipo TEXT NOT NULL, direcao TEXT DEFAULT 'recebido', origem_destino TEXT DEFAULT '', assunto TEXT NOT NULL, data_protocolo TEXT NOT NULL, prazo_resposta TEXT DEFAULT '', status TEXT DEFAULT 'recebido', observacoes TEXT DEFAULT '', doc_id INTEGER, criado_em TEXT DEFAULT (datetime('now','localtime')), FOREIGN KEY(doc_id) REFERENCES documentos_centro(id) ON DELETE SET NULL)",
            "doc_id",
            "SET NULL"
        )

        # Migrate logs (referential integrity)
        migrate_table_foreign_keys(
            "logs",
            "CREATE TABLE logs (id INTEGER PRIMARY KEY AUTOINCREMENT, acao TEXT NOT NULL, credor_id INTEGER, credor_nome TEXT, detalhes TEXT, data TEXT DEFAULT (datetime('now', 'localtime')), FOREIGN KEY(credor_id) REFERENCES credores(id) ON DELETE SET NULL)",
            "credor_id",
            "SET NULL"
        )

        # Split BLOB table: kanban_attachments
        cur.execute("PRAGMA table_info(kanban_attachments)")
        cols = [r["name"] for r in cur.fetchall()]
        if "content" in cols:
            _log_startup("Executando divisão da tabela 'kanban_attachments' (removendo blob content da tabela principal)...")
            try:
                cur.execute("ALTER TABLE kanban_attachments RENAME TO kanban_attachments_old")
                cur.execute("CREATE TABLE kanban_attachments (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL REFERENCES kanban_tasks(id) ON DELETE CASCADE, file_name TEXT NOT NULL, mime_type TEXT DEFAULT 'application/octet-stream', file_size INTEGER DEFAULT 0, criado_em TEXT DEFAULT (datetime('now','localtime')))")
                cur.execute("CREATE TABLE IF NOT EXISTS kanban_attachment_contents (attachment_id INTEGER PRIMARY KEY REFERENCES kanban_attachments(id) ON DELETE CASCADE, content BLOB NOT NULL)")
                cur.execute("INSERT INTO kanban_attachments (id, task_id, file_name, mime_type, file_size, criado_em) SELECT id, task_id, file_name, mime_type, file_size, criado_em FROM kanban_attachments_old")
                cur.execute("INSERT OR IGNORE INTO kanban_attachment_contents (attachment_id, content) SELECT id, content FROM kanban_attachments_old WHERE content IS NOT NULL")
                cur.execute("DROP TABLE kanban_attachments_old")
                _log_startup("Divisão da tabela 'kanban_attachments' realizada com sucesso.")
            except Exception as e:
                app.logger.warning(f"Erro ao dividir tabela kanban_attachments: {e}")
                _log_startup(f"Erro ao dividir tabela 'kanban_attachments': {e}", "WARNING")
        else:
            cur.execute("CREATE TABLE IF NOT EXISTS kanban_attachment_contents (attachment_id INTEGER PRIMARY KEY REFERENCES kanban_attachments(id) ON DELETE CASCADE, content BLOB NOT NULL)")
            cur.execute("PRAGMA foreign_key_list(kanban_attachment_contents)")
            fks = [dict(r) for r in cur.fetchall()]
            if any(fk["table"] == "kanban_attachments_old" for fk in fks):
                _log_startup("Corrigindo FK órfã em 'kanban_attachment_contents'...")
                try:
                    cur.execute("ALTER TABLE kanban_attachment_contents RENAME TO kanban_attachment_contents_old")
                    cur.execute("CREATE TABLE kanban_attachment_contents (attachment_id INTEGER PRIMARY KEY REFERENCES kanban_attachments(id) ON DELETE CASCADE, content BLOB NOT NULL)")
                    cur.execute("INSERT INTO kanban_attachment_contents (attachment_id, content) SELECT attachment_id, content FROM kanban_attachment_contents_old")
                    cur.execute("DROP TABLE kanban_attachment_contents_old")
                    _log_startup("FK em 'kanban_attachment_contents' corrigida com sucesso.")
                except Exception as e:
                    app.logger.warning(f"Erro ao corrigir FK de kanban_attachment_contents: {e}")
                    _log_startup(f"Erro ao corrigir FK de 'kanban_attachment_contents': {e}", "WARNING")

        # Split BLOB table: protocolo_anexos
        cur.execute("PRAGMA table_info(protocolo_anexos)")
        cols = [r["name"] for r in cur.fetchall()]
        if "content" in cols:
            _log_startup("Executando divisão da tabela 'protocolo_anexos' (removendo blob content da tabela principal)...")
            try:
                cur.execute("ALTER TABLE protocolo_anexos RENAME TO protocolo_anexos_old")
                cur.execute("CREATE TABLE protocolo_anexos (id INTEGER PRIMARY KEY AUTOINCREMENT, protocolo_id INTEGER NOT NULL REFERENCES protocolos(id) ON DELETE CASCADE, file_name TEXT NOT NULL, mime_type TEXT DEFAULT 'application/octet-stream', file_size INTEGER DEFAULT 0, criado_em TEXT DEFAULT (datetime('now','localtime')))")
                cur.execute("CREATE TABLE IF NOT EXISTS protocolo_anexo_contents (anexo_id INTEGER PRIMARY KEY REFERENCES protocolo_anexos(id) ON DELETE CASCADE, content BLOB NOT NULL)")
                cur.execute("INSERT INTO protocolo_anexos (id, protocolo_id, file_name, mime_type, file_size, criado_em) SELECT id, protocolo_id, file_name, mime_type, file_size, criado_em FROM protocolo_anexos_old")
                cur.execute("INSERT OR IGNORE INTO protocolo_anexo_contents (anexo_id, content) SELECT id, content FROM protocolo_anexos_old WHERE content IS NOT NULL")
                cur.execute("DROP TABLE protocolo_anexos_old")
                _log_startup("Divisão da tabela 'protocolo_anexos' realizada com sucesso.")
            except Exception as e:
                app.logger.warning(f"Erro ao dividir tabela protocolo_anexos: {e}")
                _log_startup(f"Erro ao dividir tabela 'protocolo_anexos': {e}", "WARNING")
        else:
            cur.execute("CREATE TABLE IF NOT EXISTS protocolo_anexo_contents (anexo_id INTEGER PRIMARY KEY REFERENCES protocolo_anexos(id) ON DELETE CASCADE, content BLOB NOT NULL)")
            cur.execute("PRAGMA foreign_key_list(protocolo_anexo_contents)")
            fks = [dict(r) for r in cur.fetchall()]
            if any(fk["table"] == "protocolo_anexos_old" for fk in fks):
                _log_startup("Corrigindo FK órfã em 'protocolo_anexo_contents'...")
                try:
                    cur.execute("ALTER TABLE protocolo_anexo_contents RENAME TO protocolo_anexo_contents_old")
                    cur.execute("CREATE TABLE protocolo_anexo_contents (anexo_id INTEGER PRIMARY KEY REFERENCES protocolo_anexos(id) ON DELETE CASCADE, content BLOB NOT NULL)")
                    cur.execute("INSERT INTO protocolo_anexo_contents (anexo_id, content) SELECT anexo_id, content FROM protocolo_anexo_contents_old")
                    cur.execute("DROP TABLE protocolo_anexo_contents_old")
                    _log_startup("FK em 'protocolo_anexo_contents' corrigida com sucesso.")
                except Exception as e:
                    app.logger.warning(f"Erro ao corrigir FK de protocolo_anexo_contents: {e}")
                    _log_startup(f"Erro ao corrigir FK de 'protocolo_anexo_contents': {e}", "WARNING")

        ensure_db_indexes(cur)
        for alter in [
            "ALTER TABLE credores ADD COLUMN atualizado_em TEXT DEFAULT (datetime('now','localtime'))",
            "ALTER TABLE kanban_tasks ADD COLUMN categoria TEXT DEFAULT ''",
            "ALTER TABLE kanban_tasks ADD COLUMN data_vencimento TEXT DEFAULT ''",
            "ALTER TABLE kanban_tasks ADD COLUMN responsavel TEXT DEFAULT ''",
            "ALTER TABLE kanban_tasks ADD COLUMN concluido_em TEXT DEFAULT ''",
            "ALTER TABLE kanban_tasks ADD COLUMN valor REAL DEFAULT 0",
            "ALTER TABLE mural_recados ADD COLUMN valor REAL DEFAULT 0.0",
            "ALTER TABLE mural_recados ADD COLUMN credor_id INTEGER REFERENCES credores(id) ON DELETE SET NULL",
            "ALTER TABLE mural_recados ADD COLUMN vencimento TEXT DEFAULT ''",
        ]:
            try:
                cur.execute(alter)
            except Exception:
                pass
        # Add snapshot columns to logs
        for alter_extra in [
            "ALTER TABLE logs ADD COLUMN credor_departamento TEXT DEFAULT ''",
            "ALTER TABLE logs ADD COLUMN credor_cnpj TEXT DEFAULT ''",
        ]:
            try:
                cur.execute(alter_extra)
            except Exception:
                pass

        # Drop senha_plana column if it still exists
        cur.execute("PRAGMA table_info(usuarios)")
        user_cols = [r["name"] for r in cur.fetchall()]
        if "senha_plana" in user_cols:
            try:
                cur.execute("ALTER TABLE usuarios RENAME TO usuarios_migration_temp")
                cur.execute("""CREATE TABLE usuarios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT NOT NULL,
                    email TEXT DEFAULT '',
                    login TEXT NOT NULL UNIQUE,
                    senha_hash TEXT NOT NULL,
                    nivel TEXT NOT NULL DEFAULT 'operador'
                        CHECK (nivel IN ('admin','operador','leitor')),
                    ativo INTEGER NOT NULL DEFAULT 1,
                    criado_em TEXT DEFAULT (datetime('now','localtime')),
                    atualizado_em TEXT DEFAULT (datetime('now','localtime'))
                )""")
                cur.execute("INSERT INTO usuarios (id,nome,email,login,senha_hash,nivel,ativo,criado_em,atualizado_em) SELECT id,nome,email,login,senha_hash,nivel,ativo,criado_em,atualizado_em FROM usuarios_migration_temp")
                cur.execute("DROP TABLE usuarios_migration_temp")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_usuarios_login ON usuarios(login)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_usuarios_nivel ON usuarios(nivel)")
            except Exception:
                pass
        conn.commit()

        # Multi-user auth table
        cur.execute("""CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT DEFAULT '',
            login TEXT NOT NULL UNIQUE,
            senha_hash TEXT NOT NULL,

            nivel TEXT NOT NULL DEFAULT 'operador'
                CHECK (nivel IN ('admin','operador','leitor')),
            ativo INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT DEFAULT (datetime('now','localtime')),
            atualizado_em TEXT DEFAULT (datetime('now','localtime'))
        )""")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_usuarios_login ON usuarios(login)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_usuarios_nivel ON usuarios(nivel)")
        conn.commit()
        _log_startup("Migrações do banco de dados (migrate_db) concluídas com sucesso.")

    def init_db():
        _log_startup("Iniciando estrutura principal do banco de dados (init_db)...")
        conn = get_db()
        cur = conn.cursor()
        for sql in [
            "CREATE TABLE IF NOT EXISTS credores (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL, valor REAL DEFAULT 0 CHECK (valor >= 0), descricao TEXT, cnpj TEXT, email TEXT, tipo_valor TEXT DEFAULT 'FIXO' CHECK (tipo_valor IN ('FIXO','VARIÁVEL')), solicitacao TEXT, pagamento TEXT, validade TEXT CHECK (validade IS NULL OR validade GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'), departamento TEXT, obs TEXT, ativo INTEGER DEFAULT 1 CHECK (ativo IN (0,1)))",
            "CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, acao TEXT NOT NULL, credor_id INTEGER, credor_nome TEXT, credor_departamento TEXT DEFAULT '', credor_cnpj TEXT DEFAULT '', detalhes TEXT, data TEXT DEFAULT (datetime('now', 'localtime')), FOREIGN KEY(credor_id) REFERENCES credores(id) ON DELETE SET NULL)",
            "CREATE TABLE IF NOT EXISTS empenhos (id INTEGER PRIMARY KEY AUTOINCREMENT, credor_id INTEGER NOT NULL, ano INTEGER NOT NULL CHECK (ano >= 2000 AND ano <= 2100), mes INTEGER NOT NULL CHECK (mes >= 1 AND mes <= 12), empenhado INTEGER DEFAULT 1 CHECK (empenhado IN (0,1)), timestamp TEXT NOT NULL DEFAULT (datetime('now','localtime')), UNIQUE(credor_id, ano, mes), FOREIGN KEY(credor_id) REFERENCES credores(id) ON DELETE CASCADE)",
            "CREATE TABLE IF NOT EXISTS rpas (id INTEGER PRIMARY KEY AUTOINCREMENT, numero_rpa TEXT, nome_prestador TEXT NOT NULL, cpf_prestador TEXT, endereco_prestador TEXT, descricao_servico TEXT, periodo_referencia TEXT, carga_horaria TEXT, local_execucao TEXT, valor_bruto REAL DEFAULT 0, num_dependentes INTEGER DEFAULT 0, pensao_alimenticia REAL DEFAULT 0, inss REAL DEFAULT 0, iss REAL DEFAULT 0, deducao_dependentes REAL DEFAULT 0, base_calculo_irrf REAL DEFAULT 0, aliquota_irrf REAL DEFAULT 0, parcela_deduzir_irrf REAL DEFAULT 0, ir REAL DEFAULT 0, valor_liquido REAL DEFAULT 0, observacoes TEXT, data_emissao TEXT, criado_em TEXT DEFAULT (datetime('now', 'localtime')))",
            "CREATE TABLE IF NOT EXISTS kanban_tasks (id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT DEFAULT '', status TEXT DEFAULT 'todo' CHECK (status IN ('todo','in-progress','done')), priority TEXT DEFAULT 'medium' CHECK (priority IN ('low','medium','high')), concluido_em TEXT DEFAULT '', criado_em TEXT DEFAULT (datetime('now', 'localtime')), atualizado_em TEXT DEFAULT (datetime('now', 'localtime')))",
            "CREATE TABLE IF NOT EXISTS kanban_attachments (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL REFERENCES kanban_tasks(id) ON DELETE CASCADE, file_name TEXT NOT NULL, mime_type TEXT DEFAULT 'application/octet-stream', file_size INTEGER DEFAULT 0, criado_em TEXT DEFAULT (datetime('now','localtime')))",
            "CREATE TABLE IF NOT EXISTS fornecimento_dados (id INTEGER PRIMARY KEY AUTOINCREMENT, tipo TEXT NOT NULL, valor TEXT NOT NULL, criado_em TEXT DEFAULT (datetime('now', 'localtime')), UNIQUE(tipo, valor))",
            "CREATE TABLE IF NOT EXISTS fornecimento_solicitacoes (id INTEGER PRIMARY KEY AUTOINCREMENT, solicitante TEXT NOT NULL, empresa TEXT DEFAULT '', data TEXT NOT NULL, obs TEXT DEFAULT '', criado_em TEXT DEFAULT (datetime('now','localtime')), atualizado_em TEXT DEFAULT (datetime('now','localtime')))",
            "CREATE TABLE IF NOT EXISTS fornecimento_solicitacao_itens (id INTEGER PRIMARY KEY AUTOINCREMENT, solicitacao_id INTEGER NOT NULL REFERENCES fornecimento_solicitacoes(id) ON DELETE CASCADE, nome TEXT NOT NULL, desc TEXT DEFAULT '', qtd TEXT DEFAULT '', preco TEXT DEFAULT '')",
            "CREATE TABLE IF NOT EXISTS configuracoes (chave TEXT PRIMARY KEY, valor TEXT NOT NULL DEFAULT '', atualizado_em TEXT DEFAULT (datetime('now', 'localtime')))",
            "CREATE TABLE IF NOT EXISTS documentos_centro (id INTEGER PRIMARY KEY AUTOINCREMENT, nome_original TEXT NOT NULL, nome_arquivo TEXT NOT NULL, categoria TEXT NOT NULL, referencia TEXT DEFAULT '', descricao TEXT DEFAULT '', tamanho INTEGER DEFAULT 0, extensao TEXT DEFAULT '', caminho_relativo TEXT NOT NULL, criado_em TEXT DEFAULT (datetime('now', 'localtime')))",
            "CREATE TABLE IF NOT EXISTS autentique_envios (id INTEGER PRIMARY KEY AUTOINCREMENT, documento_centro_id INTEGER NOT NULL, autentique_document_id TEXT DEFAULT '', autentique_signature_public_id TEXT DEFAULT '', documento_nome TEXT DEFAULT '', signatario_nome TEXT NOT NULL, signatario_phone TEXT NOT NULL, status TEXT DEFAULT 'pendente', delivery_method TEXT DEFAULT 'DELIVERY_METHOD_WHATSAPP', assinatura_link TEXT DEFAULT '', webhook_evento TEXT DEFAULT '', webhook_payload TEXT DEFAULT '', assinado_doc_id INTEGER, assinado_em TEXT DEFAULT '', criado_em TEXT DEFAULT (datetime('now', 'localtime')), atualizado_em TEXT DEFAULT (datetime('now', 'localtime')), FOREIGN KEY(documento_centro_id) REFERENCES documentos_centro(id) ON DELETE CASCADE, FOREIGN KEY(assinado_doc_id) REFERENCES documentos_centro(id) ON DELETE SET NULL)",
            "CREATE TABLE IF NOT EXISTS autentique_contatos (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL, phone TEXT NOT NULL UNIQUE, criado_em TEXT DEFAULT (datetime('now', 'localtime')), atualizado_em TEXT DEFAULT (datetime('now', 'localtime')))",
            "CREATE TABLE IF NOT EXISTS empenho_assistente_historico (id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT NOT NULL, payload_json TEXT NOT NULL DEFAULT '{}', resultado_json TEXT NOT NULL DEFAULT '{}', campos_json TEXT NOT NULL DEFAULT '{}', checklist_json TEXT NOT NULL DEFAULT '{}', descricao_base TEXT DEFAULT '', descricao_melhorada TEXT DEFAULT '', diff_json TEXT NOT NULL DEFAULT '{}', model TEXT DEFAULT '', cached INTEGER DEFAULT 0, criado_em TEXT DEFAULT (datetime('now', 'localtime')))",
            "CREATE TABLE IF NOT EXISTS classificador_despesa_historico (id INTEGER PRIMARY KEY AUTOINCREMENT, item TEXT NOT NULL, codigo_completo TEXT NOT NULL DEFAULT '', grupo TEXT DEFAULT '', modalidade TEXT DEFAULT '', elemento TEXT DEFAULT '', subelemento TEXT DEFAULT '', justificativa TEXT DEFAULT '', ponto_atencao TEXT DEFAULT '', confianca REAL DEFAULT 0.0, resultado_json TEXT NOT NULL DEFAULT '{}', model TEXT DEFAULT '', cached INTEGER DEFAULT 0, criado_em TEXT DEFAULT (datetime('now', 'localtime')))",
            "CREATE TABLE IF NOT EXISTS prazos (id INTEGER PRIMARY KEY AUTOINCREMENT, titulo TEXT NOT NULL, descricao TEXT DEFAULT '', data_limite TEXT NOT NULL, categoria TEXT DEFAULT 'geral', resolvido INTEGER DEFAULT 0, criado_em TEXT DEFAULT (datetime('now','localtime')))",
            "CREATE TABLE IF NOT EXISTS protocolos (id INTEGER PRIMARY KEY AUTOINCREMENT, numero TEXT NOT NULL UNIQUE, tipo TEXT NOT NULL, direcao TEXT DEFAULT 'recebido', origem_destino TEXT DEFAULT '', assunto TEXT NOT NULL, data_protocolo TEXT NOT NULL, prazo_resposta TEXT DEFAULT '', status TEXT DEFAULT 'recebido', observacoes TEXT DEFAULT '', doc_id INTEGER, criado_em TEXT DEFAULT (datetime('now','localtime')), FOREIGN KEY(doc_id) REFERENCES documentos_centro(id) ON DELETE SET NULL)",
            "CREATE TABLE IF NOT EXISTS protocolo_anexos (id INTEGER PRIMARY KEY AUTOINCREMENT, protocolo_id INTEGER NOT NULL REFERENCES protocolos(id) ON DELETE CASCADE, file_name TEXT NOT NULL, mime_type TEXT DEFAULT 'application/octet-stream', file_size INTEGER DEFAULT 0, criado_em TEXT DEFAULT (datetime('now','localtime')))", "CREATE TABLE IF NOT EXISTS mural_recados (id INTEGER PRIMARY KEY AUTOINCREMENT, titulo TEXT NOT NULL, conteudo TEXT NOT NULL, autor TEXT NOT NULL, destinatario TEXT DEFAULT 'Todos', prioridade TEXT DEFAULT 'media', categoria TEXT DEFAULT 'tarefa', status TEXT DEFAULT 'a_fazer', cor TEXT DEFAULT 'yellow', concluido_por TEXT DEFAULT '', concluido_em TEXT DEFAULT '', valor REAL DEFAULT 0.0, credor_id INTEGER REFERENCES credores(id) ON DELETE SET NULL, criado_em TEXT DEFAULT (datetime('now', 'localtime')), atualizado_em TEXT DEFAULT (datetime('now', 'localtime')))",
            "CREATE TABLE IF NOT EXISTS mural_anexos (id INTEGER PRIMARY KEY AUTOINCREMENT, recado_id INTEGER NOT NULL REFERENCES mural_recados(id) ON DELETE CASCADE, file_name TEXT NOT NULL, mime_type TEXT DEFAULT 'application/octet-stream', file_size INTEGER DEFAULT 0, criado_em TEXT DEFAULT (datetime('now','localtime')))",
            "CREATE TABLE IF NOT EXISTS mural_anexo_contents (attachment_id INTEGER PRIMARY KEY REFERENCES mural_anexos(id) ON DELETE CASCADE, content BLOB NOT NULL)",
            "CREATE TABLE IF NOT EXISTS mural_comentarios (id INTEGER PRIMARY KEY AUTOINCREMENT, recado_id INTEGER NOT NULL REFERENCES mural_recados(id) ON DELETE CASCADE, autor TEXT NOT NULL, texto TEXT NOT NULL, criado_em TEXT DEFAULT (datetime('now', 'localtime')))",
            "CREATE TABLE IF NOT EXISTS calendario_eventos (id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT NOT NULL, tipo TEXT NOT NULL CHECK (tipo IN ('PAYMENT','COMMITMENT','HOLIDAY','NOTE')), texto TEXT NOT NULL, criado_em TEXT DEFAULT (datetime('now','localtime')))",
            "CREATE TABLE IF NOT EXISTS calendario_overrides (data TEXT PRIMARY KEY, criado_em TEXT DEFAULT (datetime('now','localtime')))",
            "CREATE TABLE IF NOT EXISTS calendario_regras (chave TEXT PRIMARY KEY, valor TEXT NOT NULL)",

        ]:
            cur.execute(sql)

        # FTS5 virtual tables for full-text search
        cur.execute("CREATE VIRTUAL TABLE IF NOT EXISTS credores_fts USING fts5(nome, descricao, cnpj, email, content=credores, content_rowid=id)")
        cur.execute("CREATE VIRTUAL TABLE IF NOT EXISTS protocolos_fts USING fts5(assunto, origem_destino, numero, content=protocolos, content_rowid=id)")

        # Schema version tracking
        cur.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY, applied_at TEXT DEFAULT (datetime('now','localtime')))")
        cur.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (2)")

        # View para classificador sem colunas redundantes
        cur.execute("""
            CREATE VIEW IF NOT EXISTS v_classificador_despesa AS
            SELECT 
                id, item, codigo_completo,
                json_extract(resultado_json, '$.grupo') AS grupo,
                json_extract(resultado_json, '$.modalidade') AS modalidade,
                json_extract(resultado_json, '$.elemento') AS elemento,
                json_extract(resultado_json, '$.subelemento_codigo') || ' - ' || json_extract(resultado_json, '$.subelemento_nome') AS subelemento,
                json_extract(resultado_json, '$.justificativa') AS justificativa,
                json_extract(resultado_json, '$.ponto_atencao') AS ponto_atencao,
                CAST(COALESCE(json_extract(resultado_json, '$.confianca'), 0) AS REAL) AS confianca,
                resultado_json, model, cached, criado_em
            FROM classificador_despesa_historico
        """)

        # Structured audit changes in logs
        for alter_extra in [
            "ALTER TABLE logs ADD COLUMN mudancas_json TEXT DEFAULT '{}'",
        ]:
            try:
                cur.execute(alter_extra)
            except Exception:
                pass

        # Unified CSV import tables (replaces despesas_importacoes + empenhos_importacoes)
        cur.execute("CREATE TABLE IF NOT EXISTS csv_importacoes (id INTEGER PRIMARY KEY AUTOINCREMENT, tipo TEXT NOT NULL CHECK (tipo IN ('despesa','empenho')), periodo TEXT NOT NULL, descricao TEXT DEFAULT '', arquivo TEXT DEFAULT '', total_rows INTEGER DEFAULT 0, colunas TEXT DEFAULT '[]', importado_em TEXT DEFAULT (datetime('now','localtime')))")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_csv_importacoes_tipo_periodo ON csv_importacoes(tipo, periodo)")
        cur.execute("CREATE TABLE IF NOT EXISTS csv_linhas (id INTEGER PRIMARY KEY AUTOINCREMENT, importacao_id INTEGER NOT NULL REFERENCES csv_importacoes(id) ON DELETE CASCADE, dados TEXT NOT NULL)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_csv_linhas_importacao ON csv_linhas(importacao_id)")

        # Migrate data from old tables if they exist
        old_despesas = cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='despesas_importacoes'").fetchone()
        if old_despesas:
            try:
                cur.execute("INSERT OR IGNORE INTO csv_importacoes (id,tipo,periodo,descricao,arquivo,total_rows,colunas,importado_em) SELECT id,'despesa',periodo,COALESCE(descricao,''),COALESCE(arquivo,''),total_rows,COALESCE(colunas,'[]'),importado_em FROM despesas_importacoes")
                cur.execute("INSERT OR IGNORE INTO csv_linhas (id,importacao_id,dados) SELECT id,importacao_id,dados FROM despesas_linhas")
            except Exception:
                pass
        
        old_empenhos_imp = cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='empenhos_importacoes'").fetchone()
        if old_empenhos_imp:
            try:
                max_id = cur.execute("SELECT COALESCE(MAX(id),0) FROM csv_linhas").fetchone()[0]
                cur.execute("INSERT OR IGNORE INTO csv_importacoes (tipo,periodo,descricao,arquivo,total_rows,colunas,importado_em) SELECT 'empenho',periodo,COALESCE(descricao,''),COALESCE(arquivo,''),total_rows,'[]',importado_em FROM empenhos_importacoes")
                for imp_row in cur.execute("SELECT id FROM empenhos_importacoes ORDER BY id").fetchall():
                    old_id = imp_row["id"]
                    new_id = cur.execute("SELECT id FROM csv_importacoes WHERE tipo='empenho' AND id NOT IN (SELECT id FROM csv_importacoes WHERE tipo='despesa') ORDER BY id").fetchone()
                    if new_id:
                        cur.execute("INSERT OR IGNORE INTO csv_linhas (importacao_id,dados) SELECT ?,dados FROM empenhos_linhas WHERE importacao_id=?", (new_id["id"], old_id))
            except Exception:
                pass

        # FTS5 sync triggers
        cur.executescript("""
            CREATE TRIGGER IF NOT EXISTS credores_fts_ai AFTER INSERT ON credores BEGIN
                INSERT INTO credores_fts(rowid, nome, descricao, cnpj, email)
                VALUES (new.id, new.nome, new.descricao, new.cnpj, new.email);
            END;
            CREATE TRIGGER IF NOT EXISTS credores_fts_ad AFTER DELETE ON credores BEGIN
                INSERT INTO credores_fts(credores_fts, rowid, nome, descricao, cnpj, email)
                VALUES ('delete', old.id, old.nome, old.descricao, old.cnpj, old.email);
            END;
            CREATE TRIGGER IF NOT EXISTS credores_fts_au AFTER UPDATE ON credores BEGIN
                INSERT INTO credores_fts(credores_fts, rowid, nome, descricao, cnpj, email)
                VALUES ('delete', old.id, old.nome, old.descricao, old.cnpj, old.email);
                INSERT INTO credores_fts(rowid, nome, descricao, cnpj, email)
                VALUES (new.id, new.nome, new.descricao, new.cnpj, new.email);
            END;
            CREATE TRIGGER IF NOT EXISTS protocolos_fts_ai AFTER INSERT ON protocolos BEGIN
                INSERT INTO protocolos_fts(rowid, assunto, origem_destino, numero)
                VALUES (new.id, new.assunto, new.origem_destino, new.numero);
            END;
            CREATE TRIGGER IF NOT EXISTS protocolos_fts_ad AFTER DELETE ON protocolos BEGIN
                INSERT INTO protocolos_fts(protocolos_fts, rowid, assunto, origem_destino, numero)
                VALUES ('delete', old.id, old.assunto, old.origem_destino, old.numero);
            END;
            CREATE TRIGGER IF NOT EXISTS protocolos_fts_au AFTER UPDATE ON protocolos BEGIN
                INSERT INTO protocolos_fts(protocolos_fts, rowid, assunto, origem_destino, numero)
                VALUES ('delete', old.id, old.assunto, old.origem_destino, old.numero);
                INSERT INTO protocolos_fts(rowid, assunto, origem_destino, numero)
                VALUES (new.id, new.assunto, new.origem_destino, new.numero);
            END;
        """)

        count = cur.execute("SELECT COUNT(*) FROM credores").fetchone()[0]
        if count == 0 and os.path.exists(DATA_JS):
            _log_startup("Banco de dados vazio. Populando dados iniciais de data.js...")
            print("Populando banco com dados do data.js...")
            _seed_from_data_js(cur)
        ensure_db_indexes(cur)
        conn.commit()
        _log_startup("Estrutura principal do banco de dados (init_db) e triggers FTS5 gravadas e consolidadas.")

        try:
            conn.execute("VACUUM")
            _log_startup("Comando SQLite VACUUM executado com sucesso.")
        except Exception as e:
            _log_startup(f"Aviso: Falha ao rodar SQLite VACUUM: {e}", "WARNING")

    def _seed_from_data_js(cur):
        with open(DATA_JS, encoding="utf-8") as f:
            content = f.read()
        match = re.search(r"const CREDORES_FIXOS\s*=\s*(\[[\s\S]*?\]);", content)
        if not match:
            print("ATENÇÃO: Não foi possível ler o data.js.")
            return
        data = json.loads(match.group(1))
        for c in data:
            cur.execute(
                "INSERT INTO credores (nome,valor,descricao,cnpj,email,tipo_valor,solicitacao,pagamento,departamento,obs) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    c.get("NOME", ""),
                    float(c.get("VALOR") or 0),
                    c.get("DESCRIÇÃO", ""),
                    c.get("CNPJ", ""),
                    c.get("EMAIL", ""),
                    c.get("TIPO DE VALOR", "FIXO"),
                    str(c.get("SOLICITAÇÃO", "")),
                    str(c.get("PAGAMENTO", "")),
                    c.get("DEPARTAMENTO", ""),
                    c.get("OBS", ""),
                ),
            )
        print(f"  {len(data)} credores inseridos.")

    # Expose get_db to blueprints via app context
    app._get_db = get_db
    app._init_db = init_db
    app._migrate_db = migrate_db

    # ── Middlewares ──────────────────────────────────────────
    @app.before_request
    def mark_request_start():
        g._request_started_at = _time.perf_counter()
        g._request_full_path = request.full_path.rstrip("?")
        g._request_ip = (
            request.headers.get("X-Forwarded-For", request.remote_addr or "-")
            .split(",")[0]
            .strip()
        )
        g._get_db = get_db

    # ── Auth guard global para a API ─────────────────────────
    # Toda rota /api/ exige sessao autenticada, exceto o fluxo de login
    # e endpoints de monitoramento. Centraliza a protecao que antes
    # faltava na maioria dos blueprints (credores, rpas, prazos, etc.).
    _API_AUTH_WHITELIST = {
        "/api/auth/login",
        "/api/auth/adm",
        "/api/auth/verificar",
        "/api/auth/sair",
        "/api/ping",
        "/api/health",
        "/api/autentique/webhook",  # chamado por servico externo (sem sessao)
    }

    @app.before_request
    def require_api_auth():
        from flask import session

        path = request.path
        if not path.startswith("/api/"):
            return None
        if request.method == "OPTIONS":  # preflight CORS
            return None
        if path in _API_AUTH_WHITELIST:
            return None
        if "usuario_id" not in session:
            return jsonify({"error": "Nao autorizado"}), 401

    _COMPRESSIBLE = {
        "text/html",
        "text/css",
        "text/javascript",
        "application/javascript",
        "application/json",
        "image/svg+xml",
        "text/plain",
        "text/xml",
    }

    @app.after_request
    def compress_response(response):
        started_at = getattr(g, "_request_started_at", None)
        if started_at is not None:
            elapsed_ms = (_time.perf_counter() - started_at) * 1000
            response.headers["X-Response-Time-ms"] = f"{elapsed_ms:.1f}"
            if request.path.startswith("/api/"):
                _terminal_request_line(
                    request.method,
                    getattr(g, "_request_full_path", request.path),
                    response.status_code,
                    elapsed_ms,
                    getattr(g, "_request_ip", "-"),
                )
            if request.path.startswith("/api/") and elapsed_ms >= 250:
                app.logger.warning(
                    "Slow request %.1fms %s %s [%s]",
                    elapsed_ms,
                    request.method,
                    request.path,
                    response.status_code,
                )
        if (
            request.method == "GET"
            and request.path.startswith("/api/")
            and response.status_code == 200
            and "Cache-Control" not in response.headers
        ):
            response.headers["Cache-Control"] = "public, max-age=20"
        if (
            response.status_code < 200
            or response.status_code >= 300
            or response.direct_passthrough
            or "Content-Encoding" in response.headers
        ):
            return response
        mime = (response.content_type or "").split(";")[0].strip()
        if mime in _COMPRESSIBLE and "gzip" in request.headers.get(
            "Accept-Encoding", ""
        ):
            data = response.get_data()
            if len(data) > 256:
                response.set_data(_gzip.compress(data, compresslevel=4))
                response.headers["Content-Encoding"] = "gzip"
                response.headers["Vary"] = "Accept-Encoding"
                response.headers["Content-Length"] = len(response.get_data())
        return response

    # ── Static file cache in RAM ─────────────────────────────
    _file_cache: dict[str, tuple[bytes, str]] = {}
    _gzip_cache: dict[str, bytes] = {}
    _brotli_cache: dict[str, bytes] = {}
    _etag_cache: dict[str, str] = {}
    _file_mtime_cache: dict[str, float] = {}

    try:
        import brotli as _brotli

        _BROTLI_OK = True
    except ImportError:
        _BROTLI_OK = False

    _SKIP_EXTS = {
        # Banco de dados
        ".db", ".db-shm", ".db-wal",
        # Bytecode Python
        ".pyc", ".pyo",
        # Logs e scripts de sistema
        ".log", ".bat", ".ps1", ".sh",
        # Executaveis e arquivos binarios grandes (nao sao assets web)
        ".exe", ".dll", ".so", ".bin",
        # Arquivos comprimidos / pacotes
        ".zip", ".gz", ".tar", ".rar", ".7z",
        # Fontes TTF/OTF — browser moderno so precisa de .woff2
        ".ttf", ".otf", ".eot",
        # Codigo-fonte Python e docs (nao sao assets web)
        ".py", ".md", ".txt", ".rst",
        # Dados brutos (CSV pesado)
        ".csv",
    }
    _SKIP_DIRS = {
        "__pycache__",
        ".git",
        "DADOS",
        "renomer",
        "documentos_centro",
        "PARA IMPLEMENTAR TODO ESSE PROJETO NO PROJETO PRINCIPAL",
    }

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

    def _preload_static_files():
        count, total_kb = 0, 0
        started_at = _time.perf_counter()
        _terminal_log("BOOT", "Pré-carregando arquivos estáticos em RAM...", "cyan")
        _log_startup("Pré-carregamento de arquivos estáticos em RAM iniciado...")
        for root, dirs, files in os.walk(BASE_DIR):
            dirs[:] = [
                d for d in dirs 
                if d not in _SKIP_DIRS 
                and not d.startswith(".") 
                and d not in {"tests", "scripts", "services", "routes", "tmp", "scratch", "pref_extracted"}
            ]
            rel_root = os.path.relpath(root, BASE_DIR).replace("\\", "/")
            if rel_root == ".":
                rel_root = ""
            for fname in files:
                if fname.startswith("."):
                    continue
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
        _log_startup(f"Pré-carregamento finalizado. {count} arquivos carregados em RAM ({_fmt_bytes(total_kb * 1024)})")
        enc_count = max(len(_brotli_cache), len(_gzip_cache))
        enc_name = "brotli+gzip" if _BROTLI_OK else "gzip"
        _terminal_log(
            "GZIP",
            f"{enc_count} arquivos com versão {enc_name} prontos em {elapsed_ms:.1f} ms",
            "green",
        )
        _log_startup(f"Versões comprimidas prontas ({enc_count} arquivos em {elapsed_ms:.1f} ms)")

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

    # ── Static routes ────────────────────────────────────────
    @app.route("/favicon.ico")
    def favicon():
        return send_from_directory(os.path.join(BASE_DIR, "static", "img"), "brasao.png", mimetype="image/png")

    @app.route("/")
    def index():
        resp = _serve_cached("/pages/mural.html", "no-cache, no-store, must-revalidate")
        if resp:
            return resp
        r = send_file(os.path.join(BASE_DIR, "pages", "mural.html"))
        r.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return r

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
        r = send_from_directory(os.path.join(BASE_DIR, "static"), filename)
        r.headers["Cache-Control"] = cc
        return r

    @app.route("/<path:filename>")
    def static_files(filename):
        if filename.startswith("api/"):
            return jsonify({"error": "Rota não encontrada: " + filename}), 404
        url = "/" + filename
        cc = (
            "no-cache, must-revalidate"
            if filename.endswith(".html")
            else "public, max-age=3600"
        )
        resp = _serve_cached(url, cc)
        if resp:
            return resp
        r = send_from_directory(BASE_DIR, filename)
        if filename.endswith(".html"):
            r.headers["Cache-Control"] = "no-cache, must-revalidate"
        return r

    @app.errorhandler(404)
    def not_found(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Rota não encontrada", "path": request.path}), 404
        return str(e), 404

    @app.errorhandler(Exception)
    def handle_exception(e):
        import traceback
        import html
        from flask import session

        method = request.method
        url = request.url
        ip = getattr(g, "_request_ip", "-")
        if ip == "-" or not ip:
            ip = request.headers.get("X-Forwarded-For", request.remote_addr or "-").split(",")[0].strip()
        user = session.get("usuario_login") or "Anonymous"

        tb = traceback.format_exc()
        app.logger.error(
            "Erro do Sistema: %s\n"
            "Request URL: %s %s\n"
            "Client IP: %s | Usuário: %s\n"
            "Traceback:\n%s",
            str(e), method, url, ip, user, tb
        )

        if settings.debug:
            print(f"\033[31m[ERROR] {method} {url} from {ip}\033[0m")
            print(tb)

        if request.path.startswith("/api/"):
            return jsonify({
                "error": "Erro interno do servidor",
                "message": str(e),
                "path": request.path
            }), 500

        return f"""
        <!DOCTYPE html>
        <html lang="pt-BR">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Erro Interno - Prefeitura de Inajá</title>
            <link rel="preconnect" href="https://fonts.googleapis.com">
            <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
            <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;800&family=Plus+Jakarta+Sans:wght@400;500;700&family=Fira+Code:wght@400;500&display=swap" rel="stylesheet">
            <style>
                :root {{
                    --bg: #030712;
                    --card-bg: rgba(17, 24, 39, 0.7);
                    --border: rgba(255, 255, 255, 0.08);
                    --text: #f9fafb;
                    --text-secondary: #9ca3af;
                    --red: #ef4444;
                    --red-glow: rgba(239, 68, 68, 0.15);
                    --blue: #3b82f6;
                    --blue-glow: rgba(59, 130, 246, 0.2);
                    --purple: #8b5cf6;
                }}

                * {{
                    box-sizing: border-box;
                    margin: 0;
                    padding: 0;
                }}

                body {{
                    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                    background-color: var(--bg);
                    background-image: 
                        radial-gradient(circle at 10% 20%, rgba(239, 68, 68, 0.12) 0%, transparent 40%),
                        radial-gradient(circle at 90% 80%, rgba(139, 92, 246, 0.1) 0%, transparent 45%);
                    color: var(--text);
                    min-height: 100vh;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    padding: 24px;
                    overflow-x: hidden;
                }}

                .error-card {{
                    max-width: 780px;
                    width: 100%;
                    background: var(--card-bg);
                    border: 1px solid var(--border);
                    border-radius: 24px;
                    padding: 40px;
                    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
                    backdrop-filter: blur(16px);
                    -webkit-backdrop-filter: blur(16px);
                    position: relative;
                    animation: fadeInUp 0.6s cubic-bezier(0.16, 1, 0.3, 1) both;
                }}

                @keyframes fadeInUp {{
                    from {{
                        opacity: 0;
                        transform: translateY(20px);
                    }}
                    to {{
                        opacity: 1;
                        transform: translateY(0);
                    }}
                }}

                .icon-container {{
                    width: 72px;
                    height: 72px;
                    border-radius: 20px;
                    background: linear-gradient(135deg, var(--red), #b91c1c);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    margin-bottom: 24px;
                    box-shadow: 0 8px 24px var(--red-glow), inset 0 2px 4px rgba(255, 255, 255, 0.2);
                    animation: pulseGlow 2s infinite ease-in-out;
                }}

                @keyframes pulseGlow {{
                    0%, 100% {{ box-shadow: 0 8px 24px var(--red-glow); }}
                    50% {{ box-shadow: 0 8px 32px rgba(239, 68, 68, 0.35); }}
                }}

                .icon-container svg {{
                    width: 36px;
                    height: 36px;
                    color: white;
                }}

                h1 {{
                    font-family: 'Outfit', sans-serif;
                    font-size: clamp(24px, 4vw, 32px);
                    font-weight: 800;
                    letter-spacing: -0.02em;
                    background: linear-gradient(to right, #ff8a8a, #ff3b3b);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                    margin-bottom: 12px;
                }}

                .subtitle {{
                    color: var(--text-secondary);
                    font-size: 15px;
                    line-height: 1.6;
                    margin-bottom: 28px;
                }}

                .error-details {{
                    background: rgba(3, 7, 18, 0.6);
                    border: 1px solid var(--border);
                    border-radius: 16px;
                    padding: 20px;
                    margin-bottom: 28px;
                }}

                .details-header {{
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 12px;
                    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
                    padding-bottom: 8px;
                    font-size: 13px;
                    font-weight: 600;
                    color: var(--text-secondary);
                }}

                .error-class {{
                    color: var(--red);
                    background: rgba(239, 68, 68, 0.1);
                    padding: 2px 8px;
                    border-radius: 6px;
                    font-family: 'Fira Code', monospace;
                }}

                .error-traceback {{
                    max-height: 220px;
                    overflow-y: auto;
                    font-family: 'Fira Code', monospace;
                    font-size: 12px;
                    color: #d1d5db;
                    line-height: 1.7;
                    white-space: pre-wrap;
                    padding-right: 8px;
                }}

                /* Scrollbar Customization */
                .error-traceback::-webkit-scrollbar {{
                    width: 6px;
                }}
                .error-traceback::-webkit-scrollbar-track {{
                    background: transparent;
                }}
                .error-traceback::-webkit-scrollbar-thumb {{
                    background: rgba(255, 255, 255, 0.15);
                    border-radius: 10px;
                }}
                .error-traceback::-webkit-scrollbar-thumb:hover {{
                    background: rgba(255, 255, 255, 0.3);
                }}

                .actions {{
                    display: flex;
                    gap: 16px;
                    flex-wrap: wrap;
                }}

                .btn {{
                    font-family: 'Plus Jakarta Sans', sans-serif;
                    display: inline-flex;
                    align-items: center;
                    justify-content: center;
                    gap: 8px;
                    padding: 12px 24px;
                    border-radius: 12px;
                    text-decoration: none;
                    font-weight: 600;
                    font-size: 14px;
                    transition: all 0.2s ease;
                    cursor: pointer;
                    border: none;
                }}

                .btn-primary {{
                    background: linear-gradient(135deg, var(--blue), #1d4ed8);
                    color: white;
                    box-shadow: 0 4px 12px var(--blue-glow);
                }}

                .btn-primary:hover {{
                    transform: translateY(-2px);
                    box-shadow: 0 6px 16px rgba(59, 130, 246, 0.4);
                }}

                .btn-secondary {{
                    background: rgba(255, 255, 255, 0.05);
                    color: var(--text);
                    border: 1px solid var(--border);
                }}

                .btn-secondary:hover {{
                    background: rgba(255, 255, 255, 0.1);
                    transform: translateY(-2px);
                }}
            </style>
        </head>
        <body>
            <div class="error-card">
                <div class="icon-container">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/>
                        <line x1="12" y1="9" x2="12" y2="13"/>
                        <line x1="12" y1="17" x2="12.01" y2="17"/>
                    </svg>
                </div>
                <h1>Ocorreu um Erro no Servidor</h1>
                <p class="subtitle">O sistema encontrou um comportamento inesperado ou erro de processamento interno. Os administradores já foram notificados com os detalhes abaixo.</p>
                
                <div class="error-details">
                    <div class="details-header">
                        <span>DETALHES DO EVENTO</span>
                        <span class="error-class">500 - Internal Server Error</span>
                    </div>
                    <div class="error-traceback">{html.escape(str(e))}<br><br>{html.escape(tb)}</div>
                </div>

                <div class="actions">
                    <a href="/" class="btn btn-primary">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                            <path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
                            <polyline points="9 22 9 12 15 12 15 22"/>
                        </svg>
                        Ir para o Início
                    </a>
                    <button onclick="window.location.reload();" class="btn btn-secondary">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/>
                        </svg>
                        Tentar Novamente
                    </button>
                </div>
            </div>
        </body>
        </html>
        """, 500


    # ── Register Blueprints ──────────────────────────────────
    from routes.credores import bp as bp_credores
    from routes.mural import bp as bp_mural
    from routes.calendario import bp as bp_calendario
    from routes.empenhos import bp as bp_empenhos
    from routes.kanban import bp as bp_kanban
    from routes.documentos import bp as bp_documentos
    from routes.documentos import bp_autentique
    from routes.all_routes import (
        bp_prazos,
        bp_protocolos,
        bp_rpas,
        bp_fornecimento,
        bp_pdf,
        bp_despesas,
        bp_cnpj,
        bp_ia,
        bp_config,
        bp_logs,
        bp_auth,
        bp_extratos,
        bp_empenho_assistente,
        bp_classificador,
    )

    _log_startup("Registrando blueprints no aplicativo Flask...")
    app.register_blueprint(bp_credores)
    app.register_blueprint(bp_mural)
    app.register_blueprint(bp_calendario)
    app.register_blueprint(bp_empenhos)
    app.register_blueprint(bp_kanban)
    app.register_blueprint(bp_documentos)
    app.register_blueprint(bp_autentique)
    app.register_blueprint(bp_prazos)
    app.register_blueprint(bp_protocolos)
    app.register_blueprint(bp_rpas)
    app.register_blueprint(bp_fornecimento)
    app.register_blueprint(bp_pdf)
    app.register_blueprint(bp_despesas)
    app.register_blueprint(bp_cnpj)
    app.register_blueprint(bp_ia)
    app.register_blueprint(bp_config)
    app.register_blueprint(bp_logs)
    app.register_blueprint(bp_auth)
    app.register_blueprint(bp_extratos)
    app.register_blueprint(bp_empenho_assistente)
    app.register_blueprint(bp_classificador)
    _log_startup("Todos os 21 blueprints registrados com sucesso.")

    # Init auth hash (compat) + multi-user auth
    _log_startup("Inicializando hashes e sistema de autenticação multiusuário...")
    from routes.all_routes import init_auth_hash
    init_auth_hash(settings.admin_password)
    from routes.auth import init_auth_system
    init_auth_system(settings.admin_password, app)
    _log_startup("Sistema de autenticação inicializado.")

    return app, _preload_static_files, init_db, migrate_db


# ── MAIN ─────────────────────────────────────────────────────
if __name__ == "__main__":
    import socket
    import traceback

    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    boot_started_at = _time.perf_counter()

    try:
        app, _preload_static_files, init_db, migrate_db = create_app()

        _terminal_section("Sistema de Empenhos – Prefeitura Municipal de Inajá")
        _terminal_log("BOOT", "Iniciando servidor Flask...", "cyan")
        _log_startup("Iniciando banco de dados...")
        
        init_db()
        _terminal_log("BOOT", "Estrutura principal do banco verificada", "green")
        
        migrate_db()
        _terminal_log("BOOT", "Migrações do banco aplicadas", "green")
        
        _preload_static_files()

        if not settings.admin_password:
            _terminal_log("WARN", "ADM_PASSWORD nao configurada em seu ambiente/.env! Utilizando senha administrativa padrao e secret_key estatica.", "yellow")
            _log_startup("Aviso: ADM_PASSWORD não configurada no ambiente/.env! Usando credenciais padrão.", "WARNING")

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
        _terminal_log("TIME", f"Startup concluído em {boot_elapsed_ms:.1f} ms", "magenta")
        _log_startup(f"Servidor Cérebro Municipal pronto. Startup concluído em {boot_elapsed_ms:.1f} ms. Local: http://localhost:{settings.port} | Rede: http://{local_ip}:{settings.port}")
        _terminal_log(
            "INFO", "Para encerrar: feche esta janela ou pressione Ctrl+C", "cyan"
        )

        if _GEVENT_AVAILABLE:
            from gevent.pywsgi import WSGIServer as _GeventServer
            _terminal_log("SERVER", "Usando gevent (SSE/streaming habilitado)", "green")
            _log_startup("Inicializando gevent WSGIServer...")
            _GeventServer(
                (settings.host, settings.port),
                app,
                log=None,
                error_log=None,
            ).serve_forever()
        else:
            import waitress
            _terminal_log("SERVER", "gevent nao encontrado, usando Waitress (SSE limitado)", "yellow")
            _log_startup("gevent não disponível, inicializando Waitress WSGI server...")
            waitress.serve(
                app,
                host=settings.host,
                port=settings.port,
                threads=24,
                connection_limit=2000,
                channel_timeout=300,
                cleanup_interval=10,
                asyncore_use_poll=True,
            )
    except Exception as e:
        tb = traceback.format_exc()
        _terminal_log("FATAL", f"Erro fatal ao iniciar servidor: {e}", "red")
        print(tb, file=sys.stderr)
        try:
            _log_startup(f"ERRO FATAL NO BOOT DO SERVIDOR: {e}\n{tb}", "CRITICAL")
        except Exception:
            pass
        sys.exit(1)
