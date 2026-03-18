"""
server.py — Servidor Flask + SQLite para o Sistema de Empenhos Mensais
Prefeitura Municipal de Inajá

Para iniciar: python server.py
Ou duplo clique em iniciar.bat
"""

import os
import logging
from logging.handlers import RotatingFileHandler

from flask import Flask
from config import settings
from database import get_db, close_db, BASE_DIR
from migrations import run_migrations, seed_from_data_js
from blueprints import register_all_blueprints
from blueprints.core import preload_static_files
from helpers import _terminal_log, _terminal_section


def create_app():
    app = Flask(__name__, static_folder=BASE_DIR)

    _LOG_DIR = str(settings.log_dir)
    os.makedirs(_LOG_DIR, exist_ok=True)
    _log_handler = RotatingFileHandler(
        str(settings.log_file), maxBytes=2*1024*1024, backupCount=3, encoding='utf-8')
    _log_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    _log_handler.setLevel(logging.WARNING)
    app.logger.addHandler(_log_handler)

    register_all_blueprints(app)

    @app.teardown_appcontext
    def _close_db(exception):
        close_db(exception)

    with app.app_context():
        conn = get_db()
        run_migrations(conn)
        seed_from_data_js(conn.cursor(), conn)

    return app


if __name__ == '__main__':
    import socket
    import time as _time
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    boot_started_at = _time.perf_counter()
    _terminal_section('Sistema de Empenhos – Prefeitura Municipal de Inajá')
    _terminal_log('BOOT', 'Iniciando servidor Flask...', 'cyan')

    app = create_app()

    _terminal_log('BOOT', 'Estrutura principal do banco verificada', 'green')
    _terminal_log('BOOT', 'Migrações do banco aplicadas', 'green')

    preload_static_files()

    try:
        from werkzeug.serving import WSGIRequestHandler
        WSGIRequestHandler.address_string = lambda self: self.client_address[0]
        WSGIRequestHandler.protocol_version = 'HTTP/1.1'
    except Exception:
        pass

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        local_ip = s.getsockname()[0]
        s.close()
    except OSError:
        local_ip = '127.0.0.1'
    boot_elapsed_ms = (_time.perf_counter() - boot_started_at) * 1000
    _terminal_section('Servidor pronto')
    _terminal_log('LOCAL', f'http://localhost:{settings.port}', 'green')
    _terminal_log('REDE', f'http://{local_ip}:{settings.port}', 'green')
    _terminal_log('INFO', f'Modo debug: {"ligado" if settings.debug else "desligado"} | Host: {settings.host}', 'yellow')
    _terminal_log('TIME', f'Startup concluído em {boot_elapsed_ms:.1f} ms', 'magenta')
    _terminal_log('INFO', 'Para encerrar: feche esta janela ou pressione Ctrl+C', 'cyan')
    app.run(host=settings.host, port=settings.port, debug=settings.debug, threaded=True)
