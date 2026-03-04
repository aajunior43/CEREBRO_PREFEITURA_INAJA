"""
server.py — Servidor Flask + SQLite para o Sistema de Empenhos Mensais
Prefeitura Municipal de Inajá

Para iniciar: python server.py
Ou duplo clique em iniciar.bat
"""

import sqlite3
import json
import os
import re
import sys
import threading

from flask import Flask, request, jsonify, send_from_directory, send_file, Response


# ── Instala Flask se necessário ─────────────────────────────
try:
    import flask
except ImportError:
    print("Instalando Flask...")
    os.system(f'"{sys.executable}" -m pip install flask')
    import flask  # noqa

# ── Configurações ───────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, 'empenhos.db')
DATA_JS  = os.path.join(BASE_DIR, 'data.js')

app = Flask(__name__, static_folder=BASE_DIR)

# ── Banco de Dados ───────────────────────────────────────────
# Conexão thread-local reutilizada durante todo o ciclo de vida da requisição.
# Evita abrir/fechar conexão a cada chamada (crítico em ambientes OneDrive/rede).
_db_local = threading.local()

def get_db():
    """Retorna conexão SQLite persistente por thread (reutilizada entre requests)."""
    db = getattr(_db_local, 'conn', None)
    if db is None:
        db = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10.0)
        db.row_factory = sqlite3.Row
        _db_local.conn = db
    return db

@app.teardown_appcontext
def close_db(exception):
    # Conexão mantida aberta entre requisições para evitar overhead de re-abertura
    # (crítico em ambientes OneDrive onde abrir arquivo tem latência alta)
    pass

