import json
import os
import re
from config import settings
from database import ensure_db_indexes

DATA_JS = str(settings.data_js_path)

MIGRATIONS = [
    (1, 'Tabelas iniciais e índices', [
        """CREATE TABLE IF NOT EXISTS credores (
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
        )""",
        """CREATE TABLE IF NOT EXISTS logs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            acao        TEXT    NOT NULL,
            credor_id   INTEGER,
            credor_nome TEXT,
            detalhes    TEXT,
            data        TEXT    DEFAULT (datetime('now', 'localtime'))
        )""",
        """CREATE TABLE IF NOT EXISTS empenhos (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            credor_id   INTEGER NOT NULL,
            ano         INTEGER NOT NULL,
            mes         INTEGER NOT NULL,
            empenhado   INTEGER DEFAULT 1,
            timestamp   TEXT,
            UNIQUE(credor_id, ano, mes),
            FOREIGN KEY(credor_id) REFERENCES credores(id)
        )""",
        """CREATE TABLE IF NOT EXISTS rpas (
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
            parcela_deduzir_irrf REAL    DEFAULT 0,
            ir                   REAL    DEFAULT 0,
            valor_liquido        REAL    DEFAULT 0,
            observacoes          TEXT,
            data_emissao         TEXT,
            criado_em            TEXT    DEFAULT (datetime('now', 'localtime'))
        )""",
        """CREATE TABLE IF NOT EXISTS kanban_tasks (
            id          TEXT    PRIMARY KEY,
            title       TEXT    NOT NULL,
            description TEXT    DEFAULT '',
            status      TEXT    DEFAULT 'todo',
            priority    TEXT    DEFAULT 'medium',
            categoria   TEXT    DEFAULT '',
            data_vencimento TEXT DEFAULT '',
            responsavel TEXT    DEFAULT '',
            concluido_em TEXT   DEFAULT '',
            criado_em   TEXT    DEFAULT (datetime('now', 'localtime')),
            atualizado_em TEXT  DEFAULT (datetime('now', 'localtime'))
        )""",
        """CREATE TABLE IF NOT EXISTS kanban_attachments (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id         TEXT    NOT NULL
                            REFERENCES kanban_tasks(id) ON DELETE CASCADE,
            file_name       TEXT    NOT NULL,
            mime_type       TEXT    DEFAULT 'application/octet-stream',
            file_size       INTEGER DEFAULT 0,
            content         BLOB    NOT NULL,
            criado_em       TEXT    DEFAULT (datetime('now','localtime'))
        )""",
        """CREATE TABLE IF NOT EXISTS fornecimento_dados (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo      TEXT    NOT NULL,
            valor     TEXT    NOT NULL,
            criado_em TEXT    DEFAULT (datetime('now', 'localtime')),
            UNIQUE(tipo, valor)
        )""",
        """CREATE TABLE IF NOT EXISTS configuracoes (
            chave     TEXT PRIMARY KEY,
            valor     TEXT NOT NULL DEFAULT '',
            atualizado_em TEXT DEFAULT (datetime('now', 'localtime'))
        )""",
        """CREATE TABLE IF NOT EXISTS documentos_centro (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_original   TEXT    NOT NULL,
            nome_arquivo    TEXT    NOT NULL,
            categoria       TEXT    NOT NULL,
            referencia      TEXT    DEFAULT '',
            descricao       TEXT    DEFAULT '',
            tamanho         INTEGER DEFAULT 0,
            extensao        TEXT    DEFAULT '',
            caminho_relativo TEXT   NOT NULL,
            criado_em       TEXT    DEFAULT (datetime('now', 'localtime'))
        )""",
        """CREATE TABLE IF NOT EXISTS autentique_envios (
            id                           INTEGER PRIMARY KEY AUTOINCREMENT,
            documento_centro_id          INTEGER NOT NULL,
            autentique_document_id       TEXT    DEFAULT '',
            autentique_signature_public_id TEXT  DEFAULT '',
            documento_nome               TEXT    DEFAULT '',
            signatario_nome              TEXT    NOT NULL,
            signatario_phone             TEXT    NOT NULL,
            status                       TEXT    DEFAULT 'pendente',
            delivery_method              TEXT    DEFAULT 'DELIVERY_METHOD_WHATSAPP',
            assinatura_link              TEXT    DEFAULT '',
            webhook_evento               TEXT    DEFAULT '',
            webhook_payload              TEXT    DEFAULT '',
            assinado_doc_id              INTEGER,
            assinado_em                  TEXT    DEFAULT '',
            criado_em                    TEXT    DEFAULT (datetime('now', 'localtime')),
            atualizado_em                TEXT    DEFAULT (datetime('now', 'localtime'))
        )""",
        """CREATE TABLE IF NOT EXISTS autentique_contatos (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            nome            TEXT    NOT NULL,
            phone           TEXT    NOT NULL UNIQUE,
            criado_em       TEXT    DEFAULT (datetime('now', 'localtime')),
            atualizado_em   TEXT    DEFAULT (datetime('now', 'localtime'))
        )""",
        """CREATE TABLE IF NOT EXISTS empenhos_importacoes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            periodo     TEXT    NOT NULL,
            descricao   TEXT,
            arquivo     TEXT,
            total_rows  INTEGER DEFAULT 0,
            importado_em TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS empenhos_linhas (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            importacao_id   INTEGER NOT NULL
                            REFERENCES empenhos_importacoes(id) ON DELETE CASCADE,
            dados           TEXT    NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS despesas_importacoes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            periodo     TEXT    NOT NULL,
            descricao   TEXT,
            arquivo     TEXT,
            total_rows  INTEGER DEFAULT 0,
            colunas     TEXT,
            importado_em TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS despesas_linhas (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            importacao_id   INTEGER NOT NULL
                            REFERENCES despesas_importacoes(id) ON DELETE CASCADE,
            dados           TEXT    NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS prazos (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo      TEXT    NOT NULL,
            descricao   TEXT    DEFAULT '',
            data_limite TEXT    NOT NULL,
            categoria   TEXT    DEFAULT 'geral',
            resolvido   INTEGER DEFAULT 0,
            criado_em   TEXT    DEFAULT (datetime('now','localtime'))
        )""",
        """CREATE TABLE IF NOT EXISTS protocolos (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            numero          TEXT    NOT NULL UNIQUE,
            tipo            TEXT    NOT NULL,
            direcao         TEXT    DEFAULT 'recebido',
            origem_destino  TEXT    DEFAULT '',
            assunto         TEXT    NOT NULL,
            data_protocolo  TEXT    NOT NULL,
            prazo_resposta  TEXT    DEFAULT '',
            status          TEXT    DEFAULT 'recebido',
            observacoes     TEXT    DEFAULT '',
            doc_id          INTEGER,
            criado_em       TEXT    DEFAULT (datetime('now','localtime'))
        )""",
        """CREATE TABLE IF NOT EXISTS protocolo_anexos (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            protocolo_id    INTEGER NOT NULL
                            REFERENCES protocolos(id) ON DELETE CASCADE,
            file_name       TEXT    NOT NULL,
            mime_type       TEXT    DEFAULT 'application/octet-stream',
            file_size       INTEGER DEFAULT 0,
            content         BLOB    NOT NULL,
            criado_em       TEXT    DEFAULT (datetime('now','localtime'))
        )""",
    ]),
    (2, 'Colunas extras kanban (databases antigos)', [
        "ALTER TABLE kanban_tasks ADD COLUMN categoria TEXT DEFAULT ''",
        "ALTER TABLE kanban_tasks ADD COLUMN data_vencimento TEXT DEFAULT ''",
        "ALTER TABLE kanban_tasks ADD COLUMN responsavel TEXT DEFAULT ''",
        "ALTER TABLE kanban_tasks ADD COLUMN concluido_em TEXT DEFAULT ''",
    ]),
]


