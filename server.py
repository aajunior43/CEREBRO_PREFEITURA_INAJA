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
import threading
import gzip as _gzip
import hashlib
import time as _time
import logging
import mimetypes
from logging.handlers import RotatingFileHandler
from collections import defaultdict
import urllib.error as _urllib_error

from flask import Flask, request, jsonify, send_from_directory, send_file, Response, g
from config import settings
from services.empenhos_service import listar_empenhos_mes, listar_historico_credor, persistir_empenho
from services.extratos_service import listar_subpastas, processar_extratos, validar_origem_destino
from services.openrouter_service import chat_completion, listar_modelos, parse_http_error

# ── Configurações ───────────────────────────────────────────
BASE_DIR = str(settings.base_dir)
DB_PATH = str(settings.db_path)
DATA_JS = str(settings.data_js_path)
DOCUMENTS_DIR = os.path.join(BASE_DIR, 'documentos_centro')

os.makedirs(DOCUMENTS_DIR, exist_ok=True)

app = Flask(__name__, static_folder=BASE_DIR)

# ── Logging para arquivo ─────────────────────────────────────
_LOG_DIR = str(settings.log_dir)
os.makedirs(_LOG_DIR, exist_ok=True)
_log_handler = RotatingFileHandler(
    str(settings.log_file), maxBytes=2*1024*1024, backupCount=3, encoding='utf-8')
_log_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
_log_handler.setLevel(logging.WARNING)
app.logger.addHandler(_log_handler)

# ── Rate limiter simples (sem dependência externa) ───────────
_rate_buckets: dict[str, list[float]] = defaultdict(list)
_RATE_LOCK = threading.Lock()
_SERVER_START = _time.time()

def _rate_limited(key: str, max_hits: int = 5, window: int = 60) -> bool:
    """Retorna True se o key excedeu max_hits em window segundos."""
    now = _time.time()
    with _RATE_LOCK:
        hits = _rate_buckets[key]
        _rate_buckets[key] = [t for t in hits if now - t < window]
        if len(_rate_buckets[key]) >= max_hits:
            return True
        _rate_buckets[key].append(now)
        return False

# ── Cache de arquivos estáticos em RAM ───────────────────────
# Todos os arquivos estáticos são lidos do disco UMA VEZ no startup e
# mantidos em memória. Requisições subsequentes não tocam o OneDrive,
# eliminando a latência do interceptor de sincronização em cada leitura.
import mimetypes as _mimetypes

_file_cache: dict[str, tuple[bytes, str]] = {}   # url_path -> (bytes, mimetype)
_gzip_cache: dict[str, bytes] = {}               # url_path -> gzip(bytes)

_COMPRESSIBLE = {'text/html', 'text/css', 'text/javascript', 'application/javascript',
                 'application/json', 'image/svg+xml', 'text/plain', 'text/xml'}

_SKIP_EXTS = {'.db', '.db-shm', '.db-wal', '.pyc', '.pyo', '.log', '.bat'}
_SKIP_DIRS = {'__pycache__', '.git', 'DADOS', 'renomer', 'documentos_centro',
              'PARA IMPLEMENTAR TODO ESSE PROJETO NO PROJETO PRINCIPAL'}

def _preload_static_files():
    """Lê todos os arquivos estáticos para RAM no startup (+ versões gzip)."""
    count, total_kb = 0, 0
    for root, dirs, files in os.walk(BASE_DIR):
        # Não descer em diretórios que não precisamos servir
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        rel_root = os.path.relpath(root, BASE_DIR).replace('\\', '/')
        if rel_root == '.':
            rel_root = ''
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext in _SKIP_EXTS:
                continue
            fpath = os.path.join(root, fname)
            url = ('/' + rel_root + '/' + fname).replace('//', '/')
            mime, _ = _mimetypes.guess_type(fpath)
            if mime is None:
                mime = 'application/octet-stream'
            try:
                with open(fpath, 'rb') as f:
                    data = f.read()
                _file_cache[url] = (data, mime)
                # Pré-comprime texto para servir gzip sem gastar CPU por request
                base_mime = (mime or '').split(';')[0].strip()
                if base_mime in _COMPRESSIBLE and len(data) > 256:
                    _gzip_cache[url] = _gzip.compress(data, compresslevel=6)
                count += 1
                total_kb += len(data) // 1024
            except OSError:
                pass
    print(f"Cache estático: {count} arquivos, {total_kb} KB em RAM")
    print(f"Cache gzip: {len(_gzip_cache)} arquivos comprimidos")

