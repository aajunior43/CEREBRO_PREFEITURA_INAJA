import os
import re
import time as _time
import hashlib
import gzip as _gzip
import mimetypes as _mimetypes

from flask import Blueprint, request, jsonify, send_file, send_from_directory, Response, g, current_app
from config import settings
from database import get_db, row_to_dict, BASE_DIR, DB_PATH
from helpers import (
    _terminal_log, _terminal_request_line, _rate_limited,
    _parse_bool, _SERVER_START, _fmt_bytes,
)

bp = Blueprint('core', __name__)

ALLOWED_CONFIG_KEYS = {
    'api_openrouter_key',
    'api_openrouter_modelo',
    'api_cnpja_key',
    'api_autentique_key',
}

_ADM_RAW = settings.admin_password
_ADM_HASH = hashlib.sha256(_ADM_RAW.encode()).hexdigest()
del _ADM_RAW

_file_cache:   dict[str, tuple[bytes, str]] = {}
_gzip_cache:   dict[str, bytes] = {}
_brotli_cache: dict[str, bytes] = {}
_etag_cache:   dict[str, str]   = {}
_file_mtime_cache: dict[str, float] = {}

try:
    import brotli as _brotli
    _BROTLI_OK = True
except ImportError:
    _BROTLI_OK = False

_COMPRESSIBLE = {'text/html', 'text/css', 'text/javascript', 'application/javascript',
                 'application/json', 'image/svg+xml', 'text/plain', 'text/xml'}

_SKIP_EXTS = {'.db', '.db-shm', '.db-wal', '.pyc', '.pyo', '.log', '.bat'}
_SKIP_DIRS = {'__pycache__', '.git', 'DADOS', 'renomer', 'documentos_centro',
              'PARA IMPLEMENTAR TODO ESSE PROJETO NO PROJETO PRINCIPAL'}


def _url_to_static_path(url: str) -> str:
    rel = (url or '/').lstrip('/')
    if not rel:
      rel = 'index.html'
    return os.path.join(BASE_DIR, rel.replace('/', os.sep))


def _refresh_cached_file(url: str) -> bool:
    path = _url_to_static_path(url)
    if not os.path.isfile(path):
        return False
    mime, _ = _mimetypes.guess_type(path)
    if mime is None:
        mime = 'application/octet-stream'
    try:
        with open(path, 'rb') as f:
            data = f.read()
        _file_cache[url] = (data, mime)
        _etag_cache[url] = hashlib.md5(data).hexdigest()[:16]
        _file_mtime_cache[url] = os.path.getmtime(path)
        _gzip_cache.pop(url, None)
        _brotli_cache.pop(url, None)
        base_mime = (mime or '').split(';')[0].strip()
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


def preload_static_files():
    count, total_kb = 0, 0
    started_at = _time.perf_counter()
    _terminal_log('BOOT', 'Pré-carregando arquivos estáticos em RAM...', 'cyan')
    for root, dirs, files in os.walk(BASE_DIR):
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
                if _refresh_cached_file(url):
                    data, _ = _file_cache[url]
                    count += 1
                    total_kb += len(data) // 1024
            except OSError:
                pass
    elapsed_ms = (_time.perf_counter() - started_at) * 1000
    _terminal_log('CACHE', f'{count} arquivos carregados em RAM ({_fmt_bytes(total_kb * 1024)})', 'green')
    enc_count = max(len(_brotli_cache), len(_gzip_cache))
    enc_name = 'brotli+gzip' if _BROTLI_OK else 'gzip'
    _terminal_log('GZIP', f'{enc_count} arquivos com versão {enc_name} prontos em {elapsed_ms:.1f} ms', 'green')


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

    if etag and request.headers.get('If-None-Match') == f'"{etag}"':
        return Response(status=304, headers={
            'Cache-Control': cache_control,
            'ETag': f'"{etag}"',
        })

    headers = {'Cache-Control': cache_control}
    if etag:
        headers['ETag'] = f'"{etag}"'

    accept_enc = request.headers.get('Accept-Encoding', '')
    br = _brotli_cache.get(url)
    gz = _gzip_cache.get(url)
    if br and 'br' in accept_enc:
        headers['Content-Encoding'] = 'br'
        headers['Vary'] = 'Accept-Encoding'
        headers['Content-Length'] = len(br)
        return Response(br, mimetype=mime, headers=headers)
    if gz and 'gzip' in accept_enc:
        headers['Content-Encoding'] = 'gzip'
        headers['Vary'] = 'Accept-Encoding'
        headers['Content-Length'] = len(gz)
        return Response(gz, mimetype=mime, headers=headers)
    headers['Content-Length'] = len(data)
    return Response(data, mimetype=mime, headers=headers)


