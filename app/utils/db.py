"""
app/utils/db.py — Gerenciamento de conexão com banco de dados
"""

import sqlite3
import threading
from config import settings


DB_PATH = str(settings.db_path)

# Conexão thread-local
_db_local = threading.local()


def get_db():
    """
    Retorna conexão SQLite persistente por thread.
    PRAGMAs de performance aplicados em toda nova conexão.
    """
    db = getattr(_db_local, 'conn', None)
    if db is None:
        db = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10.0)
        db.row_factory = sqlite3.Row
        
        # PRAGMAs de performance
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA journal_mode=DELETE")
        db.execute("PRAGMA synchronous=NORMAL")
        db.execute("PRAGMA cache_size=-8000")
        db.execute("PRAGMA temp_store=MEMORY")
        db.execute("PRAGMA mmap_size=0")
        db.execute("PRAGMA auto_vacuum=INCREMENTAL")
        
        _db_local.conn = db
    
    return db


def init_db():
    """Inicializa o banco de dados com tabelas e índices."""
    conn = get_db()
    cur = conn.cursor()
    
    # Tabela: credores
    cur.execute("""
        CREATE TABLE IF NOT EXISTS credores (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            nome        TEXT    NOT NULL,
            valor       REAL    DEFAULT 0,
            descricao   TEXT,
            cnpj        TEXT,
            email       TEXT,
            tipo_valor  TEXT    DEFAULT 'FIXO',
            solicitacao TEXT,
            pagamento   TEXT,
            validade    TEXT,
            departamento TEXT,
            obs         TEXT,
            ativo       INTEGER DEFAULT 1
        )
    """)
    
    # Tabela: empenhos
    cur.execute("""
        CREATE TABLE IF NOT EXISTS empenhos (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            credor_id   INTEGER NOT NULL,
            ano         INTEGER NOT NULL,
            mes         INTEGER NOT NULL,
            empenhado   INTEGER DEFAULT 1,
            timestamp   TEXT,
            UNIQUE(credor_id, ano, mes),
            FOREIGN KEY(credor_id) REFERENCES credores(id)
        )
    """)
    
    # Tabela: logs
    cur.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            acao        TEXT    NOT NULL,
            credor_id   INTEGER,
            credor_nome TEXT,
            detalhes    TEXT,
            data        TEXT    DEFAULT (datetime('now', 'localtime'))
        )
    """)
    
    # Tabela: rpas
    cur.execute("""
        CREATE TABLE IF NOT EXISTS rpas (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_rpa           TEXT,
            nome_prestador       TEXT    NOT NULL,
            cpf_prestador        TEXT,
            endereco_prestador   TEXT,
            descricao_servico    TEXT,
            periodo_referencia   TEXT,
            carga_horaria        TEXT,
            local_execucao       TEXT,
            valor_bruto          REAL    DEFAULT 0,
            num_dependentes      INTEGER DEFAULT 0,
            pensao_alimenticia   REAL    DEFAULT 0,
            inss                 REAL    DEFAULT 0,
            iss                  REAL    DEFAULT 0,
            deducao_dependentes  REAL    DEFAULT 0,
            base_calculo_irrf    REAL    DEFAULT 0,
            aliquota_irrf        REAL    DEFAULT 0,
            parcela_deduzir_irrf REAL   DEFAULT 0,
            ir                   REAL    DEFAULT 0,
            valor_liquido        REAL    DEFAULT 0,
            observacoes          TEXT,
            data_emissao         TEXT,
            criado_em            TEXT    DEFAULT (datetime('now', 'localtime'))
        )
    """)
    
    # Tabela: kanban_tasks
    cur.execute("""
        CREATE TABLE IF NOT EXISTS kanban_tasks (
            id              TEXT    PRIMARY KEY,
            title           TEXT    NOT NULL,
            description     TEXT    DEFAULT '',
            status          TEXT    DEFAULT 'todo',
            priority        TEXT    DEFAULT 'medium',
            categoria       TEXT    DEFAULT '',
            data_vencimento TEXT    DEFAULT '',
            responsavel     TEXT    DEFAULT '',
            concluido_em    TEXT    DEFAULT '',
            criado_em       TEXT    DEFAULT (datetime('now', 'localtime')),
            atualizado_em   TEXT    DEFAULT (datetime('now', 'localtime'))
        )
    """)
    
    # Tabela: configuracoes
    cur.execute("""
        CREATE TABLE IF NOT EXISTS configuracoes (
            chave     TEXT PRIMARY KEY,
            valor     TEXT NOT NULL DEFAULT '',
            atualizado_em TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS documentos_centro (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_original    TEXT    NOT NULL,
            nome_arquivo     TEXT    NOT NULL,
            categoria        TEXT    NOT NULL,
            referencia       TEXT    DEFAULT '',
            descricao        TEXT    DEFAULT '',
            tamanho          INTEGER DEFAULT 0,
            extensao         TEXT    DEFAULT '',
            caminho_relativo TEXT    NOT NULL,
            criado_em        TEXT    DEFAULT (datetime('now', 'localtime'))
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS autentique_envios (
            id                             INTEGER PRIMARY KEY AUTOINCREMENT,
            documento_centro_id            INTEGER NOT NULL,
            autentique_document_id         TEXT    DEFAULT '',
            autentique_signature_public_id TEXT    DEFAULT '',
            documento_nome                 TEXT    DEFAULT '',
            signatario_nome                TEXT    NOT NULL,
            signatario_phone               TEXT    NOT NULL,
            status                         TEXT    DEFAULT 'pendente',
            delivery_method                TEXT    DEFAULT 'DELIVERY_METHOD_WHATSAPP',
            assinatura_link                TEXT    DEFAULT '',
            webhook_evento                 TEXT    DEFAULT '',
            webhook_payload                TEXT    DEFAULT '',
            assinado_doc_id                INTEGER,
            assinado_em                    TEXT    DEFAULT '',
            criado_em                      TEXT    DEFAULT (datetime('now', 'localtime')),
            atualizado_em                  TEXT    DEFAULT (datetime('now', 'localtime'))
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS autentique_contatos (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            nome          TEXT    NOT NULL,
            phone         TEXT    NOT NULL UNIQUE,
            criado_em     TEXT    DEFAULT (datetime('now', 'localtime')),
            atualizado_em TEXT    DEFAULT (datetime('now', 'localtime'))
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS empenho_assistente_historico (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            action            TEXT    NOT NULL,
            payload_json      TEXT    NOT NULL DEFAULT '{}',
            resultado_json    TEXT    NOT NULL DEFAULT '{}',
            campos_json       TEXT    NOT NULL DEFAULT '{}',
            checklist_json    TEXT    NOT NULL DEFAULT '{}',
            descricao_base    TEXT    DEFAULT '',
            descricao_melhorada TEXT  DEFAULT '',
            diff_json         TEXT    NOT NULL DEFAULT '{}',
            model             TEXT    DEFAULT '',
            cached            INTEGER DEFAULT 0,
            criado_em         TEXT    DEFAULT (datetime('now', 'localtime'))
        )
    """)
    
    # Criar índices
    ensure_db_indexes(cur)
    
    conn.commit()


def ensure_db_indexes(cur):
    """Cria índices para otimização de queries."""
    cur.execute("CREATE INDEX IF NOT EXISTS idx_empenhos_credor ON empenhos(credor_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_empenhos_ano_mes ON empenhos(ano, mes)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_empenhos_ano_mes_empenhado ON empenhos(ano, mes, empenhado)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_credores_departamento ON credores(departamento)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_credores_nome ON credores(nome)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_credores_ativo ON credores(ativo)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_docs_categoria ON documentos_centro(categoria)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_docs_referencia ON documentos_centro(referencia)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_docs_criado_em ON documentos_centro(criado_em)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_docs_categoria_ref ON documentos_centro(categoria, referencia)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_empenho_hist_action ON empenho_assistente_historico(action)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_empenho_hist_created ON empenho_assistente_historico(criado_em)")