# ── Banco de Dados ───────────────────────────────────────────
# Conexão thread-local reutilizada durante todo o ciclo de vida da requisição.
# Evita abrir/fechar conexão a cada chamada (crítico em ambientes OneDrive/rede).
_db_local = threading.local()

def get_db():
    """Retorna conexão SQLite persistente por thread (reutilizada entre requests).
    PRAGMAs de performance aplicados em TODA nova conexão (incluindo threads do Flask)."""
    db = getattr(_db_local, 'conn', None)
    if db is None:
        db = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10.0)
        db.row_factory = sqlite3.Row
        # Aplicar PRAGMAs em cada nova conexão — threads do Flask criam conexões
        # independentes e precisam dos mesmos settings para não cair nos defaults lentos
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA journal_mode=DELETE")  # sem WAL (OneDrive não suporta .db-wal)
        db.execute("PRAGMA synchronous=NORMAL")   # sem espera de confirmação do OS a cada write
        db.execute("PRAGMA cache_size=-8000")     # 8MB de cache em memória
        db.execute("PRAGMA temp_store=MEMORY")    # tabelas temporárias em RAM
        db.execute("PRAGMA mmap_size=0")          # desabilita mmap — perigoso no OneDrive
        _db_local.conn = db
    return db

@app.teardown_appcontext
def close_db(exception):
    # Conexão mantida aberta entre requisições para evitar overhead de re-abertura
    # (crítico em ambientes OneDrive onde abrir arquivo tem latência alta)
    pass

def ensure_db_indexes(cur):
    cur.execute("CREATE INDEX IF NOT EXISTS idx_empenhos_credor ON empenhos(credor_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_empenhos_ano_mes ON empenhos(ano, mes)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_credores_departamento ON credores(departamento)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_credores_nome ON credores(nome)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_credores_ativo ON credores(ativo)")
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

@app.before_request
def mark_request_start():
    g._request_started_at = _time.perf_counter()

