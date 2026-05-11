"""
app/routes/kanban.py — Rotas de gestão Kanban
"""

import uuid
from flask import Blueprint, request, jsonify
from app.utils.db import get_db
from app.utils.helpers import row_to_dict

bp = Blueprint('kanban', __name__)


@bp.route('/kanban', methods=['GET'])
def listar_kanban():
    """Lista todas as tarefas do kanban."""
    try:
        conn = get_db()
        rows = conn.execute("""
            SELECT * FROM kanban_tasks ORDER BY criado_em DESC
        """).fetchall()
        
        tasks = []
        for row in rows:
            task = row_to_dict(row)
            
            # Buscar anexos
            attachments = conn.execute("""
                SELECT id, file_name, mime_type, file_size, criado_em
                FROM kanban_attachments WHERE task_id=?
            """, (row['id'],)).fetchall()
            task['attachments'] = [row_to_dict(a) for a in attachments]
            
            tasks.append(task)
        
        return jsonify(tasks)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/kanban', methods=['POST'])
def criar_tarefa():
    """Cria nova tarefa no kanban."""
    data = request.get_json(silent=True) or {}
    
    task_id = str(uuid.uuid4())
    
    try:
        conn = get_db()
        conn.execute("""
            INSERT INTO kanban_tasks (id, title, description, status, priority, categoria)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            task_id,
            data.get('title', ''),
            data.get('description', ''),
            data.get('status', 'todo'),
            data.get('priority', 'medium'),
            data.get('categoria', ''),
        ))
        conn.commit()
        
        row = conn.execute("SELECT * FROM kanban_tasks WHERE id=?", (task_id,)).fetchone()
        return jsonify(row_to_dict(row)), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/kanban/<task_id>', methods=['PUT'])
def atualizar_tarefa(task_id):
    """Atualiza tarefa do kanban."""
    data = request.get_json(silent=True) or {}
    
    try:
        conn = get_db()
        
        existing = conn.execute("SELECT * FROM kanban_tasks WHERE id=?", (task_id,)).fetchone()
        if not existing:
            return jsonify({'error': 'Tarefa não encontrada'}), 404
        
        fields = []
        values = []
        
        for key in ['title', 'description', 'status', 'priority', 'categoria', 
                    'data_vencimento', 'responsavel', 'concluido_em']:
            if key in data:
                fields.append(f"{key}=?")
                values.append(data.get(key))
        
        if fields:
            values.append(task_id)
            conn.execute(f"""
                UPDATE kanban_tasks 
                SET {','.join(fields)}, atualizado_em=datetime('now','localtime')
                WHERE id=?
            """, values)
            conn.commit()
        
        row = conn.execute("SELECT * FROM kanban_tasks WHERE id=?", (task_id,)).fetchone()
        return jsonify(row_to_dict(row))
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/kanban/<task_id>', methods=['DELETE'])
def excluir_tarefa(task_id):
    """Exclui tarefa do kanban."""
    try:
        conn = get_db()
        
        existing = conn.execute("SELECT * FROM kanban_tasks WHERE id=?", (task_id,)).fetchone()
        if not existing:
            return jsonify({'error': 'Tarefa não encontrada'}), 404
        
        conn.execute("DELETE FROM kanban_tasks WHERE id=?", (task_id,))
        conn.commit()
        
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/kanban/<task_id>/attachments', methods=['POST'])
def upload_anexo(task_id):
    """Faz upload de anexo para tarefa."""
    try:
        conn = get_db()
        
        if 'file' not in request.files:
            return jsonify({'error': 'Nenhum arquivo enviado'}), 400
        
        file = request.files['file']
        content = file.read()
        
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO kanban_attachments (task_id, file_name, mime_type, file_size, content)
            VALUES (?, ?, ?, ?, ?)
        """, (
            task_id,
            file.filename,
            file.content_type or 'application/octet-stream',
            len(content),
            content,
        ))
        
        attachment_id = cur.lastrowid
        conn.commit()
        
        return jsonify({'ok': True, 'attachment_id': attachment_id})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/kanban/<task_id>/attachments/<int:attachment_id>', methods=['DELETE'])
def excluir_anexo(task_id, attachment_id):
    """Exclui anexo da tarefa."""
    try:
        conn = get_db()
        
        conn.execute("""
            DELETE FROM kanban_attachments 
            WHERE id=? AND task_id=?
        """, (attachment_id, task_id))
        conn.commit()
        
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
