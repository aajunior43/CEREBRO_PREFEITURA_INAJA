import io as _io
import zipfile as _zipfile

from flask import Blueprint, request, send_file
from PyPDF2 import PdfReader as _PdfReader, PdfWriter as _PdfWriter
from blueprints.documentos import _persist_document_file

bp = Blueprint('pdf_tools', __name__)


@bp.route('/pdf/mesclar', methods=['POST'])
def pdf_mesclar():
    files = request.files.getlist('pdfs')
    if len(files) < 2:
        return 'Envie ao menos 2 arquivos', 400
    writer = _PdfWriter()
    for f in files:
        reader = _PdfReader(f)
        for page in reader.pages:
            writer.add_page(page)
    buf = _io.BytesIO()
    writer.write(buf)
    buf.seek(0)
    _persist_document_file('mesclado.pdf', buf.getvalue(), 'gerados_pdf', 'mesclar', 'PDF gerado automaticamente pelo módulo de mesclagem', 'application/pdf')
    buf.seek(0)
    return send_file(buf, mimetype='application/pdf', as_attachment=True,
                     download_name='mesclado.pdf')


@bp.route('/pdf/dividir', methods=['POST'])
def pdf_dividir():
    f = request.files.get('pdf')
    ranges_str = request.form.get('ranges', '').strip()
    if not f or not ranges_str:
        return 'Parâmetros inválidos', 400
    pdf_bytes = f.read()
    reader = _PdfReader(_io.BytesIO(pdf_bytes))
    total = len(reader.pages)
    groups = []
    for part in ranges_str.split(','):
        part = part.strip()
        if not part:
            continue
        if '-' in part:
            a, b = part.split('-', 1)
            a_i = max(0, int(a.strip()) - 1)
            b_i = min(total - 1, int(b.strip()) - 1)
            pgs = list(range(a_i, b_i + 1))
            name = f"paginas_{a.strip()}-{b.strip()}.pdf"
        else:
            p = int(part.strip()) - 1
            pgs = [p] if 0 <= p < total else []
            name = f"pagina_{part.strip()}.pdf"
        if pgs:
            groups.append((name, pgs))
    if not groups:
        return 'Nenhuma página válida nos intervalos informados', 400
    if len(groups) == 1:
        writer = _PdfWriter()
        for p in groups[0][1]:
            writer.add_page(reader.pages[p])
        buf = _io.BytesIO()
        writer.write(buf)
        buf.seek(0)
        _persist_document_file(groups[0][0], buf.getvalue(), 'gerados_pdf', 'dividir', 'PDF gerado automaticamente pelo módulo de divisão', 'application/pdf')
        buf.seek(0)
        return send_file(buf, mimetype='application/pdf', as_attachment=True,
                         download_name=groups[0][0])
    zip_buf = _io.BytesIO()
    with _zipfile.ZipFile(zip_buf, 'w', _zipfile.ZIP_DEFLATED) as zf:
        for name, pgs in groups:
            writer = _PdfWriter()
            for p in pgs:
                writer.add_page(reader.pages[p])
            pdf_buf = _io.BytesIO()
            writer.write(pdf_buf)
            zf.writestr(name, pdf_buf.getvalue())
    zip_buf.seek(0)
    _persist_document_file('dividido.zip', zip_buf.getvalue(), 'gerados_pdf', 'dividir', 'ZIP gerado automaticamente pelo módulo de divisão de PDF', 'application/zip')
    zip_buf.seek(0)
    return send_file(zip_buf, mimetype='application/zip', as_attachment=True,
                     download_name='dividido.zip')


@bp.route('/pdf/proteger', methods=['POST'])
def pdf_proteger():
    f = request.files.get('pdf')
    senha = request.form.get('senha', '')
    if not f or not senha:
        return 'Parâmetros inválidos', 400
    reader = _PdfReader(f)
    writer = _PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt(senha)
    buf = _io.BytesIO()
    writer.write(buf)
    buf.seek(0)
    _persist_document_file('protegido.pdf', buf.getvalue(), 'gerados_pdf', 'proteger', 'PDF protegido gerado automaticamente', 'application/pdf')
    buf.seek(0)
    return send_file(buf, mimetype='application/pdf', as_attachment=True,
                     download_name='protegido.pdf')