@app.after_request
def compress_response(response):
    """Comprime respostas JSON/texto da API com gzip e adiciona cache headers."""
    started_at = getattr(g, '_request_started_at', None)
    if started_at is not None:
        elapsed_ms = (_time.perf_counter() - started_at) * 1000
        response.headers['X-Response-Time-ms'] = f'{elapsed_ms:.1f}'
        if request.path.startswith('/api/') and elapsed_ms >= 250:
            app.logger.warning('Slow request %.1fms %s %s [%s]', elapsed_ms, request.method, request.path, response.status_code)
    # Cache-Control para APIs GET (dados mudam pouco entre requests)
    if (request.method == 'GET' and request.path.startswith('/api/')
            and response.status_code == 200
            and 'Cache-Control' not in response.headers):
        response.headers['Cache-Control'] = 'public, max-age=5'

    if (response.status_code < 200 or response.status_code >= 300
            or response.direct_passthrough
            or 'Content-Encoding' in response.headers):
        return response
    mime = (response.content_type or '').split(';')[0].strip()
    if mime in _COMPRESSIBLE and 'gzip' in request.headers.get('Accept-Encoding', ''):
        data = response.get_data()
        if len(data) > 256:
            response.set_data(_gzip.compress(data, compresslevel=6))
            response.headers['Content-Encoding'] = 'gzip'
            response.headers['Vary'] = 'Accept-Encoding'
            response.headers['Content-Length'] = len(response.get_data())
    return response

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
    cur.execute("""
        CREATE TABLE IF NOT EXISTS documentos_centro (
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
    ensure_db_indexes(cur)
    conn.commit()


def init_db():
    """Cria as tabelas e popula credores iniciais a partir do data.js."""
    conn = get_db()
    cur  = conn.cursor()

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
    cur.execute("""
        CREATE TABLE IF NOT EXISTS documentos_centro (
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
        )
    """)

    # Popula credores iniciais se a tabela estiver vazia
    count = cur.execute("SELECT COUNT(*) FROM credores").fetchone()[0]
    if count == 0 and os.path.exists(DATA_JS):
        print("Populando banco com dados do data.js...")
        _seed_from_data_js(cur)

    ensure_db_indexes(cur)

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

def _slugify(value: str, fallback: str = 'geral') -> str:
    text = (value or '').strip().lower()
    text = re.sub(r'[^a-z0-9_-]+', '-', text)
    text = re.sub(r'-+', '-', text).strip('-')
    return text or fallback

def _build_document_storage(categoria: str, referencia: str, original_name: str) -> tuple[str, str, str]:
    categoria_slug = _slugify(categoria, 'geral')
    referencia_slug = _slugify(referencia, 'sem-referencia') if referencia else 'sem-referencia'
    ext = os.path.splitext(original_name or '')[1].lower()
    ext = ext[:20]
    unique_name = f"{int(_time.time() * 1000)}_{hashlib.sha1((original_name + str(_time.time())).encode()).hexdigest()[:10]}{ext}"
    relative_dir = os.path.join(categoria_slug, referencia_slug)
    abs_dir = os.path.join(DOCUMENTS_DIR, relative_dir)
    os.makedirs(abs_dir, exist_ok=True)
    return unique_name, relative_dir.replace('\\', '/'), os.path.join(abs_dir, unique_name)

def _persist_document_file(original_name: str, content: bytes, categoria: str = 'gerados', referencia: str = '', descricao: str = '', mime_type: str = ''):
    nome_arquivo, relative_dir, abs_path = _build_document_storage(categoria, referencia, original_name)
    with open(abs_path, 'wb') as fh:
        fh.write(content)
    tamanho = os.path.getsize(abs_path)
    extensao = os.path.splitext(original_name)[1].lower()
    caminho_relativo = f"{relative_dir}/{nome_arquivo}" if relative_dir else nome_arquivo
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO documentos_centro (nome_original, nome_arquivo, categoria, referencia, descricao, tamanho, extensao, caminho_relativo) VALUES (?,?,?,?,?,?,?,?)",
        (original_name, nome_arquivo, categoria, referencia, descricao, tamanho, extensao, caminho_relativo)
    )
    new_id = cur.lastrowid
    conn.commit()
    row = conn.execute("SELECT * FROM documentos_centro WHERE id=?", (new_id,)).fetchone()
    return row_to_dict(row)

def _serve_cached(url, cache_control):
    """Serve arquivo do cache com gzip se o cliente aceitar."""
    entry = _file_cache.get(url)
    if not entry:
        return None
    data, mime = entry
    headers = {'Cache-Control': cache_control}
    accept_enc = request.headers.get('Accept-Encoding', '')
    gz = _gzip_cache.get(url)
    if gz and 'gzip' in accept_enc:
        headers['Content-Encoding'] = 'gzip'
        headers['Vary'] = 'Accept-Encoding'
        headers['Content-Length'] = len(gz)
        return Response(gz, mimetype=mime, headers=headers)
    return Response(data, mimetype=mime, headers=headers)

# ────────────────────────────────────────────────────────────
# ROTAS – Statics
# ────────────────────────────────────────────────────────────

@app.route('/')
def index():
    resp = _serve_cached('/index.html', 'no-cache, no-store, must-revalidate')
    if resp:
        return resp
    r = send_file(os.path.join(BASE_DIR, 'index.html'))
    r.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return r


@app.route('/static/<path:filename>')
def static_cached(filename):
    url = '/static/' + filename
    resp = _serve_cached(url, 'public, max-age=86400')
    if resp:
        return resp
    r = send_from_directory(os.path.join(BASE_DIR, 'static'), filename)
    r.headers['Cache-Control'] = 'public, max-age=86400'
    return r


@app.route('/<path:filename>')
def static_files(filename):
    if filename.startswith('api/'):
        return jsonify({'error': 'Rota não encontrada: ' + filename}), 404
    url = '/' + filename
    cc = 'no-cache, no-store, must-revalidate' if filename.endswith('.html') else 'public, max-age=3600'
    resp = _serve_cached(url, cc)
    if resp:
        return resp
    r = send_from_directory(BASE_DIR, filename)
    if filename.endswith('.html'):
        r.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return r

@app.errorhandler(404)
def not_found(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Rota não encontrada', 'path': request.path}), 404
    return str(e), 404

@app.errorhandler(500)
def server_error(e):
    app.logger.error('500 em %s: %s', request.path, e)
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Erro interno do servidor', 'detail': str(e)}), 500
    return str(e), 500

# ────────────────────────────────────────────────────────────
# API – Autenticação ADM
# ────────────────────────────────────────────────────────────

# Senha armazenada como hash SHA-256 — nunca em texto puro em memória
_ADM_RAW = settings.admin_password
_ADM_HASH = hashlib.sha256(_ADM_RAW.encode()).hexdigest()
del _ADM_RAW  # limpa texto puro da memória

@app.route('/api/auth/adm', methods=['POST'])
def auth_adm():
    """Verifica a senha da área administrativa (com rate limit)."""
    ip = request.remote_addr or 'unknown'
    if _rate_limited(f'auth:{ip}', max_hits=5, window=60):
        app.logger.warning('Rate limit auth: %s', ip)
        return jsonify({'ok': False, 'error': 'Muitas tentativas. Aguarde 1 minuto.'}), 429
    d = request.get_json(force=True) or {}
    senha = d.get('senha', '')
    if hashlib.sha256(senha.encode()).hexdigest() == _ADM_HASH:
        return jsonify({'ok': True})
    app.logger.warning('Senha incorreta de %s', ip)
    return jsonify({'ok': False, 'error': 'Senha incorreta'}), 401

@app.route('/api/ping', methods=['GET'])
def ping():
    return jsonify({'ok': True})

@app.route('/api/health', methods=['GET'])
def health():
    """Status do servidor para monitoramento."""
    try:
        conn = get_db()
        conn.execute("SELECT 1").fetchone()
        db_ok = True
    except Exception:
        db_ok = False
    return jsonify({
        'status': 'ok' if db_ok else 'degraded',
        'db': db_ok,
        'uptime_s': int(_time.time() - _SERVER_START),
        'cache_files': len(_file_cache),
        'cache_gzip': len(_gzip_cache),
    })

@app.route('/api/credores', methods=['GET'])
def get_credores():
    try:
        limit = request.args.get('limit', 1000, type=int)
        offset = request.args.get('offset', 0, type=int)
        conn = get_db()
        rows = conn.execute(
            "SELECT * FROM credores WHERE ativo=1 ORDER BY departamento, nome LIMIT ? OFFSET ?",
            (limit, offset)
        ).fetchall()
        return jsonify([row_to_dict(r) for r in rows])
    except Exception as e:
        app.logger.error('GET /api/credores: %s', e)
        return jsonify({'error': str(e)}), 500

@app.route('/api/credores', methods=['POST'])
def add_credor():
    data = request.get_json()
    if not data or not data.get('nome', '').strip():
        return jsonify({'error': 'Campo "nome" é obrigatório'}), 400
    try:
        conn = get_db()
        cur  = conn.cursor()
        cur.execute("""
            INSERT INTO credores
              (nome, valor, descricao, cnpj, email, tipo_valor, solicitacao, pagamento, departamento, obs)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (
            data.get('nome', '').upper(),
            float(data.get('valor') or 0),
            (data.get('descricao') or '').upper(),
            data.get('cnpj', ''),
            data.get('email', ''),
            data.get('tipo_valor', 'FIXO'),
            data.get('solicitacao', ''),
            data.get('pagamento', ''),
            data.get('departamento', ''),
            (data.get('obs') or '').upper(),
        ))
        new_id = cur.lastrowid
        conn.commit()
        conn.commit()
        
        row = conn.execute("SELECT * FROM credores WHERE id=?", (new_id,)).fetchone()
        return jsonify(row_to_dict(row)), 201
    except Exception as e:
        app.logger.error('POST /api/credores: %s', e)
        return jsonify({'error': str(e)}), 500

