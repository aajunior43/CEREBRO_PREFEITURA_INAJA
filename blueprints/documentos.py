import os
import re
import time as _time
import hashlib
import mimetypes

from flask import Blueprint, request, jsonify, send_file, current_app
from database import get_db, row_to_dict, DOCUMENTS_DIR

bp = Blueprint('documentos', __name__)


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


@bp.route('/documentos', methods=['GET'])
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
        current_app.logger.error('GET /api/documentos: %s', e)
        return jsonify({'error': str(e)}), 500


@bp.route('/documentos', methods=['POST'])
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
        current_app.logger.error('POST /api/documentos: %s', e)
        return jsonify({'error': str(e)}), 500


@bp.route('/documentos/conteudo', methods=['POST'])
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
        current_app.logger.error('POST /api/documentos/conteudo: %s', e)
        return jsonify({'error': str(e)}), 500


@bp.route('/documentos/<int:doc_id>/download', methods=['GET'])
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
        current_app.logger.error('GET /api/documentos/%s/download: %s', doc_id, e)
        return jsonify({'error': str(e)}), 500


@bp.route('/documentos/<int:doc_id>', methods=['DELETE'])
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
                current_app.logger.warning('Arquivo de documento não removido imediatamente %s: %s', abs_path, file_err)
                return jsonify({'ok': True, 'file_removed': False})
        return jsonify({'ok': True, 'file_removed': True})
    except Exception as e:
        current_app.logger.error('DELETE /api/documentos/%s: %s', doc_id, e)
        return jsonify({'error': str(e)}), 500
