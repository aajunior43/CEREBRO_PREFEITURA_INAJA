"""
app/routes/config.py — Rotas de configuração
"""

from flask import Blueprint, request, jsonify, g
from app.utils.db import get_db
from app.utils.helpers import row_to_dict

bp = Blueprint('config', __name__)

ALLOWED_CONFIG_KEYS = {
    'api_openrouter_key',
    'api_openrouter_modelo',
    'api_cnpja_key',
    'api_autentique_key',
}


@bp.route('/config', methods=['GET'])
def config_listar():
    """Lista configurações do sistema."""
    try:
        conn = get_db()
        rows = conn.execute("SELECT * FROM configuracoes").fetchall()
        configs = {row['chave']: row['valor'] for row in rows}
        return jsonify(configs)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/config', methods=['POST'])
def config_salvar():
    """Salva configurações do sistema."""
    data = request.get_json(silent=True) or {}
    
    try:
        conn = get_db()
        for chave, valor in data.items():
            if chave not in ALLOWED_CONFIG_KEYS:
                continue
            
            conn.execute("""
                INSERT INTO configuracoes (chave, valor, atualizado_em)
                VALUES (?, ?, datetime('now', 'localtime'))
                ON CONFLICT(chave) DO UPDATE SET
                    valor = excluded.valor,
                    atualizado_em = datetime('now', 'localtime')
            """, (chave, valor))
        
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/admin/summary', methods=['GET'])
def admin_summary():
    """Retorna resumo administrativo para dashboard."""
    try:
        conn = get_db()
        
        # Contadores principais
        total_credores = conn.execute("SELECT COUNT(*) FROM credores WHERE ativo=1").fetchone()[0]
        total_empenhos = conn.execute("SELECT COUNT(*) FROM empenhos").fetchone()[0]
        total_rpas = conn.execute("SELECT COUNT(*) FROM rpas").fetchone()[0]
        total_tarefas = conn.execute("SELECT COUNT(*) FROM kanban_tasks WHERE status<>'done'").fetchone()[0]
        
        # Logs recentes
        logs_recentes = conn.execute("""
            SELECT * FROM logs ORDER BY id DESC LIMIT 50
        """).fetchall()
        
        return jsonify({
            'total_credores': total_credores,
            'total_empenhos': total_empenhos,
            'total_rpas': total_rpas,
            'total_tarefas': total_tarefas,
            'logs_recentes': [row_to_dict(r) for r in logs_recentes],
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