@app.route('/api/empenhos/<int:ano>/<int:mes>', methods=['GET'])
def get_empenhos(ano, mes):
    try:
        conn = get_db()
        return jsonify(listar_empenhos_mes(conn, ano, mes, row_to_dict))
    except Exception as e:
        app.logger.error('GET /api/empenhos/%s/%s: %s', ano, mes, e)
        return jsonify({'error': str(e)}), 500

@app.route('/api/empenhos', methods=['POST'])
def toggle_empenho():
    d = request.get_json(force=True) or {}
    credor_id = d.get('credor_id')
    ano = d.get('ano')
    mes = d.get('mes')
    if not credor_id or not ano or not mes:
        return jsonify({'error': 'credor_id, ano e mes são obrigatórios'}), 400
    try:
        conn = get_db()
        result = persistir_empenho(conn, credor_id, ano, mes, _time.strftime('%Y-%m-%d %H:%M:%S'))
        conn.commit()
        return jsonify({'ok': True, 'empenhado': result['empenhado']})
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        app.logger.error('POST /api/empenhos: %s', e)
        return jsonify({'error': str(e)}), 500

@app.route('/api/empenhos/lote', methods=['POST'])
def empenho_lote():
    d = request.get_json(force=True) or {}
    itens = d.get('itens') or []
    if not itens:
        return jsonify({'error': 'Nenhum item informado'}), 400
    try:
        conn = get_db()
        resultados = []
        for item in itens:
            credor_id = item.get('credor_id')
            ano = item.get('ano')
            mes = item.get('mes')
            if not credor_id or not ano or not mes:
                return jsonify({'error': 'Todos os itens devem conter credor_id, ano e mes'}), 400
            resultados.append(persistir_empenho(conn, credor_id, ano, mes, _time.strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()
        return jsonify({'ok': True, 'resultados': resultados})
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        app.logger.error('POST /api/empenhos/lote: %s', e)
        return jsonify({'error': str(e)}), 500

@app.route('/api/credores/<int:cid>/historico', methods=['GET'])
def get_historico_credor(cid):
    meses = request.args.get('meses', 6, type=int)
    meses = max(1, min(meses, 24))
    try:
        conn = get_db()
        return jsonify(listar_historico_credor(conn, cid, meses, _time.localtime()))
    except Exception as e:
        app.logger.error('GET /api/credores/%s/historico: %s', cid, e)
        return jsonify({'error': str(e)}), 500

@app.route('/api/config', methods=['GET'])
def config_get():
    try:
        conn = get_db()
        rows = conn.execute("SELECT chave, valor FROM configuracoes").fetchall()
        return jsonify({r['chave']: r['valor'] for r in rows if r['chave'] in ALLOWED_CONFIG_KEYS})
    except Exception as e:
        app.logger.error('GET /api/config: %s', e)
        return jsonify({'error': str(e)}), 500

@app.route('/api/config', methods=['POST'])
def config_set():
    d = request.get_json(force=True)
    try:
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
    except Exception as e:
        app.logger.error('POST /api/config: %s', e)
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/summary', methods=['GET'])
def admin_summary():
    try:
        conn = get_db()
        rows = conn.execute(
            "SELECT chave, valor, atualizado_em FROM configuracoes WHERE chave IN (?,?,?)",
            ('api_openrouter_key', 'api_openrouter_modelo', 'api_cnpja_key')
        ).fetchall()
        cfg = {row['chave']: row_to_dict(row) for row in rows}

        credores_ativos = conn.execute("SELECT COUNT(*) AS total FROM credores WHERE ativo=1").fetchone()['total']
        rpas_total = conn.execute("SELECT COUNT(*) AS total FROM rpas").fetchone()['total']
        kanban_total = conn.execute("SELECT COUNT(*) AS total FROM kanban_tasks").fetchone()['total']
        importacoes_total = conn.execute("SELECT COUNT(*) AS total FROM empenhos_importacoes").fetchone()['total']
        logs_total = conn.execute("SELECT COUNT(*) AS total FROM logs").fetchone()['total']
        recent_logs = conn.execute(
            "SELECT id, acao, credor_id, credor_nome, detalhes, data FROM logs ORDER BY data DESC LIMIT 8"
        ).fetchall()

        try:
            conn.execute("SELECT 1").fetchone()
            db_ok = True
        except Exception:
            db_ok = False

        return jsonify({
            'overview': {
                'credores_ativos': credores_ativos,
                'rpas_total': rpas_total,
                'kanban_total': kanban_total,
                'importacoes_total': importacoes_total,
                'logs_total': logs_total,
            },
            'health': {
                'status': 'ok' if db_ok else 'degraded',
                'db': db_ok,
                'uptime_s': int(_time.time() - _SERVER_START),
                'cache_files': len(_file_cache),
                'cache_gzip': len(_gzip_cache),
            },
            'config_status': {
                'openrouter_key_configured': bool(cfg.get('api_openrouter_key', {}).get('valor', '').strip()),
                'openrouter_model': cfg.get('api_openrouter_modelo', {}).get('valor', settings.openrouter_default_model) or settings.openrouter_default_model,
                'openrouter_updated_at': cfg.get('api_openrouter_key', {}).get('atualizado_em') or cfg.get('api_openrouter_modelo', {}).get('atualizado_em'),
                'cnpja_key_configured': bool(cfg.get('api_cnpja_key', {}).get('valor', '').strip()),
                'cnpja_updated_at': cfg.get('api_cnpja_key', {}).get('atualizado_em'),
            },
            'recent_logs': [row_to_dict(row) for row in recent_logs],
            'technical': {
                'host': settings.host,
                'port': settings.port,
                'debug': settings.debug,
                'db_path': DB_PATH,
                'log_file': str(settings.log_file),
                'base_dir': BASE_DIR,
            }
        })
    except Exception as e:
        app.logger.error('GET /api/admin/summary: %s', e)
        return jsonify({'error': str(e)}), 500

@app.route('/api/kanban', methods=['GET'])
def kanban_listar():
    try:
        conn = get_db()
        rows = conn.execute(
            "SELECT id, title, description, status, priority, criado_em, atualizado_em FROM kanban_tasks ORDER BY atualizado_em DESC, criado_em DESC"
        ).fetchall()
        return jsonify([row_to_dict(r) for r in rows])
    except Exception as e:
        app.logger.error('GET /api/kanban: %s', e)
        return jsonify({'error': str(e)}), 500

@app.route('/api/kanban', methods=['POST'])
def kanban_criar():
    try:
        data = request.get_json(force=True) or {}
        task_id = (data.get('id') or '').strip()
        title = (data.get('title') or '').strip()
        description = (data.get('description') or '').strip()
        status = (data.get('status') or 'todo').strip()
        priority = (data.get('priority') or 'medium').strip()
        if not task_id:
            return jsonify({'error': 'id é obrigatório'}), 400
        if not title:
            return jsonify({'error': 'title é obrigatório'}), 400
        if status not in {'todo', 'in-progress', 'done'}:
            status = 'todo'
        if priority not in {'low', 'medium', 'high'}:
            priority = 'medium'
        conn = get_db()
        conn.execute(
            "INSERT INTO kanban_tasks (id, title, description, status, priority, criado_em, atualizado_em) VALUES (?,?,?,?,?,datetime('now','localtime'),datetime('now','localtime'))",
            (task_id, title, description, status, priority)
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, title, description, status, priority, criado_em, atualizado_em FROM kanban_tasks WHERE id=?",
            (task_id,)
        ).fetchone()
        return jsonify(row_to_dict(row)), 201
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Já existe uma tarefa com esse id'}), 409
    except Exception as e:
        app.logger.error('POST /api/kanban: %s', e)
        return jsonify({'error': str(e)}), 500

@app.route('/api/kanban/<task_id>', methods=['PUT'])
def kanban_atualizar(task_id):
    try:
        data = request.get_json(force=True) or {}
        title = (data.get('title') or '').strip()
        description = (data.get('description') or '').strip()
        status = (data.get('status') or 'todo').strip()
        priority = (data.get('priority') or 'medium').strip()
        if not title:
            return jsonify({'error': 'title é obrigatório'}), 400
        if status not in {'todo', 'in-progress', 'done'}:
            status = 'todo'
        if priority not in {'low', 'medium', 'high'}:
            priority = 'medium'
        conn = get_db()
        cur = conn.execute(
            "UPDATE kanban_tasks SET title=?, description=?, status=?, priority=?, atualizado_em=datetime('now','localtime') WHERE id=?",
            (title, description, status, priority, task_id)
        )
        if cur.rowcount == 0:
            return jsonify({'error': 'Tarefa não encontrada'}), 404
        conn.commit()
        row = conn.execute(
            "SELECT id, title, description, status, priority, criado_em, atualizado_em FROM kanban_tasks WHERE id=?",
            (task_id,)
        ).fetchone()
        return jsonify(row_to_dict(row))
    except Exception as e:
        app.logger.error('PUT /api/kanban/%s: %s', task_id, e)
        return jsonify({'error': str(e)}), 500

@app.route('/api/kanban/<task_id>', methods=['DELETE'])
def kanban_excluir(task_id):
    try:
        conn = get_db()
        cur = conn.execute("DELETE FROM kanban_tasks WHERE id=?", (task_id,))
        conn.commit()
        if cur.rowcount == 0:
            return jsonify({'error': 'Tarefa não encontrada'}), 404
        return jsonify({'ok': True})
    except Exception as e:
        app.logger.error('DELETE /api/kanban/%s: %s', task_id, e)
        return jsonify({'error': str(e)}), 500

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
        'endereco': f"{d.get('logradouro','')} {d.get('numero','')}".strip(),
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

@app.route('/api/documentos', methods=['GET'])
def documentos_listar():
    try:
        categoria = (request.args.get('categoria') or '').strip()
        referencia = (request.args.get('referencia') or '').strip()
        conn = get_db()
        sql = "SELECT * FROM documentos_centro WHERE 1=1"
        params = []
        if categoria:
            sql += " AND categoria=?"
            params.append(categoria)
        if referencia:
            sql += " AND referencia LIKE ?"
            params.append(f"%{referencia}%")
        sql += " ORDER BY criado_em DESC, id DESC"
        rows = conn.execute(sql, tuple(params)).fetchall()
        return jsonify([row_to_dict(r) for r in rows])
    except Exception as e:
        app.logger.error('GET /api/documentos: %s', e)
        return jsonify({'error': str(e)}), 500

@app.route('/api/documentos', methods=['POST'])
def documentos_enviar():
    file = request.files.get('arquivo')
    categoria = (request.form.get('categoria') or 'geral').strip()
    referencia = (request.form.get('referencia') or '').strip()
    descricao = (request.form.get('descricao') or '').strip()
    if not file or not file.filename:
        return jsonify({'error': 'Arquivo é obrigatório'}), 400
    try:
        nome_arquivo, relative_dir, abs_path = _build_document_storage(categoria, referencia, file.filename)
        file.save(abs_path)
        tamanho = os.path.getsize(abs_path)
        extensao = os.path.splitext(file.filename)[1].lower()
        caminho_relativo = f"{relative_dir}/{nome_arquivo}" if relative_dir else nome_arquivo
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO documentos_centro (nome_original, nome_arquivo, categoria, referencia, descricao, tamanho, extensao, caminho_relativo) VALUES (?,?,?,?,?,?,?,?)",
            (file.filename, nome_arquivo, categoria, referencia, descricao, tamanho, extensao, caminho_relativo)
        )
        new_id = cur.lastrowid
        conn.commit()
        row = conn.execute("SELECT * FROM documentos_centro WHERE id=?", (new_id,)).fetchone()
        return jsonify(row_to_dict(row)), 201
    except Exception as e:
        app.logger.error('POST /api/documentos: %s', e)
        return jsonify({'error': str(e)}), 500

@app.route('/api/documentos/conteudo', methods=['POST'])
def documentos_salvar_conteudo():
    try:
        nome = (request.form.get('nome') or '').strip()
        categoria = (request.form.get('categoria') or 'gerados').strip()
        referencia = (request.form.get('referencia') or '').strip()
        descricao = (request.form.get('descricao') or '').strip()
        arquivo = request.files.get('arquivo')
        if not nome or not arquivo:
            return jsonify({'error': 'nome e arquivo são obrigatórios'}), 400
        saved = _persist_document_file(nome, arquivo.read(), categoria, referencia, descricao, arquivo.mimetype or '')
        return jsonify(saved), 201
    except Exception as e:
        app.logger.error('POST /api/documentos/conteudo: %s', e)
        return jsonify({'error': str(e)}), 500

@app.route('/api/documentos/<int:doc_id>/download', methods=['GET'])
def documentos_download(doc_id):
    try:
        conn = get_db()
        row = conn.execute("SELECT * FROM documentos_centro WHERE id=?", (doc_id,)).fetchone()
        if not row:
            return jsonify({'error': 'Documento não encontrado'}), 404
        abs_path = os.path.join(DOCUMENTS_DIR, row['caminho_relativo'].replace('/', os.sep))
        if not os.path.exists(abs_path):
            return jsonify({'error': 'Arquivo físico não encontrado'}), 404
        mime, _ = mimetypes.guess_type(abs_path)
        return send_file(abs_path, mimetype=mime or 'application/octet-stream', as_attachment=True, download_name=row['nome_original'])
    except Exception as e:
        app.logger.error('GET /api/documentos/%s/download: %s', doc_id, e)
        return jsonify({'error': str(e)}), 500

@app.route('/api/documentos/<int:doc_id>', methods=['DELETE'])
def documentos_excluir(doc_id):
    try:
        conn = get_db()
        row = conn.execute("SELECT * FROM documentos_centro WHERE id=?", (doc_id,)).fetchone()
        if not row:
            return jsonify({'error': 'Documento não encontrado'}), 404
        abs_path = os.path.join(DOCUMENTS_DIR, row['caminho_relativo'].replace('/', os.sep))
        conn.execute("DELETE FROM documentos_centro WHERE id=?", (doc_id,))
        conn.commit()
        if os.path.exists(abs_path):
            try:
                os.remove(abs_path)
            except OSError as file_err:
                app.logger.warning('Arquivo de documento não removido imediatamente %s: %s', abs_path, file_err)
                return jsonify({'ok': True, 'file_removed': False})
        return jsonify({'ok': True, 'file_removed': True})
    except Exception as e:
        app.logger.error('DELETE /api/documentos/%s: %s', doc_id, e)
        return jsonify({'error': str(e)}), 500

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
    _persist_document_file('mesclado.pdf', buf.getvalue(), 'gerados_pdf', 'mesclar', 'PDF gerado automaticamente pelo módulo de mesclagem', 'application/pdf')
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
        _persist_document_file(groups[0][0], buf.getvalue(), 'gerados_pdf', 'dividir', 'PDF gerado automaticamente pelo módulo de divisão', 'application/pdf')
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
    _persist_document_file('dividido.zip', zip_buf.getvalue(), 'gerados_pdf', 'dividir', 'ZIP gerado automaticamente pelo módulo de divisão de PDF', 'application/zip')
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
    _persist_document_file('protegido.pdf', buf.getvalue(), 'gerados_pdf', 'proteger', 'PDF protegido gerado automaticamente', 'application/pdf')
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

init_db()
migrate_db()

# ────────────────────────────────────────────────────────────
# MAIN
# ────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import socket
    init_db()
    migrate_db()
    _preload_static_files()   # carrega todos os arquivos estáticos em RAM

    # ── Fix de performance: Werkzeug faz reverse-DNS lookup em cada requisição
    #    via socket.getfqdn(), o que trava ~2s no Windows. Desabilitamos isso.
    #    Também habilitamos HTTP/1.1 para keep-alive (reutiliza conexão TCP).
    try:
        from werkzeug.serving import WSGIRequestHandler
        WSGIRequestHandler.address_string = lambda self: self.client_address[0]
        WSGIRequestHandler.protocol_version = 'HTTP/1.1'
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
    print(f'  Local  : http://localhost:{settings.port}')
    print(f'  Rede   : http://{local_ip}:{settings.port}   << compartilhe este link')
    print('  Para encerrar: feche esta janela ou pressione Ctrl+C')
    print('=' * 60)
    app.run(host=settings.host, port=settings.port, debug=settings.debug, threaded=True)
