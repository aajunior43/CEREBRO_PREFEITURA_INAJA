import os
import sqlite3
import threading
import time as _time
from config import settings
from helpers import _terminal_log

BASE_DIR = str(settings.base_dir)
DB_PATH = str(settings.db_path)
DATA_JS = str(settings.data_js_path)
DOCUMENTS_DIR = os.path.join(BASE_DIR, 'documentos_centro')

os.makedirs(DOCUMENTS_DIR, exist_ok=True)

_db_local = threading.local()


def get_db():
    db = getattr(_db_local, 'conn', None)
    if db is None:
        started_at = _time.perf_counter()
        db = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10.0)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA journal_mode=DELETE")
        db.execute("PRAGMA synchronous=NORMAL")
        db.execute("PRAGMA cache_size=-8000")
        db.execute("PRAGMA temp_store=MEMORY")
        db.execute("PRAGMA mmap_size=0")
        db.execute("PRAGMA auto_vacuum=INCREMENTAL")
        _db_local.conn = db
        elapsed_ms = (_time.perf_counter() - started_at) * 1000
        _terminal_log('DB', f'Conexão SQLite pronta em {elapsed_ms:.1f} ms -> {DB_PATH}', 'green')
    return db


def close_db(exception=None):
    pass


def row_to_dict(row):
    return dict(row)


def ensure_db_indexes(cur):
    cur.execute("CREATE INDEX IF NOT EXISTS idx_empenhos_credor ON empenhos(credor_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_empenhos_ano_mes ON empenhos(ano, mes)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_empenhos_ano_mes_empenhado ON empenhos(ano, mes, empenhado)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_empenhos_credor_ano_mes ON empenhos(credor_id, ano, mes)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_credores_departamento ON credores(departamento)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_credores_nome ON credores(nome)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_credores_ativo ON credores(ativo)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_credores_tipo_valor ON credores(tipo_valor)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_credores_validade ON credores(validade)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_credores_cnpj ON credores(cnpj)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_credores_email ON credores(email)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_logs_acao ON logs(acao)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_logs_data ON logs(data)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_rpas_cpf ON rpas(cpf_prestador)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_rpas_periodo ON rpas(periodo_referencia)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_rpas_data_emissao ON rpas(data_emissao)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_docs_categoria ON documentos_centro(categoria)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_docs_referencia ON documentos_centro(referencia)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_docs_criado_em ON documentos_centro(criado_em)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_docs_categoria_ref ON documentos_centro(categoria, referencia)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_despesas_importacoes_periodo ON despesas_importacoes(periodo)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_despesas_linhas_importacao ON despesas_linhas(importacao_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_empenhos_importacoes_periodo ON empenhos_importacoes(periodo)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_empenhos_linhas_importacao ON empenhos_linhas(importacao_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_kanban_attach_task ON kanban_attachments(task_id)")
