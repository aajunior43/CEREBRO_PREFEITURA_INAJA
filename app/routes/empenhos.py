"""
app/routes/empenhos.py — Rotas de gestão de empenhos
"""

from flask import Blueprint, request, jsonify
from app.utils.db import get_db
from app.utils.helpers import row_to_dict

bp = Blueprint('empenhos', __name__)


@bp.route('/empenhos/<int:ano>/<int:mes>', methods=['GET'])
def listar_empenhos(ano, mes):
    """Lista empenhos de um mês/ano específico."""
    try:
        conn = get_db()
        rows = conn.execute("""
            SELECT e.*, c.nome as credor_nome, c.valor as credor_valor, 
                   c.departamento as credor_departamento
            FROM empenhos e
            JOIN credores c ON c.id = e.credor_id
            WHERE e.ano = ? AND e.mes = ? AND c.ativo = 1
            ORDER BY c.nome ASC
        """, (ano, mes)).fetchall()
        
        return jsonify([row_to_dict(r) for r in rows])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/empenhos', methods=['POST'])
def toggle_empenho():
    """Marca/desmarca empenho de um credor."""
    data = request.get_json(silent=True) or {}
    credor_id = data.get('credor_id')
    ano = data.get('ano')
    mes = data.get('mes')
    
    if not all([credor_id, ano, mes]):
        return jsonify({'error': 'Dados incompletos'}), 400
    
    try:
        conn = get_db()
        
        # Verificar se já existe
        existing = conn.execute("""
            SELECT * FROM empenhos WHERE credor_id=? AND ano=? AND mes=?
        """, (credor_id, ano, mes)).fetchone()
        
        if existing:
            # Toggle: remove se existe, cria se não existe
            conn.execute("DELETE FROM empenhos WHERE id=?", (existing['id'],))
            conn.commit()
            
            conn.execute("""
                INSERT INTO logs (acao, credor_id, credor_nome, detalhes)
                VALUES (?, ?, ?, ?)
            """, ('EMPENHO_REMOVE', credor_id, existing.get('credor_nome', ''), 
                  f'Removido empenho {ano}/{mes}'))
            conn.commit()
            
            return jsonify({'ok': True, 'action': 'removed'})
        else:
            # Criar novo empenho
            conn.execute("""
                INSERT INTO empenhos (credor_id, ano, mes, empenhado, timestamp)
                VALUES (?, ?, ?, 1, datetime('now', 'localtime'))
            """, (credor_id, ano, mes))
            conn.commit()
            
            # Log
            conn.execute("""
                INSERT INTO logs (acao, credor_id, credor_nome, detalhes)
                VALUES (?, ?, ?, ?)
            """, ('EMPENHO_CREATE', credor_id, '', f'Empenhado {ano}/{mes}'))
            conn.commit()
            
            return jsonify({'ok': True, 'action': 'created'})
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/empenhos/lote', methods=['POST'])
def empenho_lote():
    """Marca múltiplos empenhos de uma vez."""
    data = request.get_json(silent=True) or {}
    credores_ids = data.get('credores_ids', [])
    ano = data.get('ano')
    mes = data.get('mes')
    
    if not all([credores_ids, ano, mes]):
        return jsonify({'error': 'Dados incompletos'}), 400
    
    try:
        conn = get_db()
        count = 0
        
        for credor_id in credores_ids:
            existing = conn.execute("""
                SELECT * FROM empenhos WHERE credor_id=? AND ano=? AND mes=?
            """, (credor_id, ano, mes)).fetchone()
            
            if not existing:
                conn.execute("""
                    INSERT INTO empenhos (credor_id, ano, mes, empenhado, timestamp)
                    VALUES (?, ?, ?, 1, datetime('now', 'localtime'))
                """, (credor_id, ano, mes))
                count += 1
        
        conn.commit()
        
        # Log
        conn.execute("""
            INSERT INTO logs (acao, detalhes)
            VALUES (?, ?)
        """, ('EMPENHO_LOTE', f'{count} empenhos criados para {ano}/{mes}'))
        conn.commit()
        
        return jsonify({'ok': True, 'count': count})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
