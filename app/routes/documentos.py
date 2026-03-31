"""
app/routes/documentos.py — Rotas de gestão de documentos
"""

import mimetypes
import os
from flask import Blueprint, request, jsonify, send_file
from config import settings
from app.utils.db import get_db
from app.utils.helpers import row_to_dict, persist_document_file

bp = Blueprint('documentos', __name__)

DOCUMENTS_DIR = os.path.join(str(settings.base_dir), 'documentos_centro')


@bp.route('/documentos', methods=['GET'])
def listar_documentos():
    """Lista documentos do centro de documentos."""
    try:
        conn = get_db()
        categoria = request.args.get('categoria', '')
        
        if categoria:
            rows = conn.execute("""
                SELECT * FROM documentos_centro 
                WHERE categoria=? 
                ORDER BY criado_em DESC
            """, (categoria,)).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM documentos_centro 
                ORDER BY criado_em DESC 
                LIMIT 200
            """).fetchall()
        
        return jsonify([row_to_dict(r) for r in rows])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/documentos', methods=['POST'])
def upload_documento():
    """Faz upload de documento."""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'Nenhum arquivo enviado'}), 400
        
        file = request.files['file']
        content = file.read()
        
        categoria = request.form.get('categoria', 'geral')
        referencia = request.form.get('referencia', '')
        descricao = request.form.get('descricao', '')
        
        doc = persist_document_file(
            original_name=file.filename,
            content=content,
            categoria=categoria,
            referencia=referencia,
            descricao=descricao,
            mime_type=file.content_type,
        )
        
        return jsonify(doc), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/documentos/<int:doc_id>', methods=['DELETE'])
def excluir_documento(doc_id):
    """Exclui documento."""
    try:
        conn = get_db()
        
        row = conn.execute("SELECT * FROM documentos_centro WHERE id=?", (doc_id,)).fetchone()
        if not row:
            return jsonify({'error': 'Documento não encontrado'}), 404
        
        abs_path = os.path.join(DOCUMENTS_DIR, row['caminho_relativo'].replace('/', os.sep))
        
        conn.execute("DELETE FROM documentos_centro WHERE id=?", (doc_id,))
        conn.commit()
        
        file_removed = False
        if os.path.exists(abs_path):
            try:
                os.remove(abs_path)
                file_removed = True
            except OSError:
                pass
        
        return jsonify({'ok': True, 'file_removed': file_removed})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/documentos/<int:doc_id>/download', methods=['GET'])
def download_documento(doc_id):
    """Download de documento."""
    try:
        conn = get_db()
        
        row = conn.execute("SELECT * FROM documentos_centro WHERE id=?", (doc_id,)).fetchone()
        if not row:
            return jsonify({'error': 'Documento não encontrado'}), 404
        
        abs_path = os.path.join(DOCUMENTS_DIR, row['caminho_relativo'].replace('/', os.sep))
        if not os.path.exists(abs_path):
            return jsonify({'error': 'Arquivo não encontrado'}), 404
        
        return send_file(
            abs_path,
            mimetype=mimetypes.guess_type(row['nome_original'] or row['nome_arquivo'])[0] or 'application/octet-stream',
            as_attachment=True,
            download_name=row['nome_original']
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500