def run_migrations(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS _schema_version (
            version INTEGER PRIMARY KEY,
            description TEXT,
            applied_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    applied = {row[0] for row in conn.execute("SELECT version FROM _schema_version").fetchall()}
    for version, description, statements in MIGRATIONS:
        if version in applied:
            continue
        for sql in statements:
            try:
                conn.execute(sql)
            except Exception:
                pass
        conn.execute(
            "INSERT INTO _schema_version (version, description) VALUES (?, ?)",
            (version, description)
        )
    ensure_db_indexes(conn.cursor())
    conn.commit()


def seed_from_data_js(cur, conn):
    count = cur.execute("SELECT COUNT(*) FROM credores").fetchone()[0]
    if count == 0 and os.path.exists(DATA_JS):
        print("Populando banco com dados do data.js...")
        with open(DATA_JS, encoding='utf-8') as f:
            content = f.read()
        match = re.search(r'const CREDORES_FIXOS\s*=\s*(\[[\s\S]*?\]);', content)
        if not match:
            print("ATENÇÃO: Não foi possível ler o data.js para popular o banco.")
            return
        data = json.loads(match.group(1))
        for c in data:
            cur.execute("""
                INSERT INTO credores
                  (nome, valor, descricao, cnpj, email, tipo_valor, solicitacao, pagamento, departamento, obs)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (
                c.get('NOME', ''),
                float(c.get('VALOR') or 0),
                c.get('DESCRIÇÃO', ''),
                c.get('CNPJ', ''),
                c.get('EMAIL', ''),
                c.get('TIPO DE VALOR', 'FIXO'),
                str(c.get('SOLICITAÇÃO', '')),
                str(c.get('PAGAMENTO', '')),
                c.get('DEPARTAMENTO', ''),
                c.get('OBS', ''),
            ))
        conn.commit()
        print(f"  {len(data)} credores inseridos.")
