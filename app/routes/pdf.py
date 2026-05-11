"""
app/routes/pdf.py — Rotas de manipulação de PDF
"""

import os
import io
from flask import Blueprint, request, jsonify, send_file
from PyPDF2 import PdfReader, PdfWriter

bp = Blueprint('pdf', __name__)


@bp.route('/pdf/mesclar', methods=['POST'])
def mesclar_pdf():
    """Mescla múltiplos PDFs em um."""
    try:
        if 'files' not in request.files:
            return jsonify({'error': 'Nenhum arquivo enviado'}), 400
        
        files = request.files.getlist('files')
        if len(files) < 2:
            return jsonify({'error': 'Envie pelo menos 2 arquivos'}), 400
        
        merger = PdfWriter()
        
        for file in files:
            reader = PdfReader(file.stream)
            for page in reader.pages:
                merger.add_page(page)
        
        output = io.BytesIO()
        merger.write(output)
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/pdf',
            as_attachment=True,
            download_name='mesclado.pdf'
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/pdf/dividir', methods=['POST'])
def dividir_pdf():
    """Divide PDF em páginas individuais."""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'Nenhum arquivo enviado'}), 400
        
        file = request.files['file']
        reader = PdfReader(file.stream)
        
        if len(reader.pages) <= 1:
            return jsonify({'error': 'PDF tem apenas uma página'}), 400
        
        outputs = []
        for i, page in enumerate(reader.pages):
            writer = PdfWriter()
            writer.add_page(page)
            
            output = io.BytesIO()
            writer.write(output)
            output.seek(0)
            outputs.append({
                'name': f'pagina_{i+1}.pdf',
                'content': output.getvalue()
            })
        
        return jsonify({
            'ok': True,
            'total': len(outputs),
            'message': f'PDF dividido em {len(outputs)} páginas'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/pdf/proteger', methods=['POST'])
def proteger_pdf():
    """Protege PDF com senha."""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'Nenhum arquivo enviado'}), 400
        
        data = request.form
        senha = data.get('senha', '')
        
        if not senha:
            return jsonify({'error': 'Senha é obrigatória'}), 400
        
        file = request.files['file']
        reader = PdfReader(file.stream)
        writer = PdfWriter()
        
        for page in reader.pages:
            writer.add_page(page)
        
        writer.encrypt(senha)
        
        output = io.BytesIO()
        writer.write(output)
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/pdf',
            as_attachment=True,
            download_name='protegido.pdf'
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