def migrate_db():
    """Aplica migrações no banco existente."""
    conn = get_db()
    cur = conn.cursor()
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
            parcela_deduzir_irrf REAL    DEFAULT 0,
            ir                   REAL    DEFAULT 0,
            valor_liquido        REAL    DEFAULT 0,
            observacoes          TEXT,
            data_emissao         TEXT,
            criado_em            TEXT    DEFAULT (datetime('now', 'localtime'))
        )
    """)
    # ── Empenhos (CSV histórico – Visualizador) ─────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS empenhos_importacoes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            periodo     TEXT    NOT NULL,
            descricao   TEXT,
            arquivo     TEXT,
            total_rows  INTEGER DEFAULT 0,
            importado_em TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS empenhos_linhas (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            importacao_id   INTEGER NOT NULL
                            REFERENCES empenhos_importacoes(id) ON DELETE CASCADE,
            dados           TEXT    NOT NULL
        )
    """)
    # ── Despesas da Prefeitura (CSV histórico) ──────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS despesas_importacoes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            periodo     TEXT    NOT NULL,
            descricao   TEXT,
            arquivo     TEXT,
            total_rows  INTEGER DEFAULT 0,
            colunas     TEXT,
            importado_em TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS despesas_linhas (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            importacao_id   INTEGER NOT NULL
                            REFERENCES despesas_importacoes(id) ON DELETE CASCADE,
            dados           TEXT    NOT NULL
        )
    """)
    conn.commit()


def init_db():
    """Cria as tabelas e popula credores iniciais a partir do data.js."""
    conn = get_db()
    cur  = conn.cursor()

    # PRAGMAs de performance — executados uma única vez na inicialização
    # NOTA: WAL mode DESABILITADO — OneDrive não sincroniza .db-wal corretamente
    cur.execute("PRAGMA journal_mode=DELETE")    # Modo padrão: dados sempre no .db principal
    cur.execute("PRAGMA synchronous=NORMAL")      # Mais rápido; seguro para uso local
    cur.execute("PRAGMA cache_size=-8000")       # 8MB de cache em memória
    cur.execute("PRAGMA temp_store=MEMORY")      # Tabelas temporárias em RAM
    cur.execute("PRAGMA mmap_size=134217728")    # Memory-map de 128MB
    conn.commit()

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

    cur.execute("""
        CREATE TABLE IF NOT EXISTS rpas (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_rpa          TEXT,
            nome_prestador      TEXT    NOT NULL,
            cpf_prestador       TEXT,
            endereco_prestador  TEXT,
            descricao_servico   TEXT,
            periodo_referencia  TEXT,
            carga_horaria       TEXT,
            local_execucao      TEXT,
            valor_bruto         REAL    DEFAULT 0,
            num_dependentes     INTEGER DEFAULT 0,
            pensao_alimenticia  REAL    DEFAULT 0,
            inss                REAL    DEFAULT 0,
            iss                 REAL    DEFAULT 0,
            deducao_dependentes REAL    DEFAULT 0,
            base_calculo_irrf   REAL    DEFAULT 0,
            aliquota_irrf       REAL    DEFAULT 0,
            parcela_deduzir_irrf REAL   DEFAULT 0,
            ir                  REAL    DEFAULT 0,
            valor_liquido       REAL    DEFAULT 0,
            observacoes         TEXT,
            data_emissao        TEXT,
            criado_em           TEXT    DEFAULT (datetime('now', 'localtime'))
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS kanban_tasks (
            id          TEXT    PRIMARY KEY,
            title       TEXT    NOT NULL,
            description TEXT    DEFAULT '',
            status      TEXT    DEFAULT 'todo',
            priority    TEXT    DEFAULT 'medium',
            criado_em   TEXT    DEFAULT (datetime('now', 'localtime')),
            atualizado_em TEXT  DEFAULT (datetime('now', 'localtime'))
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS fornecimento_dados (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo      TEXT    NOT NULL,
            valor     TEXT    NOT NULL,
            criado_em TEXT    DEFAULT (datetime('now', 'localtime')),
            UNIQUE(tipo, valor)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS configuracoes (
            chave     TEXT PRIMARY KEY,
            valor     TEXT NOT NULL DEFAULT '',
            atualizado_em TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)

    # Popula credores iniciais se a tabela estiver vazia
    count = cur.execute("SELECT COUNT(*) FROM credores").fetchone()[0]
    if count == 0 and os.path.exists(DATA_JS):
        print("Populando banco com dados do data.js...")
        _seed_from_data_js(cur)

    # ── Índices para performance ────────────────────────────────
    cur.execute("CREATE INDEX IF NOT EXISTS idx_empenhos_credor ON empenhos(credor_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_empenhos_ano_mes ON empenhos(ano, mes)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_credores_departamento ON credores(departamento)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_logs_data ON logs(data)")

    conn.commit()

    print(f"Banco de dados pronto: {DB_PATH}")

def _seed_from_data_js(cur):
    """Lê o data.js e insere os credores no banco."""
    import re
    with open(DATA_JS, encoding='utf-8') as f:
        content = f.read()
    # Extrai o array JSON do arquivo JS
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
    print(f"  {len(data)} credores inseridos.")

# ── Helpers ──────────────────────────────────────────────────
def row_to_dict(row):
    return dict(row)

# ────────────────────────────────────────────────────────────
# ROTAS – Statics
# ────────────────────────────────────────────────────────────

@app.route('/')
def index():
    resp = send_file(os.path.join(BASE_DIR, 'index.html'))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return resp


@app.route('/static/<path:filename>')
def static_cached(filename):
    resp = send_from_directory(os.path.join(BASE_DIR, 'static'), filename)
    resp.headers['Cache-Control'] = 'public, max-age=86400'
    return resp


@app.route('/<path:filename>')
def static_files(filename):
    if filename.startswith('api/'):
        return jsonify({'error': 'Rota não encontrada: ' + filename}), 404
    resp = send_from_directory(BASE_DIR, filename)
    if filename.endswith('.html'):
        resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return resp

@app.errorhandler(404)
def not_found(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Rota não encontrada', 'path': request.path}), 404
    return str(e), 404

@app.errorhandler(500)
def server_error(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Erro interno do servidor', 'detail': str(e)}), 500
    return str(e), 500

# ────────────────────────────────────────────────────────────
# API – Autenticação ADM
# ────────────────────────────────────────────────────────────

# Senha armazenada no servidor — nunca exposta ao cliente
_ADM_PASSWORD = os.environ.get('ADM_PASSWORD', '1999')

@app.route('/api/auth/adm', methods=['POST'])
def auth_adm():
    """Verifica a senha da área administrativa."""
    d = request.get_json(force=True) or {}
    senha = d.get('senha', '')
    if senha == _ADM_PASSWORD:
        return jsonify({'ok': True})
    return jsonify({'ok': False, 'error': 'Senha incorreta'}), 401
# ────────────────────────────────────────────────────────────

@app.route('/api/ping', methods=['GET'])
def ping():
    return jsonify({'ok': True})

@app.route('/api/credores', methods=['GET'])
def get_credores():
    limit = request.args.get('limit', 1000, type=int)
    offset = request.args.get('offset', 0, type=int)
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM credores WHERE ativo=1 ORDER BY departamento, nome LIMIT ? OFFSET ?",
        (limit, offset)
    ).fetchall()

    return jsonify([row_to_dict(r) for r in rows])


@app.route('/api/credores', methods=['POST'])
def add_credor():
    data = request.get_json()
    conn = get_db()
    cur  = conn.cursor()
    cur.execute("""
        INSERT INTO credores
          (nome, valor, descricao, cnpj, email, tipo_valor, solicitacao, pagamento, validade, departamento, obs)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, (
        data.get('nome', '').upper(),
        float(data.get('valor') or 0),
        (data.get('descricao') or '').upper(),
        data.get('cnpj', ''),
        data.get('email', ''),
        data.get('tipo_valor', 'FIXO'),
        data.get('solicitacao', ''),
        data.get('pagamento', ''),
        data.get('validade', ''),
        data.get('departamento', ''),
        (data.get('obs') or '').upper(),
    ))
    new_id = cur.lastrowid
    conn.commit()
    
    # Log da ação
    cur.execute("INSERT INTO logs (acao, credor_id, credor_nome, detalhes) VALUES (?,?,?,?)",
        ('CRIAR', new_id, data.get('nome', '').upper(), f"Criado novo credor - Valor: R$ {data.get('valor', 0)}"))
    conn.commit()
    
    row = conn.execute("SELECT * FROM credores WHERE id=?", (new_id,)).fetchone()

    return jsonify(row_to_dict(row)), 201


@app.route('/api/credores/<int:cid>', methods=['PUT'])
def update_credor(cid):
    data = request.get_json()
    conn = get_db()

    # Captura valores antigos para diff
    old_row = conn.execute("SELECT * FROM credores WHERE id=?", (cid,)).fetchone()
    old = row_to_dict(old_row) if old_row else {}

    conn.execute("""
        UPDATE credores SET
          nome=?, valor=?, descricao=?, cnpj=?, email=?,
          tipo_valor=?, solicitacao=?, pagamento=?, validade=?, departamento=?, obs=?
        WHERE id=?
    """, (
        data.get('nome', '').upper(),
        float(data.get('valor') or 0),
        (data.get('descricao') or '').upper(),
        data.get('cnpj', ''),
        data.get('email', ''),
        data.get('tipo_valor', 'FIXO'),
        data.get('solicitacao', ''),
        data.get('pagamento', ''),
        data.get('validade', ''),
        data.get('departamento', ''),
        (data.get('obs') or '').upper(),
        cid,
    ))
    conn.commit()

    # Gera diff com rótulos legíveis
    labels = {
        'nome': 'Nome', 'valor': 'Valor', 'descricao': 'Descrição',
        'cnpj': 'CNPJ', 'email': 'E-mail', 'tipo_valor': 'Tipo',
        'departamento': 'Departamento', 'obs': 'OBS',
        'pagamento': 'Pagamento', 'solicitacao': 'Solicitação'
    }
    new_vals = {
        'nome': data.get('nome', '').upper(),
        'valor': str(float(data.get('valor') or 0)),
        'descricao': (data.get('descricao') or '').upper(),
        'cnpj': data.get('cnpj', ''),
        'email': data.get('email', ''),
        'tipo_valor': data.get('tipo_valor', 'FIXO'),
        'departamento': data.get('departamento', ''),
        'obs': (data.get('obs') or '').upper(),
        'pagamento': data.get('pagamento', ''),
        'solicitacao': data.get('solicitacao', ''),
    }
    changes = []
    for key, label in labels.items():
        old_val = str(old.get(key, '') or '')
        new_val = str(new_vals.get(key, '') or '')
        if old_val != new_val:
            changes.append(f"{label}: {old_val or '—'} → {new_val or '—'}")
    detalhes = ' | '.join(changes) if changes else 'Sem alterações detectadas'

    cur = conn.cursor()
    cur.execute("INSERT INTO logs (acao, credor_id, credor_nome, detalhes) VALUES (?,?,?,?)",
        ('EDITAR', cid, data.get('nome', '').upper(), detalhes))
    conn.commit()

    row = conn.execute("SELECT * FROM credores WHERE id=?", (cid,)).fetchone()

    if not row:
        return jsonify({'error': 'Não encontrado'}), 404
    return jsonify(row_to_dict(row))


@app.route('/api/credores/<int:cid>', methods=['DELETE'])
def delete_credor(cid):
    conn = get_db()
    cur = conn.cursor()
    # Pegar nome antes de excluir
    row = conn.execute("SELECT nome FROM credores WHERE id=?", (cid,)).fetchone()
    nome = row[0] if row else 'Desconhecido'
    
    conn.execute("UPDATE credores SET ativo=0 WHERE id=?", (cid,))
    conn.execute("DELETE FROM empenhos WHERE credor_id=?", (cid,))
    
    # Log da ação
    cur.execute("INSERT INTO logs (acao, credor_id, credor_nome, detalhes) VALUES (?,?,?,?)",
        ('EXCLUIR', cid, nome, 'Credor excluído'))
    conn.commit()

    return jsonify({'ok': True})

@app.route('/api/logs', methods=['GET'])
def get_logs():
    conn = get_db()
    acao = request.args.get('acao', '').upper()
    limit = min(int(request.args.get('limit', 100)), 500)
    offset = int(request.args.get('offset', 0))
    if acao:
        rows = conn.execute(
            "SELECT * FROM logs WHERE acao=? ORDER BY data DESC LIMIT ? OFFSET ?",
            (acao, limit, offset)
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) FROM logs WHERE acao=?", (acao,)).fetchone()[0]
    else:
        rows = conn.execute(
            "SELECT * FROM logs ORDER BY data DESC LIMIT ? OFFSET ?",
            (limit, offset)
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) FROM logs").fetchone()[0]

    return jsonify({'logs': [row_to_dict(r) for r in rows], 'total': total, 'offset': offset, 'limit': limit})

# ────────────────────────────────────────────────────────────
# API – Empenhos
# ────────────────────────────────────────────────────────────

@app.route('/api/empenhos/<int:ano>/<int:mes>', methods=['GET'])
def get_empenhos(ano, mes):
    """Retorna lista de credor_ids empenhados no mês/ano."""
    conn = get_db()
    rows = conn.execute(
        "SELECT credor_id, timestamp FROM empenhos WHERE ano=? AND mes=? AND empenhado=1",
        (ano, mes)
    ).fetchall()

    return jsonify([row_to_dict(r) for r in rows])


@app.route('/api/empenhos', methods=['POST'])
def toggle_empenho():
    """Marca ou desmarca um empenho. Retorna o estado atual."""
    data      = request.get_json()
    cid       = int(data['credor_id'])
    ano       = int(data['ano'])
    mes       = int(data['mes'])
    from datetime import datetime
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    conn = get_db()
    cur = conn.cursor()
    nome_row = conn.execute("SELECT nome FROM credores WHERE id=?", (cid,)).fetchone()
    nome = nome_row['nome'] if nome_row else 'Desconhecido'

    existing = conn.execute(
        "SELECT id, empenhado FROM empenhos WHERE credor_id=? AND ano=? AND mes=?",
        (cid, ano, mes)
    ).fetchone()

    if existing:
        new_state = 0 if existing['empenhado'] == 1 else 1
        conn.execute(
            "UPDATE empenhos SET empenhado=?, timestamp=? WHERE id=?",
            (new_state, ts, existing['id'])
        )
        acao = 'EMPENHAR' if new_state == 1 else 'DESEMPENHAR'
        cur.execute("INSERT INTO logs (acao, credor_id, credor_nome, detalhes) VALUES (?,?,?,?)",
            (acao, cid, nome, f"{acao} em {mes:02d}/{ano}"))
        conn.commit()

        return jsonify({'empenhado': bool(new_state)})
    else:
        conn.execute(
            "INSERT INTO empenhos (credor_id, ano, mes, empenhado, timestamp) VALUES (?,?,?,1,?)",
            (cid, ano, mes, ts)
        )
        cur.execute("INSERT INTO logs (acao, credor_id, credor_nome, detalhes) VALUES (?,?,?,?)",
            ('EMPENHAR', cid, nome, f"EMPENHAR em {mes:02d}/{ano}"))
        conn.commit()

        return jsonify({'empenhado': True})


@app.route('/api/empenhos/historico/<int:cid>', methods=['GET'])
def historico_credor(cid):
    """Retorna histórico completo de empenhos de um credor."""
    conn = get_db()
    rows = conn.execute(
        "SELECT ano, mes, empenhado, timestamp FROM empenhos WHERE credor_id=? AND empenhado=1 ORDER BY ano DESC, mes DESC",
        (cid,)
    ).fetchall()

    return jsonify([row_to_dict(r) for r in rows])


# ────────────────────────────────────────────────────────────
# API – Organizador de Extratos (RENOMER)
# ────────────────────────────────────────────────────────────

import sys as _sys
from pathlib import Path as _Path
from datetime import datetime as _datetime

# Garante que o pacote renomer está no path
_renomer_pkg = _Path(__file__).parent
if str(_renomer_pkg) not in _sys.path:
    _sys.path.insert(0, str(_renomer_pkg))

from renomer.organizador_local_avancado import OrganizadorLocalAvancado as _OrgLocal
from renomer.organizador_ia import OrganizadorIA as _OrgIA


def _adaptar_resultado(r):
    """Converte formato RENOMER → formato esperado pela API (extratos.html)."""
    base = {
        'nome': r.get('nome_original', ''),
        'sucesso': r.get('sucesso', False),
        'data': r.get('detalhes', {}).get('data', {}),
        'conta': r.get('detalhes', {}).get('conta', {}),
        'banco': r.get('detalhes', {}).get('banco'),
        'tipo_conta': r.get('detalhes', {}).get('tipo_conta'),
        'confianca': r.get('detalhes', {}).get('confianca'),
    }
    if r.get('sucesso'):
        base['nome_novo'] = _Path(r.get('arquivo_destino', '')).name
        base['estrutura'] = r.get('estrutura', '')
        base['destino'] = r.get('arquivo_destino', '')
        base['acao'] = r.get('acao', '')
        if r.get('metodo'):
            base['metodo'] = r['metodo']
    else:
        base['erro'] = r.get('erro', 'Erro desconhecido')
    return base


@app.route('/api/extratos/preview', methods=['POST'])
def extratos_preview():
    """Escaneia pasta de origem e retorna prévia sem mover nada."""
    d = request.get_json()
    origem = d.get('origem', '').strip()
    destino = d.get('destino', '').strip()

    if not origem or not _Path(origem).is_dir():
        return jsonify({'error': 'Pasta de origem inválida ou não encontrada'}), 400
    if not destino:
        return jsonify({'error': 'Pasta de destino obrigatória'}), 400
    if _Path(origem).resolve() == _Path(destino).resolve():
        return jsonify({'error': 'Origem e destino não podem ser iguais'}), 400

    arquivos = []
    for ext in ['*.pdf', '*.PDF', '*.ofx', '*.OFX']:
        arquivos.extend(_Path(origem).rglob(ext))

    usar_ia   = d.get('usar_ia', False)
    api_key_ia = d.get('api_key_ia', '').strip()
    modelo_ia  = d.get('modelo_ia', 'openai/gpt-4o-mini').strip() or 'openai/gpt-4o-mini'

    if usar_ia and api_key_ia:
        org = _OrgIA(origem, destino, api_key_ia, modelo_ia)
    else:
        org = _OrgLocal(origem, destino)
    resultados = [_adaptar_resultado(org.processar_arquivo(a, modo_teste=True)) for a in arquivos]
    sucessos = [r for r in resultados if r['sucesso']]
    erros = [r for r in resultados if not r['sucesso']]

    return jsonify({
        'total': len(arquivos),
        'sucessos': len(sucessos),
        'erros': len(erros),
        'resultados': resultados
    })


@app.route('/api/extratos/organizar', methods=['POST'])
def extratos_organizar():
    """Organiza os arquivos de fato (copia para destino)."""
    d = request.get_json()
    origem = d.get('origem', '').strip()
    destino = d.get('destino', '').strip()

    if not origem or not _Path(origem).is_dir():
        return jsonify({'error': 'Pasta de origem inválida ou não encontrada'}), 400
    if not destino:
        return jsonify({'error': 'Pasta de destino obrigatória'}), 400
    if _Path(origem).resolve() == _Path(destino).resolve():
        return jsonify({'error': 'Origem e destino não podem ser iguais'}), 400

    try:
        _Path(destino).mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return jsonify({'error': f'Não foi possível criar pasta de destino: {e}'}), 400

    arquivos = []
    for ext in ['*.pdf', '*.PDF', '*.ofx', '*.OFX']:
        arquivos.extend(_Path(origem).rglob(ext))

    usar_ia   = d.get('usar_ia', False)
    api_key_ia = d.get('api_key_ia', '').strip()
    modelo_ia  = d.get('modelo_ia', 'openai/gpt-4o-mini').strip() or 'openai/gpt-4o-mini'

    if usar_ia and api_key_ia:
        org = _OrgIA(origem, destino, api_key_ia, modelo_ia)
    else:
        org = _OrgLocal(origem, destino)
    resultados = [_adaptar_resultado(org.processar_arquivo(a, modo_teste=False)) for a in arquivos]
    sucessos = [r for r in resultados if r['sucesso']]
    erros = [r for r in resultados if not r['sucesso']]

    return jsonify({
        'total': len(arquivos),
        'sucessos': len(sucessos),
        'erros': len(erros),
        'resultados': resultados,
        'concluido_em': _datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    })


@app.route('/api/extratos/modelos-openrouter', methods=['POST'])
def modelos_openrouter():
    """Retorna lista de modelos disponíveis no OpenRouter."""
    import urllib.request, urllib.error
    d = request.get_json()
    api_key = d.get('api_key', '').strip()
    if not api_key:
        return jsonify({'error': 'Chave API obrigatória'}), 400
    try:
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {api_key}",
                     "Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode())
        return jsonify({'modelos': data.get('data', [])})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/ia/chat', methods=['POST'])
def ia_chat_proxy():
    """Proxy para OpenRouter chat completions (evita CORS no browser)."""
    import urllib.request, urllib.error
    d = request.get_json() or {}
    api_key = d.get('api_key', '').strip()
    model   = d.get('model', 'meta-llama/llama-3.1-8b-instruct:free').strip()
    messages = d.get('messages', [])
    max_tokens = int(d.get('max_tokens', 500))
    temperature = float(d.get('temperature', 0.3))
    if not api_key:
        return jsonify({'error': 'Chave API obrigatória'}), 400
    payload = json.dumps({
        'model': model,
        'messages': messages,
        'max_tokens': max_tokens,
        'temperature': temperature
    }).encode('utf-8')
    try:
        req = urllib.request.Request(
            'https://openrouter.ai/api/v1/chat/completions',
            data=payload,
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
                'HTTP-Referer': 'https://localhost',
                'X-Title': 'CEREBRO_PREFEITURA'
            },
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read().decode())
        return jsonify(data)
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        try:
            err = json.loads(body)
        except Exception:
            err = {'message': body}
        return jsonify({'error': err, 'model_used': model}), e.code
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/extratos/listar-pasta', methods=['POST'])
def listar_pasta():
    """Lista subpastas de um caminho para navegação."""
    d = request.get_json()
    caminho = d.get('caminho', '').strip()
    p = _Path(caminho) if caminho else _Path.home()
    if not p.exists():
        p = _Path.home()
    try:
        itens = [{'nome': str(i.name), 'caminho': str(i), 'tipo': 'dir' if i.is_dir() else 'file'}
                 for i in sorted(p.iterdir()) if i.is_dir()]
        return jsonify({'caminho_atual': str(p), 'pai': str(p.parent), 'itens': itens})
    except PermissionError:
        return jsonify({'error': 'Sem permissão para acessar esta pasta'}), 403


# ────────────────────────────────────────────────────────────
# API – RPAs
# ────────────────────────────────────────────────────────────

@app.route('/api/rpas', methods=['GET'])
def get_rpas():
    conn = get_db()
    rows = conn.execute("SELECT * FROM rpas ORDER BY criado_em DESC").fetchall()

    return jsonify([row_to_dict(r) for r in rows])


@app.route('/api/credores/<int:cid>/historico', methods=['GET'])
def get_historico_credor(cid):
    conn = get_db()
    meses = int(request.args.get('meses', 6))
    from datetime import date
    hoje = date.today()

    # Calcula o intervalo de meses desejado
    resultado = []
    periodo = []
    for i in range(meses - 1, -1, -1):
        m = hoje.month - i
        y = hoje.year
        while m <= 0:
            m += 12
            y -= 1
        periodo.append((y, m))

    # Uma única query para todos os meses
    placeholders = ','.join('(?,?)' for _ in periodo)
    params = [v for pair in periodo for v in pair]
    rows = conn.execute(
        f"SELECT ano, mes FROM empenhos WHERE credor_id=? AND empenhado=1 AND (ano,mes) IN ({placeholders})",
        [cid] + params
    ).fetchall()
    empenhados = {(r['ano'], r['mes']) for r in rows}

    mes_nomes = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez']
    for y, m in periodo:
        resultado.append({
            'ano': y, 'mes': m,
            'mes_nome': mes_nomes[m - 1],
            'empenhado': (y, m) in empenhados
        })
    return jsonify(resultado)


@app.route('/api/rpas', methods=['POST'])
def add_rpa():
    d = request.get_json()
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO rpas (
            numero_rpa, nome_prestador, cpf_prestador, endereco_prestador,
            descricao_servico, periodo_referencia, carga_horaria, local_execucao,
            valor_bruto, num_dependentes, pensao_alimenticia,
            inss, iss, deducao_dependentes, base_calculo_irrf,
            aliquota_irrf, parcela_deduzir_irrf, ir, valor_liquido,
            observacoes, data_emissao
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        d.get('numeroRPA', ''),
        d.get('nomePrestador', ''),
        d.get('cpfPrestador', ''),
        d.get('enderecoPrestador', ''),
        d.get('descricaoServico', ''),
        d.get('periodoReferencia', ''),
        d.get('cargaHoraria', ''),
        d.get('localExecucao', ''),
        float(d.get('valorBruto') or 0),
        int(d.get('numDependentes') or 0),
        float(d.get('pensaoAlimenticia') or 0),
        float(d.get('inss') or 0),
        float(d.get('iss') or 0),
        float(d.get('deducaoDependentes') or 0),
        float(d.get('baseCalculoIRRF') or 0),
        float(d.get('aliquotaIRRF') or 0),
        float(d.get('parcelaDeduzirIRRF') or 0),
        float(d.get('ir') or 0),
        float(d.get('valorLiquido') or 0),
        d.get('observacoes', ''),
        d.get('dataEmissao', ''),
    ))
    new_id = cur.lastrowid
    conn.commit()
    row = conn.execute("SELECT * FROM rpas WHERE id=?", (new_id,)).fetchone()

    return jsonify(row_to_dict(row)), 201


@app.route('/api/rpas/<int:rid>', methods=['PUT'])
def update_rpa(rid):
    d = request.get_json()
    conn = get_db()
    conn.execute("""
        UPDATE rpas SET
            numero_rpa=?, nome_prestador=?, cpf_prestador=?, endereco_prestador=?,
            descricao_servico=?, periodo_referencia=?, carga_horaria=?, local_execucao=?,
            valor_bruto=?, num_dependentes=?, pensao_alimenticia=?,
            inss=?, iss=?, deducao_dependentes=?, base_calculo_irrf=?,
            aliquota_irrf=?, parcela_deduzir_irrf=?, ir=?, valor_liquido=?,
            observacoes=?, data_emissao=?
        WHERE id=?
    """, (
        d.get('numeroRPA', ''),
        d.get('nomePrestador', ''),
        d.get('cpfPrestador', ''),
        d.get('enderecoPrestador', ''),
        d.get('descricaoServico', ''),
        d.get('periodoReferencia', ''),
        d.get('cargaHoraria', ''),
        d.get('localExecucao', ''),
        float(d.get('valorBruto') or 0),
        int(d.get('numDependentes') or 0),
        float(d.get('pensaoAlimenticia') or 0),
        float(d.get('inss') or 0),
        float(d.get('iss') or 0),
        float(d.get('deducaoDependentes') or 0),
        float(d.get('baseCalculoIRRF') or 0),
        float(d.get('aliquotaIRRF') or 0),
        float(d.get('parcelaDeduzirIRRF') or 0),
        float(d.get('ir') or 0),
        float(d.get('valorLiquido') or 0),
        d.get('observacoes', ''),
        d.get('dataEmissao', ''),
        rid,
    ))
    conn.commit()
    row = conn.execute("SELECT * FROM rpas WHERE id=?", (rid,)).fetchone()

    if not row:
        return jsonify({'error': 'Não encontrado'}), 404
    return jsonify(row_to_dict(row))


@app.route('/api/rpas/<int:rid>', methods=['DELETE'])
def delete_rpa(rid):
    conn = get_db()
    conn.execute("DELETE FROM rpas WHERE id=?", (rid,))
    conn.commit()

    return jsonify({'ok': True})


# ────────────────────────────────────────────────────────────
# API – Kanban Tasks
# ────────────────────────────────────────────────────────────

@app.route('/api/kanban', methods=['GET'])
def kanban_list():
    conn = get_db()
    rows = conn.execute("SELECT * FROM kanban_tasks ORDER BY criado_em ASC").fetchall()

    return jsonify([dict(r) for r in rows])

@app.route('/api/kanban', methods=['POST'])
def kanban_create():
    d = request.json or {}
    if not d.get('id') or not d.get('title'):
        return jsonify({'error': 'id e title são obrigatórios'}), 400
    conn = get_db()
    conn.execute(
        "INSERT INTO kanban_tasks (id, title, description, status, priority) VALUES (?,?,?,?,?)",
        (d['id'], d['title'], d.get('description',''), d.get('status','todo'), d.get('priority','medium'))
    )
    conn.commit()
    row = conn.execute("SELECT * FROM kanban_tasks WHERE id=?", (d['id'],)).fetchone()

    return jsonify(dict(row)), 201

@app.route('/api/kanban/<task_id>', methods=['PUT'])
def kanban_update(task_id):
    d = request.json or {}
    conn = get_db()
    conn.execute(
        """UPDATE kanban_tasks SET title=?, description=?, status=?, priority=?,
           atualizado_em=datetime('now','localtime') WHERE id=?""",
        (d.get('title'), d.get('description',''), d.get('status'), d.get('priority'), task_id)
    )
    conn.commit()
    row = conn.execute("SELECT * FROM kanban_tasks WHERE id=?", (task_id,)).fetchone()

    if not row:
        return jsonify({'error': 'not found'}), 404
    return jsonify(dict(row))

@app.route('/api/kanban/<task_id>', methods=['DELETE'])
def kanban_delete(task_id):
    conn = get_db()
    conn.execute("DELETE FROM kanban_tasks WHERE id=?", (task_id,))
    conn.commit()

    return jsonify({'ok': True})


# ────────────────────────────────────────────────────────────
# API – Fornecimento Dados (solicitantes / empresas / observações)
# ────────────────────────────────────────────────────────────
@app.route('/api/fornecimento/dados', methods=['GET'])
def fornecimento_dados_get():
    conn = get_db()
    rows = conn.execute("SELECT tipo, valor FROM fornecimento_dados ORDER BY tipo, valor COLLATE NOCASE").fetchall()

    result = {'solicitantes': [], 'empresas': [], 'observacoes': []}
    for r in rows:
        if r['tipo'] in result:
            result[r['tipo']].append(r['valor'])
    return jsonify(result)

@app.route('/api/fornecimento/dados', methods=['POST'])
def fornecimento_dados_add():
    d = request.get_json(force=True)
    tipo  = d.get('tipo', '').strip()
    valor = d.get('valor', '').strip()
    if tipo not in ('solicitantes', 'empresas', 'observacoes') or not valor:
        return jsonify({'error': 'tipo ou valor inválido'}), 400
    conn = get_db()
    conn.execute("INSERT OR IGNORE INTO fornecimento_dados (tipo, valor) VALUES (?,?)", (tipo, valor))
    conn.commit()

    return jsonify({'ok': True})

@app.route('/api/fornecimento/dados', methods=['DELETE'])
def fornecimento_dados_del():
    d = request.get_json(force=True)
    tipo  = d.get('tipo', '').strip()
    valor = d.get('valor', '').strip()
    conn = get_db()
    conn.execute("DELETE FROM fornecimento_dados WHERE tipo=? AND valor=?", (tipo, valor))
    conn.commit()

    return jsonify({'ok': True})


# ────────────────────────────────────────────────────────────
# API – Configurações (chave/valor persistido no banco)
# ────────────────────────────────────────────────────────────
ALLOWED_CONFIG_KEYS = {'api_openrouter_key', 'api_openrouter_modelo', 'api_cnpja_key'}

@app.route('/api/config', methods=['GET'])
def config_get():
    conn = get_db()
    rows = conn.execute("SELECT chave, valor FROM configuracoes").fetchall()

    return jsonify({r['chave']: r['valor'] for r in rows if r['chave'] in ALLOWED_CONFIG_KEYS})

@app.route('/api/config', methods=['POST'])
def config_set():
    d = request.get_json(force=True)
    conn = get_db()
    for chave, valor in d.items():
        if chave in ALLOWED_CONFIG_KEYS:
            conn.execute(
                "INSERT INTO configuracoes (chave, valor, atualizado_em) VALUES (?,?,datetime('now','localtime')) "
                "ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor, atualizado_em=excluded.atualizado_em",
                (chave, str(valor))
            )
    conn.commit()

    return jsonify({'ok': True})

import urllib.request as _urllib_req
import urllib.error as _urllib_err

def _cnpj_so_numeros(cnpj: str) -> str:
    import re as _re2
    return _re2.sub(r'\D', '', cnpj)

def _buscar_cnpja(cnpj: str, api_key: str = '') -> dict:
    """Consulta API CNPJá (open.cnpja.com). Com api_key usa tier pago (sem limite de taxa)."""
    url = f"https://open.cnpja.com/office/{cnpj}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    if api_key:
        headers['Authorization'] = f'Bearer {api_key}'
    req = _urllib_req.Request(url, headers=headers)
    with _urllib_req.urlopen(req, timeout=15) as r:
        d = json.loads(r.read().decode())

    def fmt_moeda(v):
        try: return f"R$ {float(v):,.2f}".replace(',','X').replace('.',',').replace('X','.')
        except: return str(v) if v else ''

    end = d.get('address', {})
    telefones = [f"({p.get('area','')}) {p.get('number','')} [{p.get('type','')}]"
                 for p in d.get('phones', []) if p.get('number')]
    emails = [f"{e.get('address','')} [{e.get('ownership','')}]"
              for e in d.get('emails', []) if e.get('address')]
    socios = [{'nome': m.get('person',{}).get('name',''),
               'qualificacao': m.get('role',{}).get('text','')}
              for m in d.get('company', {}).get('members', [])]
    cnaes_sec = [a.get('text','') for a in d.get('sideActivities', [])]

    complemento = end.get('details', '')
    end_str = f"{end.get('street','')} {end.get('number','')}".strip()
    if complemento: end_str += f", {complemento}"
    end_str += f" - {end.get('district','')} - {end.get('city','')}/{end.get('state','')} - CEP {end.get('zip','')}"

    return {
        'cnpj': cnpj,
        'razao_social': d.get('company',{}).get('name',''),
        'nome_fantasia': d.get('alias',''),
        'situacao': d.get('status',{}).get('text',''),
        'situacao_id': d.get('status',{}).get('id',''),
        'data_situacao': d.get('statusDate',''),
        'data_abertura': d.get('founded',''),
        'natureza_juridica': d.get('company',{}).get('nature',{}).get('text',''),
        'capital_social': fmt_moeda(d.get('company',{}).get('equity')),
        'porte': d.get('company',{}).get('size',{}).get('text',''),
        'simples': 'Sim' if d.get('company',{}).get('simples',{}).get('optant') else 'Não',
        'mei': 'Sim' if d.get('company',{}).get('simei',{}).get('optant') else 'Não',
        'matriz': 'Sim' if d.get('head') else 'Filial',
        'endereco': end_str,
        'cnae_principal': d.get('mainActivity',{}).get('text',''),
        'cnaes_secundarios': cnaes_sec,
        'socios': socios,
        'telefones': telefones,
        'emails': emails,
        'fonte': 'CNPJá',
    }

def _buscar_receitaws(cnpj: str) -> dict:
    """Fallback para ReceitaWS."""
    url = f"https://www.receitaws.com.br/v1/cnpj/{cnpj}"
    req = _urllib_req.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with _urllib_req.urlopen(req, timeout=10) as r:
        d = json.loads(r.read().decode())
    if d.get('status') == 'ERROR':
        raise Exception(d.get('message', 'CNPJ não encontrado'))
    socios = [{'nome': s.get('nome',''), 'qualificacao': s.get('qual','')}
              for s in d.get('qsa', [])]
    return {
        'cnpj': cnpj,
        'razao_social': d.get('nome',''),
        'nome_fantasia': d.get('fantasia',''),
        'situacao': d.get('situacao',''),
        'situacao_id': d.get('situacao','').upper(),
        'data_abertura': d.get('abertura',''),
        'natureza_juridica': d.get('natureza_juridica',''),
        'capital_social': d.get('capital_social',''),
        'porte': d.get('porte',''),
        'simples': d.get('simples',''),
        'mei': d.get('mei',''),
        'endereco': f"{d.get('logradouro','')} {d.get('numero','')} - {d.get('bairro','')} - {d.get('municipio','')}/{d.get('uf','')} - CEP {d.get('cep','')}",
        'cnae_principal': d.get('atividade_principal',[{}])[0].get('text','') if d.get('atividade_principal') else '',
        'cnaes_secundarios': [a.get('text','') for a in d.get('atividades_secundarias', [])],
        'socios': socios,
        'telefones': [d.get('telefone','')] if d.get('telefone') else [],
        'emails': [d.get('email','')] if d.get('email') else [],
        'fonte': 'ReceitaWS',
    }

@app.route('/api/cnpj/buscar', methods=['POST'])
def cnpj_buscar():
    """Consulta dados de empresa pelo CNPJ. Usa CNPJá com fallback ReceitaWS."""
    d = request.get_json()
    cnpj = _cnpj_so_numeros(d.get('cnpj', ''))
    api_key = d.get('api_key_cnpja', '').strip()
    if len(cnpj) != 14:
        return jsonify({'error': 'CNPJ deve ter 14 dígitos'}), 400
    # Tenta CNPJá primeiro
    try:
        return jsonify(_buscar_cnpja(cnpj, api_key))
    except _urllib_err.HTTPError as e:
        if e.code == 429:
            return jsonify({'error': 'Limite de consultas atingido (5/min). Aguarde 1 minuto.'}), 429
        if e.code == 404:
            pass  # Tenta fallback
        else:
            pass
    except Exception:
        pass
    # Fallback ReceitaWS
    try:
        return jsonify(_buscar_receitaws(cnpj))
    except Exception as e2:
        return jsonify({'error': f'CNPJ não encontrado: {e2}'}), 404



# ────────────────────────────────────────────────────────────
# PDF – Mesclar / Dividir / Proteger
# ────────────────────────────────────────────────────────────
import io as _io
import zipfile as _zipfile
from PyPDF2 import PdfReader as _PdfReader, PdfWriter as _PdfWriter

@app.route('/api/pdf/mesclar', methods=['POST'])
def pdf_mesclar():
    files = request.files.getlist('pdfs')
    if len(files) < 2:
        return 'Envie ao menos 2 arquivos', 400
    writer = _PdfWriter()
    for f in files:
        reader = _PdfReader(f)
        for page in reader.pages:
            writer.add_page(page)
    buf = _io.BytesIO()
    writer.write(buf)
    buf.seek(0)
    return send_file(buf, mimetype='application/pdf', as_attachment=True,
                     download_name='mesclado.pdf')

@app.route('/api/pdf/dividir', methods=['POST'])
def pdf_dividir():
    f = request.files.get('pdf')
    ranges_str = request.form.get('ranges', '').strip()
    if not f or not ranges_str:
        return 'Parâmetros inválidos', 400
    pdf_bytes = f.read()
    reader = _PdfReader(_io.BytesIO(pdf_bytes))
    total = len(reader.pages)
    groups = []
    for part in ranges_str.split(','):
        part = part.strip()
        if not part:
            continue
        if '-' in part:
            a, b = part.split('-', 1)
            a_i = max(0, int(a.strip()) - 1)
            b_i = min(total - 1, int(b.strip()) - 1)
            pgs = list(range(a_i, b_i + 1))
            name = f"paginas_{a.strip()}-{b.strip()}.pdf"
        else:
            p = int(part.strip()) - 1
            pgs = [p] if 0 <= p < total else []
            name = f"pagina_{part.strip()}.pdf"
        if pgs:
            groups.append((name, pgs))
    if not groups:
        return 'Nenhuma página válida nos intervalos informados', 400
    if len(groups) == 1:
        writer = _PdfWriter()
        for p in groups[0][1]:
            writer.add_page(reader.pages[p])
        buf = _io.BytesIO()
        writer.write(buf)
        buf.seek(0)
        return send_file(buf, mimetype='application/pdf', as_attachment=True,
                         download_name=groups[0][0])
    zip_buf = _io.BytesIO()
    with _zipfile.ZipFile(zip_buf, 'w', _zipfile.ZIP_DEFLATED) as zf:
        for name, pgs in groups:
            writer = _PdfWriter()
            for p in pgs:
                writer.add_page(reader.pages[p])
            pdf_buf = _io.BytesIO()
            writer.write(pdf_buf)
            zf.writestr(name, pdf_buf.getvalue())
    zip_buf.seek(0)
    return send_file(zip_buf, mimetype='application/zip', as_attachment=True,
                     download_name='dividido.zip')

@app.route('/api/pdf/proteger', methods=['POST'])
def pdf_proteger():
    f = request.files.get('pdf')
    senha = request.form.get('senha', '')
    if not f or not senha:
        return 'Parâmetros inválidos', 400
    reader = _PdfReader(f)
    writer = _PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt(senha)
    buf = _io.BytesIO()
    writer.write(buf)
    buf.seek(0)
    return send_file(buf, mimetype='application/pdf', as_attachment=True,
                     download_name='protegido.pdf')


# ────────────────────────────────────────────────────────────
# API – Despesas da Prefeitura (histórico CSV → BD)
# ────────────────────────────────────────────────────────────

@app.route('/api/despesas/importacoes', methods=['GET'])
def despesas_listar_importacoes():
    """Lista todas as importações de despesas salvas no banco."""
    conn = get_db()
    rows = conn.execute(
        "SELECT id, periodo, descricao, arquivo, total_rows, importado_em "
        "FROM despesas_importacoes ORDER BY importado_em DESC"
    ).fetchall()

    return jsonify([row_to_dict(r) for r in rows])


@app.route('/api/despesas/importar', methods=['POST'])
def despesas_importar():
    """Salva um CSV de despesas no banco de dados com período e descrição."""
    try:
        d = request.get_json(force=True)
        if not d:
            return jsonify({'error': 'JSON inválido ou vazio'}), 400
        periodo  = (d.get('periodo') or '').strip()
        descricao = (d.get('descricao') or '').strip()
        arquivo  = (d.get('arquivo') or '').strip()
        linhas   = d.get('linhas', [])   # lista de objetos {coluna: valor}
        colunas  = d.get('colunas', [])  # lista de strings

        if not periodo:
            return jsonify({'error': 'Período obrigatório'}), 400
        if not linhas:
            return jsonify({'error': 'Nenhuma linha recebida'}), 400

        from datetime import datetime as _dt_now
        now = _dt_now.now().strftime('%Y-%m-%d %H:%M:%S')

        conn = get_db()
        cur  = conn.cursor()
        cur.execute(
            "INSERT INTO despesas_importacoes (periodo, descricao, arquivo, total_rows, colunas, importado_em) "
            "VALUES (?,?,?,?,?,?)",
            (periodo, descricao, arquivo, len(linhas), json.dumps(colunas, ensure_ascii=False), now)
        )
        imp_id = cur.lastrowid

        cur.executemany(
            "INSERT INTO despesas_linhas (importacao_id, dados) VALUES (?,?)",
            [(imp_id, json.dumps(row, ensure_ascii=False)) for row in linhas]
        )

        conn.commit()
        row = conn.execute(
            "SELECT id, periodo, descricao, arquivo, total_rows, importado_em "
            "FROM despesas_importacoes WHERE id=?", (imp_id,)
        ).fetchone()

        return jsonify(row_to_dict(row)), 201
    except Exception as e:
        return jsonify({'error': 'Erro ao salvar no banco', 'detail': str(e)}), 500


@app.route('/api/despesas/importacoes/<int:imp_id>', methods=['GET'])
def despesas_carregar(imp_id):
    """Retorna os dados completos de uma importação."""
    conn = get_db()
    imp = conn.execute(
        "SELECT id, periodo, descricao, arquivo, total_rows, colunas, importado_em "
        "FROM despesas_importacoes WHERE id=?", (imp_id,)
    ).fetchone()
    if not imp:

        return jsonify({'error': 'Importação não encontrada'}), 404

    linhas_rows = conn.execute(
        "SELECT dados FROM despesas_linhas WHERE importacao_id=? ORDER BY id",
        (imp_id,)
    ).fetchall()


    imp_dict = row_to_dict(imp)
    imp_dict['colunas'] = json.loads(imp_dict['colunas'] or '[]')
    linhas = [json.loads(r['dados']) for r in linhas_rows]
    return jsonify({'importacao': imp_dict, 'linhas': linhas})


@app.route('/api/despesas/importacoes/<int:imp_id>', methods=['DELETE'])
def despesas_excluir(imp_id):
    """Exclui uma importação e todas as suas linhas."""
    conn = get_db()
    conn.execute("DELETE FROM despesas_linhas WHERE importacao_id=?", (imp_id,))
    conn.execute("DELETE FROM despesas_importacoes WHERE id=?", (imp_id,))
    conn.commit()

    return jsonify({'ok': True})


@app.route('/api/despesas/importacoes/<int:imp_id>/resumo', methods=['GET'])
def despesas_resumo(imp_id):
    """Retorna totais e agrupamentos de uma importação (sem retornar todas as linhas)."""
    conn = get_db()
    imp = conn.execute(
        "SELECT id, periodo, descricao, arquivo, total_rows, colunas, importado_em "
        "FROM despesas_importacoes WHERE id=?", (imp_id,)
    ).fetchone()
    if not imp:

        return jsonify({'error': 'Importação não encontrada'}), 404

    linhas_rows = conn.execute(
        "SELECT dados FROM despesas_linhas WHERE importacao_id=?", (imp_id,)
    ).fetchall()


    colunas = json.loads(imp['colunas'] or '[]')
    linhas = [json.loads(r['dados']) for r in linhas_rows]

    def parse_val(v):
        if not v:
            return 0.0
        s = str(v).replace('.', '').replace(',', '.').strip()
        try:
            return float(s)
        except Exception:
            return 0.0

    # Detecta colunas de valor
    val_cols = [c for c in colunas if any(k in c.lower() for k in ['saldo', 'valor', 'empenhado', 'liquidado', 'pago'])]
    totais = {c: sum(parse_val(r.get(c, 0)) for r in linhas) for c in val_cols}

    # Agrupamentos
    def agrupar(col_key):
        grupos = {}
        for r in linhas:
            k = r.get(col_key) or '(Sem valor)'
            grupos[k] = grupos.get(k, 0) + 1
        return dict(sorted(grupos.items(), key=lambda x: -x[1])[:20])

    secretaria_col = next((c for c in colunas if 'organograma' in c.lower()), None)
    funcao_col     = next((c for c in colunas if 'função' in c.lower() or 'funcao' in c.lower()), None)
    natureza_col   = next((c for c in colunas if 'natureza' in c.lower() and 'descrição' not in c.lower() and 'descricao' not in c.lower()), None)
    recurso_col    = next((c for c in colunas if 'recurso' in c.lower() and 'descrição' not in c.lower()), None)

    # Totais por agrupamento de valor (top secretaria por soma de saldo)
    saldo_col = next((c for c in colunas if 'saldo' in c.lower()), None)
    por_secretaria_valor = {}
    if secretaria_col and saldo_col:
        for r in linhas:
            k = r.get(secretaria_col) or '(Sem valor)'
            por_secretaria_valor[k] = por_secretaria_valor.get(k, 0) + parse_val(r.get(saldo_col, 0))
        por_secretaria_valor = dict(sorted(por_secretaria_valor.items(), key=lambda x: -x[1])[:15])

    return jsonify({
        'importacao': {
            'id': imp['id'],
            'periodo': imp['periodo'],
            'descricao': imp['descricao'],
            'arquivo': imp['arquivo'],
            'total_rows': imp['total_rows'],
            'importado_em': imp['importado_em'],
        },
        'totais': totais,
        'por_secretaria_contagem': agrupar(secretaria_col) if secretaria_col else {},
        'por_secretaria_valor': por_secretaria_valor,
        'por_funcao': agrupar(funcao_col) if funcao_col else {},
        'por_natureza': agrupar(natureza_col) if natureza_col else {},
        'por_recurso': agrupar(recurso_col) if recurso_col else {},
        'saldo_col': saldo_col,
        'colunas': colunas,
    })


# ────────────────────────────────────────────────────────────
# API – Empenhos CSV (Visualizador de Empenhos → BD)
# ────────────────────────────────────────────────────────────

@app.route('/api/empenhos-csv/importar', methods=['POST'])
def empenhos_csv_importar():
    """Salva dados de empenhos (CSV do visualizador) no banco."""
    try:
        d = request.get_json(force=True)
        if not d:
            return jsonify({'error': 'JSON inválido'}), 400
        periodo  = (d.get('periodo') or '').strip()
        descricao = (d.get('descricao') or '').strip()
        arquivo  = (d.get('arquivo') or '').strip()
        linhas   = d.get('linhas', [])

        if not periodo:
            return jsonify({'error': 'Período obrigatório'}), 400
        if not linhas:
            return jsonify({'error': 'Nenhuma linha recebida'}), 400

        from datetime import datetime as _dt
        now = _dt.now().strftime('%Y-%m-%d %H:%M:%S')
        conn = get_db()
        cur  = conn.cursor()
        cur.execute(
            "INSERT INTO empenhos_importacoes (periodo, descricao, arquivo, total_rows, importado_em) VALUES (?,?,?,?,?)",
            (periodo, descricao, arquivo, len(linhas), now)
        )
        imp_id = cur.lastrowid
        cur.executemany(
            "INSERT INTO empenhos_linhas (importacao_id, dados) VALUES (?,?)",
            [(imp_id, json.dumps(row, ensure_ascii=False)) for row in linhas]
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, periodo, descricao, arquivo, total_rows, importado_em FROM empenhos_importacoes WHERE id=?", (imp_id,)
        ).fetchone()
        return jsonify(row_to_dict(row)), 201
    except Exception as e:
        return jsonify({'error': 'Erro ao salvar', 'detail': str(e)}), 500


@app.route('/api/empenhos-csv/importacoes', methods=['GET'])
def empenhos_csv_listar():
    conn = get_db()
    rows = conn.execute(
        "SELECT id, periodo, descricao, arquivo, total_rows, importado_em FROM empenhos_importacoes ORDER BY importado_em DESC"
    ).fetchall()
    return jsonify([row_to_dict(r) for r in rows])


@app.route('/api/empenhos-csv/importacoes/<int:imp_id>', methods=['GET'])
def empenhos_csv_carregar(imp_id):
    conn = get_db()
    imp = conn.execute(
        "SELECT id, periodo, descricao, arquivo, total_rows, importado_em FROM empenhos_importacoes WHERE id=?", (imp_id,)
    ).fetchone()
    if not imp:
        return jsonify({'error': 'Importação não encontrada'}), 404
    linhas_rows = conn.execute(
        "SELECT dados FROM empenhos_linhas WHERE importacao_id=? ORDER BY id", (imp_id,)
    ).fetchall()
    linhas = [json.loads(r['dados']) for r in linhas_rows]
    return jsonify({'importacao': row_to_dict(imp), 'linhas': linhas})


@app.route('/api/empenhos-csv/importacoes/<int:imp_id>', methods=['DELETE'])
def empenhos_csv_excluir(imp_id):
    conn = get_db()
    conn.execute("DELETE FROM empenhos_linhas WHERE importacao_id=?", (imp_id,))
    conn.execute("DELETE FROM empenhos_importacoes WHERE id=?", (imp_id,))
    conn.commit()
    return jsonify({'ok': True})


# ────────────────────────────────────────────────────────────
# MAIN
# ────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import socket
    init_db()
    migrate_db()

    # ── Fix de performance: Werkzeug faz reverse-DNS lookup em cada requisição
    #    via socket.getfqdn(), o que trava ~2s no Windows. Desabilitamos isso.
    try:
        from werkzeug.serving import WSGIRequestHandler
        WSGIRequestHandler.address_string = lambda self: self.client_address[0]
    except Exception:
        pass

    # Detecta o IP local da máquina
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        local_ip = s.getsockname()[0]
        s.close()
    except OSError:
        local_ip = '127.0.0.1'
    print('=' * 60)
    print('  Sistema de Empenhos – Prefeitura Municipal de Inajá')
    print(f'  Local  : http://localhost:5000')
    print(f'  Rede   : http://{local_ip}:5000   << compartilhe este link')
    print('  Para encerrar: feche esta janela ou pressione Ctrl+C')
    print('=' * 60)
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)