@bp.before_app_request
def mark_request_start():
    g._request_started_at = _time.perf_counter()
    g._request_path = request.path
    g._request_full_path = request.full_path.rstrip('?')
    g._request_ip = request.headers.get('X-Forwarded-For', request.remote_addr or '-').split(',')[0].strip()


@bp.after_app_request
def compress_response(response):
    started_at = getattr(g, '_request_started_at', None)
    if started_at is not None:
        elapsed_ms = (_time.perf_counter() - started_at) * 1000
        response.headers['X-Response-Time-ms'] = f'{elapsed_ms:.1f}'
        if request.path.startswith('/api/'):
            _terminal_request_line(
                request.method,
                getattr(g, '_request_full_path', request.path),
                response.status_code,
                elapsed_ms,
                getattr(g, '_request_ip', '-')
            )
        if request.path.startswith('/api/') and elapsed_ms >= 250:
            current_app.logger.warning('Slow request %.1fms %s %s [%s]', elapsed_ms, request.method, request.path, response.status_code)
    if (request.method == 'GET' and request.path.startswith('/api/')
            and response.status_code == 200
            and 'Cache-Control' not in response.headers):
        response.headers['Cache-Control'] = 'public, max-age=20'

    if (response.status_code < 200 or response.status_code >= 300
            or response.direct_passthrough
            or 'Content-Encoding' in response.headers):
        return response
    mime = (response.content_type or '').split(';')[0].strip()
    if mime in _COMPRESSIBLE and 'gzip' in request.headers.get('Accept-Encoding', ''):
        data = response.get_data()
        if len(data) > 256:
            response.set_data(_gzip.compress(data, compresslevel=4))
            response.headers['Content-Encoding'] = 'gzip'
            response.headers['Vary'] = 'Accept-Encoding'
            response.headers['Content-Length'] = len(response.get_data())
    return response


