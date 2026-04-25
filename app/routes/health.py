"""
app/routes/health.py — Endpoints de health check e monitoramento

Endpoints:
    GET /health          - Status geral do sistema
    GET /health/ready    - Verifica se está pronto para receber requisições
    GET /health/live     - Verifica se está vivo (liveness probe)
"""

from flask import Blueprint, jsonify
from datetime import datetime
import sqlite3

bp = Blueprint('health', __name__)


@bp.route('/health')
def health_check():
    """
    Health check geral do sistema.

    Verifica:
    - Conexão com banco de dados
    - Timestamp atual
    - Versão do sistema

    Returns:
        200: Sistema saudável
        503: Sistema com problemas
    """
    try:
        from app.utils.db import get_db

        # Testar conexão com banco
        conn = get_db()
        conn.execute("SELECT 1").fetchone()

        # Contar registros principais
        credores_count = conn.execute("SELECT COUNT(*) FROM credores WHERE ativo=1").fetchone()[0]
        empenhos_count = conn.execute("SELECT COUNT(*) FROM empenhos").fetchone()[0]

        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'database': {
                'status': 'connected',
                'credores_ativos': credores_count,
                'empenhos_total': empenhos_count
            },
            'version': '1.0.0',
            'service': 'Sistema de Empenhos - Prefeitura de Inajá'
        }), 200

    except sqlite3.Error as e:
        return jsonify({
            'status': 'unhealthy',
            'timestamp': datetime.now().isoformat(),
            'database': {
                'status': 'error',
                'error': str(e)
            }
        }), 503

    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'timestamp': datetime.now().isoformat(),
            'error': str(e)
        }), 503


@bp.route('/health/ready')
def readiness_check():
    """
    Readiness probe - verifica se o sistema está pronto para receber requisições.

    Verifica:
    - Banco de dados acessível
    - Tabelas principais existem
    - Estrutura do banco está correta

    Returns:
        200: Sistema pronto
        503: Sistema não está pronto
    """
    try:
        from app.utils.db import get_db

        conn = get_db()

        # Verificar se tabelas principais existem
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()

        existing_tables = {row[0] for row in tables}

        # Tabelas obrigatórias
        required_tables = {
            'credores',
            'empenhos',
            'logs',
            'rpas',
            'kanban_tasks',
            'documentos_centro'
        }

        missing_tables = required_tables - existing_tables

        if missing_tables:
            return jsonify({
                'status': 'not_ready',
                'reason': 'missing_tables',
                'missing_tables': list(missing_tables),
                'timestamp': datetime.now().isoformat()
            }), 503

        # Verificar se consegue fazer queries básicas
        conn.execute("SELECT COUNT(*) FROM credores").fetchone()
        conn.execute("SELECT COUNT(*) FROM empenhos").fetchone()

        return jsonify({
            'status': 'ready',
            'timestamp': datetime.now().isoformat(),
            'tables': list(existing_tables)
        }), 200

    except Exception as e:
        return jsonify({
            'status': 'not_ready',
            'reason': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 503


@bp.route('/health/live')
def liveness_check():
    """
    Liveness probe - verifica se o processo está vivo.

    Este endpoint deve ser extremamente leve e sempre responder,
    a menos que o processo esteja completamente travado.

    Returns:
        200: Processo está vivo
    """
    return jsonify({
        'status': 'alive',
        'timestamp': datetime.now().isoformat()
    }), 200


@bp.route('/health/metrics')
def metrics():
    """
    Métricas básicas do sistema.

    Returns:
        200: Métricas coletadas
        503: Erro ao coletar métricas
    """
    try:
        from app.utils.db import get_db
        import os

        conn = get_db()

        # Estatísticas do banco
        stats = {
            'credores': {
                'total': conn.execute("SELECT COUNT(*) FROM credores").fetchone()[0],
                'ativos': conn.execute("SELECT COUNT(*) FROM credores WHERE ativo=1").fetchone()[0],
                'inativos': conn.execute("SELECT COUNT(*) FROM credores WHERE ativo=0").fetchone()[0],
            },
            'empenhos': {
                'total': conn.execute("SELECT COUNT(*) FROM empenhos").fetchone()[0],
                'empenhados': conn.execute("SELECT COUNT(*) FROM empenhos WHERE empenhado=1").fetchone()[0],
            },
            'rpas': {
                'total': conn.execute("SELECT COUNT(*) FROM rpas").fetchone()[0],
            },
            'logs': {
                'total': conn.execute("SELECT COUNT(*) FROM logs").fetchone()[0],
                'ultimas_24h': conn.execute(
                    "SELECT COUNT(*) FROM logs WHERE data >= datetime('now', '-1 day')"
                ).fetchone()[0],
            },
            'kanban': {
                'total': conn.execute("SELECT COUNT(*) FROM kanban_tasks").fetchone()[0],
                'todo': conn.execute("SELECT COUNT(*) FROM kanban_tasks WHERE status='todo'").fetchone()[0],
                'in_progress': conn.execute("SELECT COUNT(*) FROM kanban_tasks WHERE status='in_progress'").fetchone()[0],
                'done': conn.execute("SELECT COUNT(*) FROM kanban_tasks WHERE status='done'").fetchone()[0],
            }
        }

        # Tamanho do banco de dados
        from config import settings
        db_size = os.path.getsize(settings.db_path) if os.path.exists(settings.db_path) else 0

        return jsonify({
            'status': 'ok',
            'timestamp': datetime.now().isoformat(),
            'database': {
                'size_bytes': db_size,
                'size_mb': round(db_size / (1024 * 1024), 2)
            },
            'statistics': stats
        }), 200

    except Exception as e:
        return jsonify({
            'status': 'error',
            'timestamp': datetime.now().isoformat(),
            'error': str(e)
        }), 503
