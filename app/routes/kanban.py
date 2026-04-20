"""
app/routes/kanban.py — Rotas de gestão Kanban
"""

import uuid
from flask import Blueprint, request, jsonify
from app.utils.db import get_db
from app.utils.helpers import row_to_dict

bp = Blueprint('kanban', __name__)

# Limite de upload: 5MB
MAX_UPLOAD_SIZE = 5 * 1024 * 1024
ALLOWED_EXTENSIONS = {
    '.pdf', '.jpg', '.jpeg', '.png', '.gif', '.webp',
    '.doc', '.docx', '.xls', '.xlsx', '.txt', '.csv',
    '.zip', '.rar', '.mp4', '.mp3', '.wav',
}
ALLOWED_MIME_TYPES = {
    'application/pdf',
    'image/jpeg', 'image/png', 'image/gif', 'image/webp',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'text/plain', 'text/csv',
    'application/zip', 'application/x-rar-compressed',
    'video/mp4', 'audio/mpeg', 'audio/wav',
    'application/octet-stream',
}


@bp.route('/kanban', methods=['GET'])
def listar_kanban():
    """Lista todas as tarefas do kanban com anexos (JOIN único)."""
    try:
        conn = get_db()

        # Busca todas as tarefas
        rows = conn.execute("""
            SELECT * FROM kanban_tasks ORDER BY criado_em DESC
        """).fetchall()

        # Busca todos os anexos de uma vez
        task_ids = [row['id'] for row in rows]
        if task_ids:
            placeholders = ','.join('?' for _ in task_ids)
            attachments_rows = conn.execute(f"""
                SELECT * FROM kanban_attachments
                WHERE task_id IN ({placeholders})
                ORDER BY criado_em DESC
            """, task_ids).fetchall()
        else:
            attachments_rows = []

        # Agrupa anexos por task_id
        attachments_by_task = {}
        for att in attachments_rows:
            att_dict = row_to_dict(att)
            tid = att['task_id']
            if tid not in attachments_by_task:
                attachments_by_task[tid] = []
            attachments_by_task[tid].append(att_dict)

        # Monta resposta
        tasks = []
        for row in rows:
            task = row_to_dict(row)
            task['attachments'] = attachments_by_task.get(task['id'], [])
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
    """Faz upload de anexo para tarefa com validação de segurança."""
    try:
        conn = get_db()

        # Verifica se a tarefa existe
        task = conn.execute(
            "SELECT id FROM kanban_tasks WHERE id=?", (task_id,)
        ).fetchone()
        if not task:
            return jsonify({'error': 'Tarefa não encontrada'}), 404

        if 'file' not in request.files:
            return jsonify({'error': 'Nenhum arquivo enviado'}), 400

        file = request.files['file']
        if not file.filename or file.filename.strip() == '':
            return jsonify({'error': 'Nome de arquivo inválido'}), 400

        # Lê conteúdo e valida tamanho
        content = file.read()
        if len(content) > MAX_UPLOAD_SIZE:
            return jsonify({
                'error': f'Arquivo muito grande. Tamanho máximo: {MAX_UPLOAD_SIZE // (1024*1024)}MB'
            }), 413

        # Valida extensão
        ext = ''
        if '.' in file.filename:
            ext = '.' + file.filename.rsplit('.', 1)[1].lower()
        if ext and ext not in ALLOWED_EXTENSIONS:
            return jsonify({
                'error': f'Tipo de arquivo não permitido. Tipos aceitos: {", ".join(sorted(ALLOWED_EXTENSIONS))}'
            }), 400

        # Valida MIME type
        mime_type = file.content_type or 'application/octet-stream'
        if mime_type not in ALLOWED_MIME_TYPES:
            return jsonify({
                'error': 'Tipo de conteúdo não permitido'
            }), 400

        cur = conn.cursor()
        cur.execute("""
            INSERT INTO kanban_attachments (task_id, file_name, mime_type, file_size, content)
            VALUES (?, ?, ?, ?, ?)
        """, (
            task_id,
            file.filename,
            mime_type,
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