@bp.app_errorhandler(404)
def not_found(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Rota não encontrada', 'path': request.path}), 404
    return str(e), 404


@bp.app_errorhandler(500)
def server_error(e):
    current_app.logger.error('500 em %s: %s', request.path, e)
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Erro interno do servidor', 'detail': str(e)}), 500
    return str(e), 500


@bp.route('/')
def index():
    resp = _serve_cached('/index.html', 'no-cache, no-store, must-revalidate')
    if resp:
        return resp
    r = send_file(os.path.join(BASE_DIR, 'index.html'))
    r.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return r


@bp.route('/static/<path:filename>')
def static_cached(filename):
    url = '/static/' + filename
    ext = os.path.splitext(filename)[1].lower()
    if ext in {'.js', '.css', '.html'}:
        cc = 'no-cache, must-revalidate'
    elif ext in {'.woff2', '.woff', '.ttf', '.otf', '.eot'}:
        cc = 'public, max-age=31536000, immutable'
    else:
        cc = 'public, max-age=86400'
    resp = _serve_cached(url, cc)
    if resp:
        return resp
    r = send_from_directory(os.path.join(BASE_DIR, 'static'), filename)
    r.headers['Cache-Control'] = cc
    return r


@bp.route('/<path:filename>')
def static_files(filename):
    if filename.startswith('api/'):
        return jsonify({'error': 'Rota não encontrada: ' + filename}), 404
    url = '/' + filename
    cc = 'no-cache, must-revalidate' if filename.endswith('.html') else 'public, max-age=3600'
    resp = _serve_cached(url, cc)
    if resp:
        return resp
    r = send_from_directory(BASE_DIR, filename)
    if filename.endswith('.html'):
        r.headers['Cache-Control'] = 'no-cache, must-revalidate'
    return r


@bp.route('/api/auth/adm', methods=['POST'])
def auth_adm():
    ip = request.remote_addr or 'unknown'
    if _rate_limited(f'auth:{ip}', max_hits=5, window=60):
        current_app.logger.warning('Rate limit auth: %s', ip)
        return jsonify({'ok': False, 'error': 'Muitas tentativas. Aguarde 1 minuto.'}), 429
    d = request.get_json(force=True) or {}
    senha = d.get('senha', '')
    if hashlib.sha256(senha.encode()).hexdigest() == _ADM_HASH:
        return jsonify({'ok': True})
    current_app.logger.warning('Senha incorreta de %s', ip)
    return jsonify({'ok': False, 'error': 'Senha incorreta'}), 401


@bp.route('/api/ping', methods=['GET'])
def ping():
    return jsonify({'ok': True})


@bp.route('/api/health', methods=['GET'])
def health():
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


@bp.route('/api/config', methods=['GET'])
def config_get():
    try:
        conn = get_db()
        rows = conn.execute("SELECT chave, valor FROM configuracoes").fetchall()
        return jsonify({r['chave']: r['valor'] for r in rows if r['chave'] in ALLOWED_CONFIG_KEYS})
    except Exception as e:
        current_app.logger.error('GET /api/config: %s', e)
        return jsonify({'error': str(e)}), 500


@bp.route('/api/config', methods=['POST'])
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
        current_app.logger.error('POST /api/config: %s', e)
        return jsonify({'error': str(e)}), 500


@bp.route('/api/admin/summary', methods=['GET'])
def admin_summary():
    try:
        from blueprints.autentique import _parse_autentique_keys
        conn = get_db()
        rows = conn.execute(
            "SELECT chave, valor, atualizado_em FROM configuracoes WHERE chave IN (?,?,?,?)",
            ('api_openrouter_key', 'api_openrouter_modelo', 'api_cnpja_key', 'api_autentique_key')
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
                'autentique_key_configured': bool(_parse_autentique_keys(cfg.get('api_autentique_key', {}).get('valor', ''))),
                'autentique_key_count': len(_parse_autentique_keys(cfg.get('api_autentique_key', {}).get('valor', ''))),
                'autentique_updated_at': cfg.get('api_autentique_key', {}).get('atualizado_em'),
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
        current_app.logger.error('GET /api/admin/summary: %s', e)
        return jsonify({'error': str(e)}), 500


@bp.route('/api/logs', methods=['GET'])
def get_logs():
    try:
        conn = get_db()
        limit  = min(int(request.args.get('limit',  50)), 200)
        offset = int(request.args.get('offset', 0))
        acao   = (request.args.get('acao') or '').strip()
        if acao:
            total = conn.execute("SELECT COUNT(*) FROM logs WHERE acao=?", (acao,)).fetchone()[0]
            rows  = conn.execute(
                "SELECT id,acao,credor_id,credor_nome,detalhes,data FROM logs "
                "WHERE acao=? ORDER BY data DESC LIMIT ? OFFSET ?",
                (acao, limit, offset)
            ).fetchall()
        else:
            total = conn.execute("SELECT COUNT(*) FROM logs").fetchone()[0]
            rows  = conn.execute(
                "SELECT id,acao,credor_id,credor_nome,detalhes,data FROM logs "
                "ORDER BY data DESC LIMIT ? OFFSET ?",
                (limit, offset)
            ).fetchall()
        return jsonify({'logs': [row_to_dict(r) for r in rows], 'total': total})
    except Exception as e:
        current_app.logger.error('GET /api/logs: %s', e)
        return jsonify({'error': str(e)}), 500
