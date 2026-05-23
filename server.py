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
    app.secret_key = settings.admin_password or os.urandom(32).hex()
    app.config["SESSION_COOKIE_NAME"] = "inaja_sid"
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

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
            "CREATE INDEX IF NOT EXISTS idx_kanban_tasks_dates ON kanban_tasks(atualizado_em, criado_em)",
            "CREATE INDEX IF NOT EXISTS idx_protocolos_status ON protocolos(status)",
            "CREATE INDEX IF NOT EXISTS idx_protocolos_tipo ON protocolos(tipo)",
            "CREATE INDEX IF NOT EXISTS idx_protocolos_direcao ON protocolos(direcao)",
            "CREATE INDEX IF NOT EXISTS idx_prazos_filtro ON prazos(resolvido, data_limite)",
            "CREATE INDEX IF NOT EXISTS idx_prazos_data_limite ON prazos(data_limite)",
            "CREATE INDEX IF NOT EXISTS idx_classificador_despesa_item ON classificador_despesa_historico(item)",
            "CREATE INDEX IF NOT EXISTS idx_classificador_despesa_created ON classificador_despesa_historico(criado_em)",
        ]:
            try:
                cur.execute(sql)
            except Exception:
                pass

    def migrate_db():
        conn = get_db()
        cur = conn.cursor()
        
        # 1. Base Table Creation (without _contents tables)
        for sql in [
            "CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, acao TEXT NOT NULL, credor_id INTEGER, credor_nome TEXT, detalhes TEXT, data TEXT DEFAULT (datetime('now', 'localtime')), FOREIGN KEY(credor_id) REFERENCES credores(id) ON DELETE SET NULL)",
            "CREATE TABLE IF NOT EXISTS rpas (id INTEGER PRIMARY KEY AUTOINCREMENT, numero_rpa TEXT, nome_prestador TEXT NOT NULL, cpf_prestador TEXT, endereco_prestador TEXT, descricao_servico TEXT, periodo_referencia TEXT, carga_horaria TEXT, local_execucao TEXT, valor_bruto REAL DEFAULT 0, num_dependentes INTEGER DEFAULT 0, pensao_alimenticia REAL DEFAULT 0, inss REAL DEFAULT 0, iss REAL DEFAULT 0, deducao_dependentes REAL DEFAULT 0, base_calculo_irrf REAL DEFAULT 0, aliquota_irrf REAL DEFAULT 0, parcela_deduzir_irrf REAL DEFAULT 0, ir REAL DEFAULT 0, valor_liquido REAL DEFAULT 0, observacoes TEXT, data_emissao TEXT, criado_em TEXT DEFAULT (datetime('now', 'localtime')))",
            "CREATE TABLE IF NOT EXISTS empenhos_importacoes (id INTEGER PRIMARY KEY AUTOINCREMENT, periodo TEXT NOT NULL, descricao TEXT, arquivo TEXT, total_rows INTEGER DEFAULT 0, importado_em TEXT)",
            "CREATE TABLE IF NOT EXISTS empenhos_linhas (id INTEGER PRIMARY KEY AUTOINCREMENT, importacao_id INTEGER NOT NULL REFERENCES empenhos_importacoes(id) ON DELETE CASCADE, dados TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS documentos_centro (id INTEGER PRIMARY KEY AUTOINCREMENT, nome_original TEXT NOT NULL, nome_arquivo TEXT NOT NULL, categoria TEXT NOT NULL, referencia TEXT DEFAULT '', descricao TEXT DEFAULT '', tamanho INTEGER DEFAULT 0, extensao TEXT DEFAULT '', caminho_relativo TEXT NOT NULL, criado_em TEXT DEFAULT (datetime('now', 'localtime')))",
            "CREATE TABLE IF NOT EXISTS autentique_envios (id INTEGER PRIMARY KEY AUTOINCREMENT, documento_centro_id INTEGER NOT NULL, autentique_document_id TEXT DEFAULT '', autentique_signature_public_id TEXT DEFAULT '', documento_nome TEXT DEFAULT '', signatario_nome TEXT NOT NULL, signatario_phone TEXT NOT NULL, status TEXT DEFAULT 'pendente', delivery_method TEXT DEFAULT 'DELIVERY_METHOD_WHATSAPP', assinatura_link TEXT DEFAULT '', webhook_evento TEXT DEFAULT '', webhook_payload TEXT DEFAULT '', assinado_doc_id INTEGER, assinado_em TEXT DEFAULT '', criado_em TEXT DEFAULT (datetime('now', 'localtime')), atualizado_em TEXT DEFAULT (datetime('now', 'localtime')), FOREIGN KEY(documento_centro_id) REFERENCES documentos_centro(id) ON DELETE CASCADE, FOREIGN KEY(assinado_doc_id) REFERENCES documentos_centro(id) ON DELETE SET NULL)",
            "CREATE TABLE IF NOT EXISTS autentique_contatos (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL, phone TEXT NOT NULL UNIQUE, criado_em TEXT DEFAULT (datetime('now', 'localtime')), atualizado_em TEXT DEFAULT (datetime('now', 'localtime')))",
            "CREATE TABLE IF NOT EXISTS despesas_importacoes (id INTEGER PRIMARY KEY AUTOINCREMENT, periodo TEXT NOT NULL, descricao TEXT, arquivo TEXT, total_rows INTEGER DEFAULT 0, colunas TEXT, importado_em TEXT)",
            "CREATE TABLE IF NOT EXISTS despesas_linhas (id INTEGER PRIMARY KEY AUTOINCREMENT, importacao_id INTEGER NOT NULL REFERENCES despesas_importacoes(id) ON DELETE CASCADE, dados TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS kanban_attachments (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL REFERENCES kanban_tasks(id) ON DELETE CASCADE, file_name TEXT NOT NULL, mime_type TEXT DEFAULT 'application/octet-stream', file_size INTEGER DEFAULT 0, criado_em TEXT DEFAULT (datetime('now','localtime')))",
            "CREATE TABLE IF NOT EXISTS prazos (id INTEGER PRIMARY KEY AUTOINCREMENT, titulo TEXT NOT NULL, descricao TEXT DEFAULT '', data_limite TEXT NOT NULL, categoria TEXT DEFAULT 'geral', resolvido INTEGER DEFAULT 0, criado_em TEXT DEFAULT (datetime('now','localtime')))",
            "CREATE TABLE IF NOT EXISTS protocolos (id INTEGER PRIMARY KEY AUTOINCREMENT, numero TEXT NOT NULL UNIQUE, tipo TEXT NOT NULL, direcao TEXT DEFAULT 'recebido', origem_destino TEXT DEFAULT '', assunto TEXT NOT NULL, data_protocolo TEXT NOT NULL, prazo_resposta TEXT DEFAULT '', status TEXT DEFAULT 'recebido', observacoes TEXT DEFAULT '', doc_id INTEGER, criado_em TEXT DEFAULT (datetime('now','localtime')), FOREIGN KEY(doc_id) REFERENCES documentos_centro(id) ON DELETE SET NULL)",
            "CREATE TABLE IF NOT EXISTS protocolo_anexos (id INTEGER PRIMARY KEY AUTOINCREMENT, protocolo_id INTEGER NOT NULL REFERENCES protocolos(id) ON DELETE CASCADE, file_name TEXT NOT NULL, mime_type TEXT DEFAULT 'application/octet-stream', file_size INTEGER DEFAULT 0, criado_em TEXT DEFAULT (datetime('now','localtime')))",
        ]:
            cur.execute(sql)

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
                    except Exception as e:
                        app.logger.warning(f"Erro ao migrar foreign keys da tabela {table_name}: {e}")

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
            try:
                cur.execute("ALTER TABLE kanban_attachments RENAME TO kanban_attachments_old")
                cur.execute("CREATE TABLE kanban_attachments (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL REFERENCES kanban_tasks(id) ON DELETE CASCADE, file_name TEXT NOT NULL, mime_type TEXT DEFAULT 'application/octet-stream', file_size INTEGER DEFAULT 0, criado_em TEXT DEFAULT (datetime('now','localtime')))")
                cur.execute("CREATE TABLE IF NOT EXISTS kanban_attachment_contents (attachment_id INTEGER PRIMARY KEY REFERENCES kanban_attachments(id) ON DELETE CASCADE, content BLOB NOT NULL)")
                cur.execute("INSERT INTO kanban_attachments (id, task_id, file_name, mime_type, file_size, criado_em) SELECT id, task_id, file_name, mime_type, file_size, criado_em FROM kanban_attachments_old")
                cur.execute("INSERT OR IGNORE INTO kanban_attachment_contents (attachment_id, content) SELECT id, content FROM kanban_attachments_old WHERE content IS NOT NULL")
                cur.execute("DROP TABLE kanban_attachments_old")
            except Exception as e:
                app.logger.warning(f"Erro ao dividir tabela kanban_attachments: {e}")
        else:
            cur.execute("CREATE TABLE IF NOT EXISTS kanban_attachment_contents (attachment_id INTEGER PRIMARY KEY REFERENCES kanban_attachments(id) ON DELETE CASCADE, content BLOB NOT NULL)")
            cur.execute("PRAGMA foreign_key_list(kanban_attachment_contents)")
            fks = [dict(r) for r in cur.fetchall()]
            if any(fk["table"] == "kanban_attachments_old" for fk in fks):
                try:
                    cur.execute("ALTER TABLE kanban_attachment_contents RENAME TO kanban_attachment_contents_old")
                    cur.execute("CREATE TABLE kanban_attachment_contents (attachment_id INTEGER PRIMARY KEY REFERENCES kanban_attachments(id) ON DELETE CASCADE, content BLOB NOT NULL)")
                    cur.execute("INSERT INTO kanban_attachment_contents (attachment_id, content) SELECT attachment_id, content FROM kanban_attachment_contents_old")
                    cur.execute("DROP TABLE kanban_attachment_contents_old")
                except Exception as e:
                    app.logger.warning(f"Erro ao corrigir FK de kanban_attachment_contents: {e}")

        # Split BLOB table: protocolo_anexos
        cur.execute("PRAGMA table_info(protocolo_anexos)")
        cols = [r["name"] for r in cur.fetchall()]
        if "content" in cols:
            try:
                cur.execute("ALTER TABLE protocolo_anexos RENAME TO protocolo_anexos_old")
                cur.execute("CREATE TABLE protocolo_anexos (id INTEGER PRIMARY KEY AUTOINCREMENT, protocolo_id INTEGER NOT NULL REFERENCES protocolos(id) ON DELETE CASCADE, file_name TEXT NOT NULL, mime_type TEXT DEFAULT 'application/octet-stream', file_size INTEGER DEFAULT 0, criado_em TEXT DEFAULT (datetime('now','localtime')))")
                cur.execute("CREATE TABLE IF NOT EXISTS protocolo_anexo_contents (anexo_id INTEGER PRIMARY KEY REFERENCES protocolo_anexos(id) ON DELETE CASCADE, content BLOB NOT NULL)")
                cur.execute("INSERT INTO protocolo_anexos (id, protocolo_id, file_name, mime_type, file_size, criado_em) SELECT id, protocolo_id, file_name, mime_type, file_size, criado_em FROM protocolo_anexos_old")
                cur.execute("INSERT OR IGNORE INTO protocolo_anexo_contents (anexo_id, content) SELECT id, content FROM protocolo_anexos_old WHERE content IS NOT NULL")
                cur.execute("DROP TABLE protocolo_anexos_old")
            except Exception as e:
                app.logger.warning(f"Erro ao dividir tabela protocolo_anexos: {e}")
        else:
            cur.execute("CREATE TABLE IF NOT EXISTS protocolo_anexo_contents (anexo_id INTEGER PRIMARY KEY REFERENCES protocolo_anexos(id) ON DELETE CASCADE, content BLOB NOT NULL)")
            cur.execute("PRAGMA foreign_key_list(protocolo_anexo_contents)")
            fks = [dict(r) for r in cur.fetchall()]
            if any(fk["table"] == "protocolo_anexos_old" for fk in fks):
                try:
                    cur.execute("ALTER TABLE protocolo_anexo_contents RENAME TO protocolo_anexo_contents_old")
                    cur.execute("CREATE TABLE protocolo_anexo_contents (anexo_id INTEGER PRIMARY KEY REFERENCES protocolo_anexos(id) ON DELETE CASCADE, content BLOB NOT NULL)")
                    cur.execute("INSERT INTO protocolo_anexo_contents (anexo_id, content) SELECT anexo_id, content FROM protocolo_anexo_contents_old")
                    cur.execute("DROP TABLE protocolo_anexo_contents_old")
                except Exception as e:
                    app.logger.warning(f"Erro ao corrigir FK de protocolo_anexo_contents: {e}")

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

        # Multi-user auth table
        cur.execute("""CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT DEFAULT '',
            login TEXT NOT NULL UNIQUE,
            senha_hash TEXT NOT NULL,
            senha_plana TEXT DEFAULT '',
            nivel TEXT NOT NULL DEFAULT 'operador'
                CHECK (nivel IN ('admin','operador','leitor')),
            ativo INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT DEFAULT (datetime('now','localtime')),
            atualizado_em TEXT DEFAULT (datetime('now','localtime'))
        )""")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_usuarios_login ON usuarios(login)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_usuarios_nivel ON usuarios(nivel)")
        conn.commit()

    def init_db():
        conn = get_db()
        cur = conn.cursor()
        for sql in [
            "CREATE TABLE IF NOT EXISTS credores (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL, valor REAL DEFAULT 0, descricao TEXT, cnpj TEXT, email TEXT, tipo_valor TEXT DEFAULT 'FIXO', solicitacao TEXT, pagamento TEXT, validade TEXT, departamento TEXT, obs TEXT, ativo INTEGER DEFAULT 1)",
            "CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, acao TEXT NOT NULL, credor_id INTEGER, credor_nome TEXT, detalhes TEXT, data TEXT DEFAULT (datetime('now', 'localtime')), FOREIGN KEY(credor_id) REFERENCES credores(id) ON DELETE SET NULL)",
            "CREATE TABLE IF NOT EXISTS empenhos (id INTEGER PRIMARY KEY AUTOINCREMENT, credor_id INTEGER NOT NULL, ano INTEGER NOT NULL, mes INTEGER NOT NULL, empenhado INTEGER DEFAULT 1, timestamp TEXT, UNIQUE(credor_id, ano, mes), FOREIGN KEY(credor_id) REFERENCES credores(id) ON DELETE CASCADE)",
            "CREATE TABLE IF NOT EXISTS rpas (id INTEGER PRIMARY KEY AUTOINCREMENT, numero_rpa TEXT, nome_prestador TEXT NOT NULL, cpf_prestador TEXT, endereco_prestador TEXT, descricao_servico TEXT, periodo_referencia TEXT, carga_horaria TEXT, local_execucao TEXT, valor_bruto REAL DEFAULT 0, num_dependentes INTEGER DEFAULT 0, pensao_alimenticia REAL DEFAULT 0, inss REAL DEFAULT 0, iss REAL DEFAULT 0, deducao_dependentes REAL DEFAULT 0, base_calculo_irrf REAL DEFAULT 0, aliquota_irrf REAL DEFAULT 0, parcela_deduzir_irrf REAL DEFAULT 0, ir REAL DEFAULT 0, valor_liquido REAL DEFAULT 0, observacoes TEXT, data_emissao TEXT, criado_em TEXT DEFAULT (datetime('now', 'localtime')))",
            "CREATE TABLE IF NOT EXISTS kanban_tasks (id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT DEFAULT '', status TEXT DEFAULT 'todo', priority TEXT DEFAULT 'medium', concluido_em TEXT DEFAULT '', criado_em TEXT DEFAULT (datetime('now', 'localtime')), atualizado_em TEXT DEFAULT (datetime('now', 'localtime')))",
            "CREATE TABLE IF NOT EXISTS kanban_attachments (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL REFERENCES kanban_tasks(id) ON DELETE CASCADE, file_name TEXT NOT NULL, mime_type TEXT DEFAULT 'application/octet-stream', file_size INTEGER DEFAULT 0, criado_em TEXT DEFAULT (datetime('now','localtime')))",
            "CREATE TABLE IF NOT EXISTS fornecimento_dados (id INTEGER PRIMARY KEY AUTOINCREMENT, tipo TEXT NOT NULL, valor TEXT NOT NULL, criado_em TEXT DEFAULT (datetime('now', 'localtime')), UNIQUE(tipo, valor))",
            "CREATE TABLE IF NOT EXISTS configuracoes (chave TEXT PRIMARY KEY, valor TEXT NOT NULL DEFAULT '', atualizado_em TEXT DEFAULT (datetime('now', 'localtime')))",
            "CREATE TABLE IF NOT EXISTS documentos_centro (id INTEGER PRIMARY KEY AUTOINCREMENT, nome_original TEXT NOT NULL, nome_arquivo TEXT NOT NULL, categoria TEXT NOT NULL, referencia TEXT DEFAULT '', descricao TEXT DEFAULT '', tamanho INTEGER DEFAULT 0, extensao TEXT DEFAULT '', caminho_relativo TEXT NOT NULL, criado_em TEXT DEFAULT (datetime('now', 'localtime')))",
            "CREATE TABLE IF NOT EXISTS autentique_envios (id INTEGER PRIMARY KEY AUTOINCREMENT, documento_centro_id INTEGER NOT NULL, autentique_document_id TEXT DEFAULT '', autentique_signature_public_id TEXT DEFAULT '', documento_nome TEXT DEFAULT '', signatario_nome TEXT NOT NULL, signatario_phone TEXT NOT NULL, status TEXT DEFAULT 'pendente', delivery_method TEXT DEFAULT 'DELIVERY_METHOD_WHATSAPP', assinatura_link TEXT DEFAULT '', webhook_evento TEXT DEFAULT '', webhook_payload TEXT DEFAULT '', assinado_doc_id INTEGER, assinado_em TEXT DEFAULT '', criado_em TEXT DEFAULT (datetime('now', 'localtime')), atualizado_em TEXT DEFAULT (datetime('now', 'localtime')), FOREIGN KEY(documento_centro_id) REFERENCES documentos_centro(id) ON DELETE CASCADE, FOREIGN KEY(assinado_doc_id) REFERENCES documentos_centro(id) ON DELETE SET NULL)",
            "CREATE TABLE IF NOT EXISTS autentique_contatos (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL, phone TEXT NOT NULL UNIQUE, criado_em TEXT DEFAULT (datetime('now', 'localtime')), atualizado_em TEXT DEFAULT (datetime('now', 'localtime')))",
            "CREATE TABLE IF NOT EXISTS empenho_assistente_historico (id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT NOT NULL, payload_json TEXT NOT NULL DEFAULT '{}', resultado_json TEXT NOT NULL DEFAULT '{}', campos_json TEXT NOT NULL DEFAULT '{}', checklist_json TEXT NOT NULL DEFAULT '{}', descricao_base TEXT DEFAULT '', descricao_melhorada TEXT DEFAULT '', diff_json TEXT NOT NULL DEFAULT '{}', model TEXT DEFAULT '', cached INTEGER DEFAULT 0, criado_em TEXT DEFAULT (datetime('now', 'localtime')))",
            "CREATE TABLE IF NOT EXISTS classificador_despesa_historico (id INTEGER PRIMARY KEY AUTOINCREMENT, item TEXT NOT NULL, codigo_completo TEXT NOT NULL DEFAULT '', grupo TEXT DEFAULT '', modalidade TEXT DEFAULT '', elemento TEXT DEFAULT '', subelemento TEXT DEFAULT '', justificativa TEXT DEFAULT '', ponto_atencao TEXT DEFAULT '', confianca REAL DEFAULT 0.0, resultado_json TEXT NOT NULL DEFAULT '{}', model TEXT DEFAULT '', cached INTEGER DEFAULT 0, criado_em TEXT DEFAULT (datetime('now', 'localtime')))",
            "CREATE TABLE IF NOT EXISTS prazos (id INTEGER PRIMARY KEY AUTOINCREMENT, titulo TEXT NOT NULL, descricao TEXT DEFAULT '', data_limite TEXT NOT NULL, categoria TEXT DEFAULT 'geral', resolvido INTEGER DEFAULT 0, criado_em TEXT DEFAULT (datetime('now','localtime')))",
            "CREATE TABLE IF NOT EXISTS protocolos (id INTEGER PRIMARY KEY AUTOINCREMENT, numero TEXT NOT NULL UNIQUE, tipo TEXT NOT NULL, direcao TEXT DEFAULT 'recebido', origem_destino TEXT DEFAULT '', assunto TEXT NOT NULL, data_protocolo TEXT NOT NULL, prazo_resposta TEXT DEFAULT '', status TEXT DEFAULT 'recebido', observacoes TEXT DEFAULT '', doc_id INTEGER, criado_em TEXT DEFAULT (datetime('now','localtime')), FOREIGN KEY(doc_id) REFERENCES documentos_centro(id) ON DELETE SET NULL)",
            "CREATE TABLE IF NOT EXISTS protocolo_anexos (id INTEGER PRIMARY KEY AUTOINCREMENT, protocolo_id INTEGER NOT NULL REFERENCES protocolos(id) ON DELETE CASCADE, file_name TEXT NOT NULL, mime_type TEXT DEFAULT 'application/octet-stream', file_size INTEGER DEFAULT 0, criado_em TEXT DEFAULT (datetime('now','localtime')))",
        ]:
            cur.execute(sql)

        count = cur.execute("SELECT COUNT(*) FROM credores").fetchone()[0]
        if count == 0 and os.path.exists(DATA_JS):
            print("Populando banco com dados do data.js...")
            _seed_from_data_js(cur)
        ensure_db_indexes(cur)
        conn.commit()

        try:
            conn.execute("VACUUM")
        except Exception:
            pass

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

    _SKIP_EXTS = {".db", ".db-shm", ".db-wal", ".pyc", ".pyo", ".log", ".bat"}
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
            f"{enc_count} arquivos com versão {enc_name} prontos em {elapsed_ms:.1f} ms",
            "green",
        )

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
    @app.route("/")
    def index():
        resp = _serve_cached("/index.html", "no-cache, no-store, must-revalidate")
        if resp:
            return resp
        r = send_file(os.path.join(BASE_DIR, "index.html"))
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

    @app.errorhandler(500)
    def server_error(e):
        app.logger.error("500 em %s: %s", request.path, e)
        if request.path.startswith("/api/"):
            return jsonify({"error": "Erro interno do servidor", "detail": str(e)}), 500
        return str(e), 500

    # ── Register Blueprints ──────────────────────────────────
    from routes.credores import bp as bp_credores
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

    app.register_blueprint(bp_credores)
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

    # Init auth hash (compat) + multi-user auth
    from routes.all_routes import init_auth_hash
    init_auth_hash(settings.admin_password)
    from routes.auth import init_auth_system
    init_auth_system(settings.admin_password, app)

    return app, _preload_static_files, init_db, migrate_db


# ── MAIN ─────────────────────────────────────────────────────
if __name__ == "__main__":
    import socket

    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    boot_started_at = _time.perf_counter()

    app, _preload_static_files, init_db, migrate_db = create_app()

    _terminal_section("Sistema de Empenhos – Prefeitura Municipal de Inajá")
    _terminal_log("BOOT", "Iniciando servidor Flask...", "cyan")
    init_db()
    _terminal_log("BOOT", "Estrutura principal do banco verificada", "green")
    migrate_db()
    _terminal_log("BOOT", "Migrações do banco aplicadas", "green")
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
    _terminal_log("TIME", f"Startup concluído em {boot_elapsed_ms:.1f} ms", "magenta")
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
