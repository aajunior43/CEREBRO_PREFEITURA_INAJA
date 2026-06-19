"""Blueprint: PDF Merge/Split/Protect"""

import io as _io
from flask import Blueprint, request, send_file
from routes._shared import require_login

bp = Blueprint("pdf", __name__)


@bp.route("/api/pdf/mesclar", methods=["POST"])
@require_login
def pdf_mesclar():
    from PyPDF2 import PdfReader as _PdfReader, PdfWriter as _PdfWriter

    files = request.files.getlist("pdfs")
    if len(files) < 2:
        return "Envie ao menos 2 arquivos", 400
    writer = _PdfWriter()
    for f in files:
        for page in _PdfReader(f).pages:
            writer.add_page(page)
    buf = _io.BytesIO()
    writer.write(buf)
    buf.seek(0)
    return send_file(
        buf,
        mimetype="application/pdf",
        as_attachment=True,
        download_name="mesclado.pdf",
    )


@bp.route("/api/pdf/dividir", methods=["POST"])
@require_login
def pdf_dividir():
    import zipfile as _zipfile
    from PyPDF2 import PdfReader as _PdfReader, PdfWriter as _PdfWriter

    f = request.files.get("pdf")
    ranges_str = request.form.get("ranges", "").strip()
    if not f or not ranges_str:
        return "Parâmetros inválidos", 400
    reader = _PdfReader(_io.BytesIO(f.read()))
    total = len(reader.pages)
    groups = []
    for part in ranges_str.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            a_i, b_i = max(0, int(a.strip()) - 1), min(total - 1, int(b.strip()) - 1)
            groups.append(
                (f"paginas_{a.strip()}-{b.strip()}.pdf", list(range(a_i, b_i + 1)))
            )
        else:
            p = int(part.strip()) - 1
            if 0 <= p < total:
                groups.append((f"pagina_{part.strip()}.pdf", [p]))
    if not groups:
        return "Nenhuma página válida", 400
    if len(groups) == 1:
        writer = _PdfWriter()
        for p in groups[0][1]:
            writer.add_page(reader.pages[p])
        buf = _io.BytesIO()
        writer.write(buf)
        buf.seek(0)
        return send_file(
            buf,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=groups[0][0],
        )
    zip_buf = _io.BytesIO()
    with _zipfile.ZipFile(zip_buf, "w", _zipfile.ZIP_DEFLATED) as zf:
        for name, pgs in groups:
            writer = _PdfWriter()
            for p in pgs:
                writer.add_page(reader.pages[p])
            pdf_buf = _io.BytesIO()
            writer.write(pdf_buf)
            zf.writestr(name, pdf_buf.getvalue())
    zip_buf.seek(0)
    return send_file(
        zip_buf,
        mimetype="application/zip",
        as_attachment=True,
        download_name="dividido.zip",
    )


@bp.route("/api/pdf/proteger", methods=["POST"])
@require_login
def pdf_proteger():
    from PyPDF2 import PdfReader as _PdfReader, PdfWriter as _PdfWriter

    f = request.files.get("pdf")
    senha = request.form.get("senha", "")
    if not f or not senha:
        return "Parâmetros inválidos", 400
    writer = _PdfWriter()
    for page in _PdfReader(f).pages:
        writer.add_page(page)
    writer.encrypt(senha)
    buf = _io.BytesIO()
    writer.write(buf)
    buf.seek(0)
    return send_file(
        buf,
        mimetype="application/pdf",
        as_attachment=True,
        download_name="protegido.pdf",
    )
