"""Blueprint: Documentos + Autentique (assinatura digital)"""

import json
import os
import re
import time as _time
import hashlib
import mimetypes

import requests
from flask import Blueprint, request, jsonify, send_file, session

from config import settings
from routes._shared import require_login
from routes.helpers import slugify

import base64

bp = Blueprint("documentos", __name__)
bp_autentique = Blueprint("autentique", __name__)

DOCUMENTS_DIR = os.path.join(settings.base_dir, "documentos_centro")


def get_db():
    from flask import g
    return g._get_db()


def extrair_texto_pdf(abs_path):
    try:
        import PyPDF2
        texto = []
        with open(abs_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            # Limit page scanning to prevent excessive cpu use
            for page in reader.pages[:100]:
                t = page.extract_text()
                if t:
                    texto.append(t)
        return "\n".join(texto)
    except Exception as e:
        print(f"Erro ao extrair texto do PDF {abs_path}: {e}")
        return ""


def indexar_documento(doc_id, abs_path):
    import threading
    import sqlite3
    db_path = str(settings.db_path)

    def _worker():
        try:
            conn = sqlite3.connect(db_path, timeout=30.0)
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT 1 FROM documentos_texto WHERE documento_id=?", (doc_id,)).fetchone()
            if row:
                conn.close()
                return
            if not os.path.exists(abs_path):
                conn.close()
                return
            _, ext = os.path.splitext(abs_path)
            texto = ""
            if ext.lower() == ".pdf":
                texto = extrair_texto_pdf(abs_path)
            elif ext.lower() in [".txt", ".json", ".csv", ".xml"]:
                try:
                    with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                        texto = f.read()
                except Exception:
                    pass
            if texto:
                conn.execute("INSERT OR REPLACE INTO documentos_texto (documento_id, texto_conteudo) VALUES (?,?)", (doc_id, texto))
                conn.commit()
            conn.close()
        except Exception as e:
            print(f"Erro ao indexar documento {doc_id} em background: {e}")

    threading.Thread(target=_worker, daemon=True).start()



def row_to_dict(row):
    return dict(row)





def build_document_storage(
    categoria: str, referencia: str, original_name: str
) -> tuple[str, str, str]:
    categoria_slug = slugify(categoria, "geral")
    referencia_slug = (
        slugify(referencia, "sem-referencia") if referencia else "sem-referencia"
    )
    ext = os.path.splitext(original_name or "")[1].lower()[:20]
    unique_name = f"{int(_time.time() * 1000)}_{hashlib.sha1((original_name + str(_time.time())).encode()).hexdigest()[:10]}{ext}"
    relative_dir = os.path.join(categoria_slug, referencia_slug)
    abs_dir = os.path.join(DOCUMENTS_DIR, relative_dir)
    os.makedirs(abs_dir, exist_ok=True)
    return (
        unique_name,
        relative_dir.replace("\\", "/"),
        os.path.join(abs_dir, unique_name),
    )


def persist_document_file(
    original_name: str,
    content: bytes,
    categoria: str = "gerados",
    referencia: str = "",
    descricao: str = "",
    mime_type: str = "",
):
    nome_arquivo, relative_dir, abs_path = build_document_storage(
        categoria, referencia, original_name
    )
    with open(abs_path, "wb") as fh:
        fh.write(content)
    tamanho = os.path.getsize(abs_path)
    extensao = os.path.splitext(original_name)[1].lower()
    caminho_relativo = (
        f"{relative_dir}/{nome_arquivo}" if relative_dir else nome_arquivo
    )
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO documentos_centro (nome_original,nome_arquivo,categoria,referencia,descricao,tamanho,extensao,caminho_relativo) VALUES (?,?,?,?,?,?,?,?)",
        (
            original_name,
            nome_arquivo,
            categoria,
            referencia,
            descricao,
            tamanho,
            extensao,
            caminho_relativo,
        ),
    )
    conn.execute(
        "INSERT INTO logs (acao, detalhes) VALUES (?, ?)",
        ("DOC_UPLOADO", f"Salvou documento: '{original_name}' (Categoria: {categoria})")
    )
    conn.commit()
    doc_id = cur.lastrowid
    try:
        indexar_documento(doc_id, abs_path)
    except Exception:
        pass
    row = conn.execute(
        "SELECT * FROM documentos_centro WHERE id=?", (doc_id,)
    ).fetchone()
    return row_to_dict(row)


# ── Documentos CRUD ──────────────────────────────────────────
@bp.route("/api/documentos", methods=["GET"])
@require_login
def documentos_listar():
    try:
        limit = max(1, min(request.args.get("limit", 100, type=int), 1000))
        offset = max(0, request.args.get("offset", 0, type=int))
        categoria = (request.args.get("categoria") or "").strip()
        referencia = (request.args.get("referencia") or "").strip()
        busca = (request.args.get("busca") or "").strip()
        
        conn = get_db()
        
        # On-the-fly indexing check (index up to 15 unindexed PDFs/files per request)
        try:
            unindexed = conn.execute(
                "SELECT id, caminho_relativo FROM documentos_centro WHERE id NOT IN (SELECT documento_id FROM documentos_texto) AND extensao IN ('.pdf', '.txt', '.json', '.xml', '.csv') LIMIT 15"
            ).fetchall()
            for u in unindexed:
                u_path = os.path.join(DOCUMENTS_DIR, u["caminho_relativo"].replace("/", os.sep))
                indexar_documento(u["id"], u_path)
        except Exception:
            pass

        sql = "SELECT * FROM documentos_centro WHERE 1=1"
        count_sql = "SELECT COUNT(*) AS total FROM documentos_centro WHERE 1=1"
        params, count_params = [], []
        if categoria:
            sql += " AND categoria=?"
            count_sql += " AND categoria=?"
            params.append(categoria)
            count_params.append(categoria)
        if referencia:
            sql += " AND referencia LIKE ?"
            count_sql += " AND referencia LIKE ?"
            like = f"%{referencia}%"
            params.append(like)
            count_params.append(like)
            
        if busca:
            like_busca = f"%{busca}%"
            clause = """ AND (nome_original LIKE ? OR descricao LIKE ? OR referencia LIKE ? OR id IN (
                SELECT documento_id FROM documentos_texto WHERE texto_conteudo LIKE ?
            ))"""
            sql += clause
            count_sql += clause
            params.extend([like_busca, like_busca, like_busca, like_busca])
            count_params.extend([like_busca, like_busca, like_busca, like_busca])
            
        total = conn.execute(count_sql, count_params).fetchone()["total"]
        sql += " ORDER BY criado_em DESC, id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = conn.execute(sql, params).fetchall()
        return jsonify(
            {
                "items": [row_to_dict(r) for r in rows],
                "total": total,
                "limit": limit,
                "offset": offset,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/documentos", methods=["POST"])
@require_login
def documentos_enviar():
    file = request.files.get("arquivo")
    categoria = (request.form.get("categoria") or "geral").strip()
    referencia = (request.form.get("referencia") or "").strip()
    descricao = (request.form.get("descricao") or "").strip()
    if not file or not file.filename:
        return jsonify({"error": "Arquivo é obrigatório"}), 400
    
    # Apenas o usuário 'aleksandro' pode adicionar arquivos à biblioteca
    if categoria.startswith("biblioteca-"):
        if session.get("usuario_login") != "aleksandro":
            return jsonify({"error": "Apenas o usuário 'aleksandro' pode adicionar arquivos à biblioteca."}), 403

    try:
        nome_arquivo, relative_dir, abs_path = build_document_storage(
            categoria, referencia, file.filename
        )
        file.save(abs_path)
        tamanho = os.path.getsize(abs_path)
        extensao = os.path.splitext(file.filename)[1].lower()
        caminho_relativo = (
            f"{relative_dir}/{nome_arquivo}" if relative_dir else nome_arquivo
        )
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO documentos_centro (nome_original,nome_arquivo,categoria,referencia,descricao,tamanho,extensao,caminho_relativo) VALUES (?,?,?,?,?,?,?,?)",
            (
                file.filename,
                nome_arquivo,
                categoria,
                referencia,
                descricao,
                tamanho,
                extensao,
                caminho_relativo,
            ),
        )
        conn.execute(
            "INSERT INTO logs (acao, detalhes) VALUES (?, ?)",
            ("DOC_UPLOADO", f"Enviou o arquivo: '{file.filename}' (Categoria: {categoria})")
        )
        conn.commit()
        doc_id = cur.lastrowid
        try:
            indexar_documento(doc_id, abs_path)
        except Exception:
            pass
        row = conn.execute(
            "SELECT * FROM documentos_centro WHERE id=?", (doc_id,)
        ).fetchone()
        return jsonify(row_to_dict(row)), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/documentos/conteudo", methods=["POST"])
@require_login
def documentos_salvar_conteudo():
    try:
        nome = (request.form.get("nome") or "").strip()
        categoria = (request.form.get("categoria") or "gerados").strip()
        referencia = (request.form.get("referencia") or "").strip()
        descricao = (request.form.get("descricao") or "").strip()
        arquivo = request.files.get("arquivo")
        if not nome or not arquivo:
            return jsonify({"error": "nome e arquivo são obrigatórios"}), 400
        
        # Apenas o usuário 'aleksandro' pode adicionar arquivos à biblioteca
        if categoria.startswith("biblioteca-"):
            if session.get("usuario_login") != "aleksandro":
                return jsonify({"error": "Apenas o usuário 'aleksandro' pode adicionar arquivos à biblioteca."}), 403

        saved = persist_document_file(
            nome,
            arquivo.read(),
            categoria,
            referencia,
            descricao,
            arquivo.mimetype or "",
        )
        return jsonify(saved), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/documentos/<int:doc_id>/download", methods=["GET"])
@require_login
def documentos_download(doc_id):
    try:
        conn = get_db()
        row = conn.execute(
            "SELECT * FROM documentos_centro WHERE id=?", (doc_id,)
        ).fetchone()
        if not row:
            return jsonify({"error": "Documento não encontrado"}), 404
        abs_path = os.path.join(
            DOCUMENTS_DIR, row["caminho_relativo"].replace("/", os.sep)
        )
        if not os.path.exists(abs_path):
            return jsonify({"error": "Arquivo físico não encontrado"}), 404
        mime, _ = mimetypes.guess_type(abs_path)
        return send_file(
            abs_path,
            mimetype=mime or "application/octet-stream",
            as_attachment=True,
            download_name=row["nome_original"],
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/documentos/<int:doc_id>/view", methods=["GET"])
@require_login
def documentos_view(doc_id):
    try:
        conn = get_db()
        row = conn.execute(
            "SELECT * FROM documentos_centro WHERE id=?", (doc_id,)
        ).fetchone()
        if not row:
            return jsonify({"error": "Documento não encontrado"}), 404
        abs_path = os.path.join(
            DOCUMENTS_DIR, row["caminho_relativo"].replace("/", os.sep)
        )
        if not os.path.exists(abs_path):
            return jsonify({"error": "Arquivo físico não encontrado"}), 404
        mime, _ = mimetypes.guess_type(abs_path)
        return send_file(abs_path, mimetype=mime or "application/pdf", as_attachment=False)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/documentos/<int:doc_id>", methods=["DELETE"])
@require_login
def documentos_excluir(doc_id):
    try:
        conn = get_db()
        row = conn.execute(
            "SELECT * FROM documentos_centro WHERE id=?", (doc_id,)
        ).fetchone()
        if not row:
            return jsonify({"error": "Documento não encontrado"}), 404
        
        # Apenas o usuário 'aleksandro' pode excluir arquivos da biblioteca
        categoria = row["categoria"] or ""
        if categoria.startswith("biblioteca-"):
            if session.get("usuario_login") != "aleksandro":
                return jsonify({"error": "Apenas o usuário 'aleksandro' pode excluir arquivos da biblioteca."}), 403

        abs_path = os.path.join(
            DOCUMENTS_DIR, row["caminho_relativo"].replace("/", os.sep)
        )
        conn.execute("DELETE FROM documentos_centro WHERE id=?", (doc_id,))
        conn.execute(
            "INSERT INTO logs (acao, detalhes) VALUES (?, ?)",
            ("DOC_EXCLUIR", f"Excluiu o documento: '{row['nome_original']}'")
        )
        conn.commit()
        file_removed = True
        if os.path.exists(abs_path):
            try:
                os.remove(abs_path)
            except OSError:
                file_removed = False
        return jsonify({"ok": True, "file_removed": file_removed})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Autentique ───────────────────────────────────────────────
def _parse_autentique_keys(value: str) -> list[str]:
    text = (value or "").replace("\r", "\n")
    raw_items = []
    for chunk in text.split("\n"):
        raw_items.extend(part.strip() for part in chunk.split(","))
    keys = [item for item in raw_items if item]
    seen = set()
    unique = []
    for item in keys:
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique


def _get_autentique_config(conn, api_key_override: str = ""):
    rows = conn.execute(
        "SELECT chave,valor FROM configuracoes WHERE chave IN (?,?)",
        ("api_autentique_key", "api_autentique_key_cursor"),
    ).fetchall()
    cfg = {row["chave"]: (row["valor"] or "").strip() for row in rows}
    override_keys = _parse_autentique_keys(api_key_override)
    if override_keys:
        return override_keys[0]
    configured_keys = _parse_autentique_keys(cfg.get("api_autentique_key", ""))
    env_keys = _parse_autentique_keys(os.environ.get("AUTENTIQUE_API_KEY") or "")
    keys = configured_keys or env_keys
    if not keys:
        return ""
    if len(keys) == 1:
        return keys[0]
    try:
        cursor = int(cfg.get("api_autentique_key_cursor", "0") or "0")
    except ValueError:
        cursor = 0
    index = cursor % len(keys)
    selected = keys[index]
    try:
        conn.execute(
            "INSERT INTO configuracoes (chave,valor,atualizado_em) VALUES (?,?,datetime('now','localtime')) "
            "ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor,atualizado_em=excluded.atualizado_em",
            ("api_autentique_key_cursor", str((index + 1) % len(keys))),
        )
        conn.commit()
    except Exception:
        pass
    return selected


def _normalize_phone_br(value: str) -> str:
    digits = re.sub(r"\D+", "", value or "")
    if digits.startswith("55") and len(digits) >= 12:
        return "+" + digits
    if len(digits) in {10, 11}:
        return "+55" + digits
    return ("+" + digits) if digits else ""


def _autentique_guess_status(*values) -> str:
    text = " ".join(str(v or "").strip().lower() for v in values if v)
    if any(
        t in text
        for t in (
            "signed",
            "assinado",
            "completed",
            "complete",
            "finalizado",
            "finished",
            "concluido",
        )
    ):
        return "assinado"
    if any(t in text for t in ("rejected", "recusado", "declined")):
        return "recusado"
    if any(t in text for t in ("canceled", "cancelado", "cancelled")):
        return "cancelado"
    if any(t in text for t in ("expired", "expirado")):
        return "expirado"
    return "pendente"


def _autentique_scan_payload(node, trail=""):
    found = []
    if isinstance(node, dict):
        for key, value in node.items():
            path = f"{trail}.{key}" if trail else str(key)
            found.extend(_autentique_scan_payload(value, path))
            if isinstance(value, (str, int, float, bool)) or value is None:
                found.append((path.lower(), value))
    elif isinstance(node, list):
        for idx, value in enumerate(node):
            path = f"{trail}[{idx}]" if trail else f"[{idx}]"
            found.extend(_autentique_scan_payload(value, path))
    return found


def _autentique_extract_webhook(payload: dict) -> dict:
    entries = _autentique_scan_payload(payload)
    event_name = document_id = signature_public_id = signature_link = download_url = (
        signed_at
    ) = delivery_method = ""
    status_values = []
    for path, value in entries:
        text = "" if value is None else str(value).strip()
        if not text:
            continue
        lower = text.lower()
        if (
            not event_name
            and path.endswith(("event", "type", "action", "name"))
            and any(t in lower for t in ("sign", "document", "signature", "webhook"))
        ):
            event_name = text
        if not document_id and any(
            t in path
            for t in (
                "document.id",
                "document_id",
                "createDocument.id",
                "document.public_id",
            )
        ):
            document_id = text
        if not signature_public_id and ("public_id" in path or "signature_id" in path):
            signature_public_id = text
        if not signature_link and "link.short_link" in path:
            signature_link = text
        if not signed_at and any(
            t in path for t in ("signed_at", "completed_at", "finished_at")
        ):
            signed_at = text
        if not delivery_method and "delivery_method" in path:
            delivery_method = text
        if ("status" in path) or path.endswith(("event", "type", "action")):
            status_values.append(text)
        if text.startswith("http"):
            key_hint = path.split(".")[-1]
            if not download_url and any(
                t in key_hint
                for t in ("download", "signed", "file_url", "original_file", "arquivo")
            ):
                download_url = text
    return {
        "event_name": event_name,
        "document_id": document_id,
        "signature_public_id": signature_public_id,
        "signature_link": signature_link,
        "download_url": download_url,
        "signed_at": signed_at,
        "delivery_method": delivery_method or "DELIVERY_METHOD_WHATSAPP",
        "status": _autentique_guess_status(event_name, signed_at, *status_values),
    }


def _autentique_save_signed_document(
    download_url: str, original_name: str, api_key: str
):
    if not download_url:
        return None
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    resp = requests.get(download_url, headers=headers, timeout=90)
    if resp.status_code >= 400:
        resp = requests.get(download_url, timeout=90)
    resp.raise_for_status()
    signed_name_root, _ = os.path.splitext(original_name or "documento")
    return persist_document_file(
        f"{signed_name_root}-assinado.pdf",
        resp.content,
        "assinados_autentique",
        "assinatura-digital",
        "Documento assinado pela Autentique",
        resp.headers.get("Content-Type") or "application/pdf",
    )


@bp_autentique.route("/api/autentique/testar", methods=["POST"])
@require_login
def autentique_testar():
    data = request.get_json(silent=True) or {}
    try:
        conn = get_db()
        api_key = _get_autentique_config(
            conn, api_key_override=(data.get("api_key") or "").strip()
        )
        if not api_key:
            return jsonify({"error": "Chave da Autentique não configurada."}), 400
        resp = requests.post(
            "https://api.autentique.com.br/v2/graphql",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={"query": "query { me { id name email } }"},
            timeout=35,
        )
        payload = resp.json()
        if resp.status_code >= 400 or payload.get("errors"):
            message = (payload.get("errors") or [{}])[0].get(
                "message"
            ) or f"Erro HTTP {resp.status_code}"
            return jsonify({"error": message}), resp.status_code or 502
        user = (payload.get("data") or {}).get("me") or {}
        return jsonify({"ok": True, "usuario": user})
    except requests.RequestException as err:
        return jsonify({"error": f"Falha de conexão: {err}"}), 502
    except Exception as err:
        return jsonify({"error": str(err)}), 500


@bp_autentique.route("/api/autentique/saldo", methods=["GET"])
@require_login
def autentique_saldo():
    try:
        conn = get_db()
        api_key = _get_autentique_config(
            conn, api_key_override=(request.args.get("api_key") or "").strip()
        )
        if not api_key:
            return jsonify({"error": "Chave da Autentique não configurada."}), 400
        resp = requests.post(
            "https://api.autentique.com.br/v2/graphql",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "query": "query { me { id name email subscription { documents credits } } }"
            },
            timeout=35,
        )
        payload = resp.json()
        if resp.status_code >= 400 or payload.get("errors"):
            message = (payload.get("errors") or [{}])[0].get(
                "message"
            ) or f"Erro HTTP {resp.status_code}"
            return jsonify({"error": message}), resp.status_code or 502
        me = (payload.get("data") or {}).get("me") or {}
        sub = me.get("subscription") or {}
        return jsonify(
            {
                "ok": True,
                "usuario": {
                    "id": me.get("id"),
                    "name": me.get("name"),
                    "email": me.get("email"),
                },
                "subscription": {
                    "documents": sub.get("documents"),
                    "credits": sub.get("credits"),
                },
            }
        )
    except requests.RequestException as err:
        return jsonify({"error": f"Falha de conexão: {err}"}), 502
    except Exception as err:
        return jsonify({"error": str(err)}), 500


@bp_autentique.route("/api/autentique/chaves", methods=["GET"])
@require_login
def autentique_listar_chaves():
    try:
        conn = get_db()
        rows = conn.execute(
            "SELECT valor FROM configuracoes WHERE chave=?", ("api_autentique_key",)
        ).fetchall()
        raw = rows[0]["valor"] if rows else ""
        keys = _parse_autentique_keys(raw)
        items = []
        for idx, key in enumerate(keys):
            masked = f"{key[:8]}...{key[-6:]}" if len(key) > 18 else key
            items.append(
                {
                    "id": idx + 1,
                    "label": f"Chave {idx + 1}",
                    "masked": masked,
                    "value": key,
                }
            )
        return jsonify(items)
    except Exception as err:
        return jsonify({"error": str(err)}), 500


@bp_autentique.route("/api/autentique/enviar-whatsapp", methods=["POST"])
@require_login
def autentique_enviar_whatsapp():
    data = request.get_json(silent=True) or {}
    doc_id = data.get("documento_id")
    signer_name = (data.get("signer_name") or "").strip()
    signer_phone_raw = (data.get("signer_phone") or "").strip()
    if not doc_id:
        return jsonify({"error": "documento_id é obrigatório"}), 400
    if not signer_name:
        return jsonify({"error": "Nome do signatário é obrigatório"}), 400
    if not signer_phone_raw:
        return jsonify({"error": "Telefone/WhatsApp é obrigatório"}), 400
    signer_phone = _normalize_phone_br(signer_phone_raw)
    if len(signer_phone) < 12:
        return jsonify({"error": "Telefone inválido"}), 400
    try:
        conn = get_db()
        api_key = _get_autentique_config(
            conn, api_key_override=(data.get("api_key") or "").strip()
        )
        if not api_key:
            return jsonify({"error": "Chave da Autentique não configurada."}), 400
        row = conn.execute(
            "SELECT * FROM documentos_centro WHERE id=?", (doc_id,)
        ).fetchone()
        if not row:
            return jsonify({"error": "Documento não encontrado"}), 404
        abs_path = os.path.join(
            DOCUMENTS_DIR, row["caminho_relativo"].replace("/", os.sep)
        )
        if not os.path.exists(abs_path):
            return jsonify({"error": "Arquivo físico não encontrado"}), 404
        mutation = """mutation CreateDocument($document: DocumentInput!, $signers: [SignerInput!]!, $file: Upload!) {
  createDocument(document: $document, signers: $signers, file: $file) { id name signatures { public_id name email created_at action { name } link { short_link } } } }"""
        operations = {
            "query": mutation,
            "variables": {
                "document": {"name": row["nome_original"] or f"documento-{doc_id}.pdf"},
                "signers": [
                    {
                        "name": signer_name,
                        "phone": signer_phone,
                        "delivery_method": "DELIVERY_METHOD_WHATSAPP",
                        "action": "SIGN",
                    }
                ],
                "file": None,
            },
        }
        mime, _ = mimetypes.guess_type(abs_path)
        with open(abs_path, "rb") as fh:
            resp = requests.post(
                "https://api.autentique.com.br/v2/graphql",
                headers={"Authorization": f"Bearer {api_key}"},
                data={
                    "operations": json.dumps(operations, ensure_ascii=False),
                    "map": json.dumps({"0": ["variables.file"]}),
                },
                files={
                    "0": (
                        row["nome_original"] or os.path.basename(abs_path),
                        fh,
                        mime or "application/pdf",
                    )
                },
                timeout=60,
            )
        payload = resp.json()
        if resp.status_code >= 400 or payload.get("errors"):
            message = (payload.get("errors") or [{}])[0].get(
                "message"
            ) or f"Erro HTTP {resp.status_code}"
            return jsonify(
                {"error": f"Falha ao criar documento: {message}"}
            ), resp.status_code or 502
        doc_data = (payload.get("data") or {}).get("createDocument") or {}
        signatures = doc_data.get("signatures") or []
        first_sig = signatures[0] if signatures else {}
        sig_link = (first_sig.get("link") or {}).get("short_link") or ""
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO autentique_envios (documento_centro_id,autentique_document_id,autentique_signature_public_id,documento_nome,signatario_nome,signatario_phone,status,delivery_method,assinatura_link,criado_em,atualizado_em) VALUES (?,?,?,?,?,?,?,?,?,datetime('now','localtime'),datetime('now','localtime'))",
            (
                doc_id,
                doc_data.get("id") or "",
                first_sig.get("public_id") or "",
                doc_data.get("name") or row["nome_original"],
                signer_name,
                signer_phone,
                _autentique_guess_status(
                    first_sig.get("status"), first_sig.get("created_at")
                ),
                first_sig.get("delivery_method") or "DELIVERY_METHOD_WHATSAPP",
                sig_link,
            ),
        )
        envio_id = cur.lastrowid
        conn.commit()
        return jsonify(
            {
                "ok": True,
                "envio_id": envio_id,
                "documento": {
                    "id": doc_data.get("id"),
                    "name": doc_data.get("name") or row["nome_original"],
                },
                "assinatura": {
                    "public_id": first_sig.get("public_id"),
                    "name": first_sig.get("name") or signer_name,
                    "email": first_sig.get("email") or "",
                    "phone": first_sig.get("phone") or signer_phone,
                    "delivery_method": first_sig.get("delivery_method")
                    or "DELIVERY_METHOD_WHATSAPP",
                    "link": sig_link,
                },
                "whatsapp_enviado": True,
                "phone_normalized": signer_phone,
            }
        )
    except requests.RequestException as err:
        return jsonify({"error": f"Falha de conexão: {err}"}), 502
    except Exception as err:
        return jsonify({"error": str(err)}), 500


@bp_autentique.route("/api/autentique/envios", methods=["GET"])
@require_login
def autentique_listar_envios():
    try:
        conn = get_db()
        rows = conn.execute("""
            SELECT e.*, d.nome_original AS documento_origem_nome, d.categoria AS documento_origem_categoria,
                   s.nome_original AS documento_assinado_nome
            FROM autentique_envios e
            LEFT JOIN documentos_centro d ON d.id = e.documento_centro_id
            LEFT JOIN documentos_centro s ON s.id = e.assinado_doc_id
            ORDER BY e.id DESC LIMIT 200""").fetchall()
        return jsonify([row_to_dict(r) for r in rows])
    except Exception as err:
        return jsonify({"error": str(err)}), 500


@bp_autentique.route("/api/autentique/envios/<int:envio_id>", methods=["DELETE"])
@require_login
def autentique_excluir_envio(envio_id):
    try:
        conn = get_db()
        if not conn.execute(
            "SELECT * FROM autentique_envios WHERE id=?", (envio_id,)
        ).fetchone():
            return jsonify({"error": "Envio não encontrado"}), 404
        conn.execute("DELETE FROM autentique_envios WHERE id=?", (envio_id,))
        conn.commit()
        return jsonify({"ok": True})
    except Exception as err:
        return jsonify({"error": str(err)}), 500


@bp_autentique.route("/api/autentique/contatos", methods=["GET"])
@require_login
def autentique_listar_contatos():
    try:
        conn = get_db()
        rows = conn.execute(
            "SELECT * FROM autentique_contatos ORDER BY nome COLLATE NOCASE ASC, id DESC"
        ).fetchall()
        return jsonify([row_to_dict(r) for r in rows])
    except Exception as err:
        return jsonify({"error": str(err)}), 500


@bp_autentique.route("/api/autentique/contatos", methods=["POST"])
@require_login
def autentique_salvar_contato():
    data = request.get_json(silent=True) or {}
    nome = (data.get("nome") or "").strip()
    phone = _normalize_phone_br((data.get("phone") or "").strip())
    if not nome:
        return jsonify({"error": "Nome é obrigatório"}), 400
    if len(re.sub(r"\D+", "", phone)) < 12:
        return jsonify({"error": "WhatsApp inválido"}), 400
    try:
        conn = get_db()
        existing = conn.execute(
            "SELECT * FROM autentique_contatos WHERE phone=?", (phone,)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE autentique_contatos SET nome=?,atualizado_em=datetime('now','localtime') WHERE id=?",
                (nome, existing["id"]),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM autentique_contatos WHERE id=?", (existing["id"],)
            ).fetchone()
            return jsonify(row_to_dict(row))
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO autentique_contatos (nome,phone,criado_em,atualizado_em) VALUES (?, ?, datetime('now','localtime'), datetime('now','localtime'))",
            (nome, phone),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM autentique_contatos WHERE id=?", (cur.lastrowid,)
        ).fetchone()
        return jsonify(row_to_dict(row)), 201
    except Exception as err:
        return jsonify({"error": str(err)}), 500


@bp_autentique.route("/api/autentique/contatos/<int:contato_id>", methods=["DELETE"])
@require_login
def autentique_excluir_contato(contato_id):
    try:
        conn = get_db()
        if not conn.execute(
            "SELECT * FROM autentique_contatos WHERE id=?", (contato_id,)
        ).fetchone():
            return jsonify({"error": "Contato não encontrado"}), 404
        conn.execute("DELETE FROM autentique_contatos WHERE id=?", (contato_id,))
        conn.commit()
        return jsonify({"ok": True})
    except Exception as err:
        return jsonify({"error": str(err)}), 500


@bp_autentique.route(
    "/api/autentique/envios/<int:envio_id>/download-assinado", methods=["GET"]
)
@require_login
def autentique_download_assinado(envio_id):
    try:
        conn = get_db()
        row = conn.execute(
            "SELECT e.assinado_doc_id, d.nome_original, d.caminho_relativo FROM autentique_envios e LEFT JOIN documentos_centro d ON d.id = e.assinado_doc_id WHERE e.id=?",
            (envio_id,),
        ).fetchone()
        if not row:
            return jsonify({"error": "Envio não encontrado"}), 404
        if not row["assinado_doc_id"] or not row["caminho_relativo"]:
            return jsonify({"error": "Documento assinado não disponível"}), 404
        abs_path = os.path.join(
            DOCUMENTS_DIR, row["caminho_relativo"].replace("/", os.sep)
        )
        if not os.path.exists(abs_path):
            return jsonify({"error": "Arquivo assinado não encontrado"}), 404
        mime, _ = mimetypes.guess_type(abs_path)
        return send_file(
            abs_path,
            mimetype=mime or "application/pdf",
            as_attachment=True,
            download_name=row["nome_original"],
        )
    except Exception as err:
        return jsonify({"error": str(err)}), 500


@bp_autentique.route("/api/autentique/envios/<int:envio_id>/view-assinado", methods=["GET"])
@require_login
def autentique_view_assinado(envio_id):
    try:
        conn = get_db()
        row = conn.execute(
            "SELECT e.assinado_doc_id, d.nome_original, d.caminho_relativo "
            "FROM autentique_envios e LEFT JOIN documentos_centro d ON d.id = e.assinado_doc_id "
            "WHERE e.id=?", (envio_id,)
        ).fetchone()
        if not row:
            return jsonify({"error": "Envio não encontrado"}), 404
        if not row["assinado_doc_id"] or not row["caminho_relativo"]:
            return jsonify({"error": "Documento assinado não disponível"}), 404
        abs_path = os.path.join(DOCUMENTS_DIR, row["caminho_relativo"].replace("/", os.sep))
        if not os.path.exists(abs_path):
            return jsonify({"error": "Arquivo assinado não encontrado"}), 404
        mime, _ = mimetypes.guess_type(abs_path)
        return send_file(abs_path, mimetype=mime or "application/pdf", as_attachment=False)
    except Exception as err:
        return jsonify({"error": str(err)}), 500


@bp_autentique.route("/api/autentique/envios/<int:envio_id>/sincronizar", methods=["POST"])
@require_login
def autentique_sincronizar_envio(envio_id):
    try:
        conn = get_db()
        data = request.get_json(silent=True) or {}
        api_key = _get_autentique_config(
            conn, api_key_override=(data.get("api_key") or "").strip()
        )
        if not api_key:
            return jsonify({"error": "Chave da Autentique não configurada."}), 400
        row = conn.execute(
            "SELECT * FROM autentique_envios WHERE id=?", (envio_id,)
        ).fetchone()
        if not row:
            return jsonify({"error": "Envio não encontrado"}), 404
        autentique_doc_id = (row["autentique_document_id"] or "").strip()
        if not autentique_doc_id:
            return jsonify({"error": "ID do documento na Autentique não disponível"}), 400
        query = """
        query GetDocument($id: UUID!) {
          document(id: $id) {
            id name
            files { signed original }
            signatures { public_id name signed { created_at } action { name } }
          }
        }"""
        resp = requests.post(
            "https://api.autentique.com.br/v2/graphql",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={"query": query, "variables": {"id": autentique_doc_id}},
            timeout=35,
        )
        payload = resp.json()
        if resp.status_code >= 400 or payload.get("errors"):
            message = (payload.get("errors") or [{}])[0].get(
                "message"
            ) or f"Erro HTTP {resp.status_code}"
            return jsonify({"error": message}), 400
        doc_data = (payload.get("data") or {}).get("document") or {}
        signed_url = (doc_data.get("files") or {}).get("signed") or ""
        signatures = doc_data.get("signatures") or []
        sigs_info = [
            {
                "nome": sig.get("name") or "",
                "assinado": sig.get("signed") is not None,
                "assinado_em": (sig.get("signed") or {}).get("created_at") or "",
            }
            for sig in signatures
        ]
        sigs_total = len(sigs_info)
        sigs_signed = sum(1 for s in sigs_info if s["assinado"])
        is_signed = sigs_signed > 0 and signed_url
        if not is_signed:
            return jsonify({
                "ok": True, "status": "pendente",
                "sigs_total": sigs_total, "sigs_signed": sigs_signed,
                "signatures": sigs_info,
                "message": f"Documento ainda não foi assinado. ({sigs_signed}/{sigs_total})",
            })
        if row["assinado_doc_id"]:
            return jsonify({
                "ok": True, "status": "assinado",
                "assinado_doc_id": row["assinado_doc_id"],
                "sigs_total": sigs_total, "sigs_signed": sigs_signed,
                "signatures": sigs_info, "message": "Já sincronizado.",
            })
        original_name = row["documento_nome"] or "documento"
        saved_doc = _autentique_save_signed_document(signed_url, original_name, api_key)
        signed_doc_id = saved_doc["id"] if saved_doc else None
        conn.execute(
            "UPDATE autentique_envios SET status='assinado', assinado_doc_id=?, "
            "assinado_em=COALESCE(NULLIF(assinado_em,''), datetime('now','localtime')), "
            "atualizado_em=datetime('now','localtime') WHERE id=?",
            (signed_doc_id, envio_id),
        )
        conn.commit()
        return jsonify({
            "ok": True, "status": "assinado",
            "assinado_doc_id": signed_doc_id,
            "sigs_total": sigs_total, "sigs_signed": sigs_signed,
            "signatures": sigs_info,
        })
    except requests.RequestException as err:
        return jsonify({"error": f"Falha de conexão: {err}"}), 502
    except Exception as err:
        return jsonify({"error": str(err)}), 500


@bp_autentique.route("/api/autentique/webhook", methods=["POST"])
def autentique_webhook():
    payload = request.get_json(silent=True) or {}
    extracted = _autentique_extract_webhook(payload)
    if not extracted["document_id"] and not extracted["signature_public_id"]:
        return jsonify({"error": "Payload sem identificador"}), 400
    try:
        conn = get_db()
        params, where = [], []
        if extracted["signature_public_id"]:
            where.append("autentique_signature_public_id=?")
            params.append(extracted["signature_public_id"])
        if extracted["document_id"]:
            where.append("autentique_document_id=?")
            params.append(extracted["document_id"])
        row = conn.execute(
            f"SELECT * FROM autentique_envios WHERE {' OR '.join(where)} ORDER BY id DESC LIMIT 1",
            tuple(params),
        ).fetchone()
        if not row:
            return jsonify(
                {
                    "ok": True,
                    "matched": False,
                    "message": "Webhook recebido, mas nenhum envio local correspondeu.",
                }
            )
        current_status = (
            extracted["status"]
            if extracted["status"] != "pendente"
            else (row["status"] or "pendente")
        )
        signed_doc_id = row["assinado_doc_id"]
        saved_doc = None
        api_key = _get_autentique_config(conn)
        if (
            current_status == "assinado"
            and not signed_doc_id
            and extracted["download_url"]
        ):
            try:
                saved_doc = _autentique_save_signed_document(
                    extracted["download_url"],
                    row["documento_nome"] or "documento",
                    api_key,
                )
                signed_doc_id = saved_doc["id"]
            except Exception as download_err:
                pass
        conn.execute(
            "UPDATE autentique_envios SET status=?,delivery_method=?,assinatura_link=COALESCE(NULLIF(?,''),assinatura_link),webhook_evento=?,webhook_payload=?,assinado_doc_id=?,assinado_em=CASE WHEN ?<>'' THEN ? WHEN ?='assinado' AND COALESCE(assinado_em,'')='' THEN datetime('now','localtime') ELSE assinado_em END,atualizado_em=datetime('now','localtime') WHERE id=?",
            (
                current_status,
                extracted["delivery_method"]
                or row["delivery_method"]
                or "DELIVERY_METHOD_WHATSAPP",
                extracted["signature_link"] or "",
                extracted["event_name"] or "",
                json.dumps(payload, ensure_ascii=False),
                signed_doc_id,
                extracted["signed_at"] or "",
                extracted["signed_at"] or "",
                current_status,
                row["id"],
            ),
        )
        conn.commit()
        return jsonify(
            {
                "ok": True,
                "matched": True,
                "envio_id": row["id"],
                "status": current_status,
                "assinado_doc_id": signed_doc_id,
                "download_salvo": bool(saved_doc),
            }
        )
    except Exception as err:
        return jsonify({"error": str(err)}), 500


@bp.route("/api/documentos/<int:doc_id>", methods=["PUT"])
@require_login
def documentos_atualizar(doc_id):
    try:
        conn = get_db()
        row = conn.execute(
            "SELECT * FROM documentos_centro WHERE id=?", (doc_id,)
        ).fetchone()
        if not row:
            return jsonify({"error": "Documento não encontrado"}), 404
        
        # Apenas o usuário 'aleksandro' pode alterar arquivos da biblioteca
        categoria = row["categoria"] or ""
        if categoria.startswith("biblioteca-"):
            if session.get("usuario_login") != "aleksandro":
                return jsonify({"error": "Apenas o usuário 'aleksandro' pode alterar arquivos da biblioteca."}), 403

        data = request.get_json(force=True) or {}
        novo_nome = (data.get("nome_original") or "").strip()
        nova_descricao = data.get("descricao")
        
        if not novo_nome:
            return jsonify({"error": "Nome do arquivo é obrigatório"}), 400
            
        # Limpar caracteres inválidos
        novo_nome = os.path.basename(novo_nome)
        
        # Manter extensão original caso tenha sido omitida
        _, ext_orig = os.path.splitext(row["nome_original"])
        nome_base, ext_nova = os.path.splitext(novo_nome)
        if not ext_nova:
            novo_nome = nome_base + ext_orig
            
        conn.execute(
            "UPDATE documentos_centro SET nome_original=?, descricao=? WHERE id=?",
            (novo_nome, nova_descricao if nova_descricao is not None else row["descricao"], doc_id)
        )
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/documentos/<int:doc_id>/sugerir-nome", methods=["GET"])
@require_login
def documentos_sugerir_nome(doc_id):
    try:
        conn = get_db()
        row = conn.execute(
            "SELECT * FROM documentos_centro WHERE id=?", (doc_id,)
        ).fetchone()
        if not row:
            return jsonify({"error": "Documento não encontrado"}), 404

        abs_path = os.path.join(
            DOCUMENTS_DIR, row["caminho_relativo"].replace("/", os.sep)
        )
        
        texto_conteudo = ""
        if os.path.exists(abs_path):
            from renomer.file_processor import extrair_texto
            from pathlib import Path
            texto_conteudo = extrair_texto(Path(abs_path)) or ""
            
        from routes._shared import _get_openrouter_config, _build_ai_service
        api_key, model = _get_openrouter_config(conn)
        if not api_key:
            return jsonify({"error": "Chave API OpenRouter não configurada."}), 400
            
        prompt = f"""Você é o Cérebro Municipal, assistente de IA da Prefeitura de Inajá.
Analise os metadados e o conteúdo de um arquivo da biblioteca municipal e sugira um nome padronizado, limpo e profissional para o arquivo (exemplo: "Lei-Municipal-123-2024.pdf" ou "Manual-de-Contas-Waitress.pdf").

METADADOS DO ARQUIVO:
- Nome Original: {row['nome_original']}
- Categoria: {row['categoria']}
- Descrição: {row['descricao']}

CONTEÚDO EXTRAÍDO DO ARQUIVO (PREVIEW):
{texto_conteudo[:2500]}

INSTRUÇÕES:
- O nome deve ser conciso, legível, sem espaços (use hifens ou CamelCase) e manter a extensão original do arquivo ({row['extensao']}).
- Sugira o nome mais adequado baseado nas informações do conteúdo ou do título original.
- Responda estritamente em formato JSON contendo as chaves:
  "sugestao": "o_nome_sugerido{row['extensao']}",
  "justificativa": "breve explicação do porquê desse nome (ex: detectado número da Lei 123 de 2024)."
"""

        response = _build_ai_service(api_key, model).chat_by_task(
            task_type="chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=250,
            use_cache=True,
            metadata={"feature": "sugerir_nome_documento", "doc_id": doc_id},
        )
        
        from services.openrouter_service import extract_json_block
        parsed = extract_json_block(response.text)
        sugestao = parsed.get("sugestao") if parsed else None
        justificativa = parsed.get("justificativa") if parsed else None
        
        if not sugestao:
            sugestao = row["nome_original"]
            justificativa = "Não foi possível obter sugestão da IA."
            
        return jsonify({
            "sugestao": sugestao,
            "justificativa": justificativa
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/documentos/<int:doc_id>/thumbnail", methods=["GET"])
@require_login
def documentos_obter_thumbnail(doc_id):
    try:
        thumb_path = os.path.join(DOCUMENTS_DIR, "thumbnails", f"{doc_id}.png")
        if not os.path.exists(thumb_path):
            return jsonify({"error": "Thumbnail não encontrada"}), 404
        return send_file(thumb_path, mimetype="image/png")
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/documentos/<int:doc_id>/thumbnail", methods=["POST"])
@require_login
def documentos_salvar_thumbnail(doc_id):
    try:
        # Apenas 'aleksandro' pode salvar ou atualizar capas na biblioteca
        if session.get("usuario_login") != "aleksandro":
            return jsonify({"error": "Apenas o usuário 'aleksandro' pode salvar capas na biblioteca."}), 403
            
        data = request.get_json(silent=True) or {}
        img_b64 = data.get("image")
        if not img_b64:
            return jsonify({"error": "Dados da imagem vazios"}), 400
            
        if "base64," in img_b64:
            img_b64 = img_b64.split("base64,")[1]
            
        img_data = base64.b64decode(img_b64)
        
        thumb_dir = os.path.join(DOCUMENTS_DIR, "thumbnails")
        os.makedirs(thumb_dir, exist_ok=True)
        thumb_path = os.path.join(thumb_dir, f"{doc_id}.png")
        
        with open(thumb_path, "wb") as f:
            f.write(img_data)
            
        return jsonify({"ok": True}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/documentos/<int:doc_id>/sugerir-metadados-csv", methods=["POST"])
@require_login
def documentos_sugerir_metadados_csv(doc_id):
    try:
        conn = get_db()
        row = conn.execute(
            "SELECT * FROM documentos_centro WHERE id=?", (doc_id,)
        ).fetchone()
        if not row:
            return jsonify({"error": "Documento não encontrado"}), 404

        abs_path = os.path.join(
            DOCUMENTS_DIR, row["caminho_relativo"].replace("/", os.sep)
        )
        
        texto_conteudo = ""
        if os.path.exists(abs_path):
            try:
                with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = [f.readline() for _ in range(150)]
                    texto_conteudo = "".join(lines)
            except Exception:
                pass
            
        from routes._shared import _get_openrouter_config, _build_ai_service
        api_key, model = _get_openrouter_config(conn)
        if not api_key:
            return jsonify({"error": "Chave API OpenRouter não configurada."}), 400
            
        prompt = f"""Você é o Cérebro Municipal, assistente de IA da Prefeitura de Inajá.
Analise a estrutura e o conteúdo de um arquivo CSV de relatório municipal para identificar o tipo de dados, dotações, período e finalidade.
Sugira uma Referência de período adequada (ex: "Exercício 2026", "Junho 2026"), uma Descrição limpa do relatório, e um nome profissional para o arquivo mantendo a extensão '.csv'.

NOME ORIGINAL DO ARQUIVO: {row['nome_original']}

PRIMEIRAS LINHAS DO CONTEÚDO CSV:
{texto_conteudo[:3000]}

INSTRUÇÕES:
- Identifique a data, ano, exercício fiscal ou período de referência contido nos cabeçalhos ou dados.
- O nome sugerido deve ser conciso, legível, sem espaços (use hifens) e terminar em '.csv'.
- Responda estritamente em formato JSON contendo as chaves:
  "referencia": "o_periodo_sugerido",
  "descricao": "breve_descricao_do_relatorio",
  "nome_sugerido": "nome-do-arquivo.csv"
"""

        response = _build_ai_service(api_key, model).chat_by_task(
            task_type="chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=250,
            use_cache=True,
            metadata={"feature": "sugerir_metadados_csv", "doc_id": doc_id},
        )
        
        from services.openrouter_service import extract_json_block
        parsed = extract_json_block(response.text)
        
        if parsed:
            referencia = parsed.get("referencia") or "Sem ref."
            descricao = parsed.get("descricao") or "Relatório CSV"
            nome_sugerido = parsed.get("nome_sugerido") or row["nome_original"]
            if not nome_sugerido.endswith(".csv"):
                nome_sugerido += ".csv"
                
            conn.execute(
                "UPDATE documentos_centro SET nome_original=?, referencia=?, descricao=? WHERE id=?",
                (nome_sugerido, referencia, descricao, doc_id)
            )
            
            # Auto-import CSV content to csv_importacoes if applicable
            _tipo_detectado = None
            try:
                import csv
                # Detect delimiter
                delimiter = ';'
                if os.path.exists(abs_path):
                    with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f_detect:
                        sample = f_detect.read(2048)
                        if ',' in sample and sample.count(',') > sample.count(';'):
                            delimiter = ','
                    
                    with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f_parse:
                        reader = csv.reader(f_parse, delimiter=delimiter)
                        headers = next(reader)
                        # Clean headers (strip and handle BOM)
                        headers = [h.strip().replace('\ufeff', '') for h in headers]
                        
                        # Score-based type detection with normalized headers
                        _hl = []
                        for _raw in headers:
                            _n = _raw.lower()
                            for _f, _t in [(' ', '_'), ('.', ''), ('ç', 'c'), ('ã', 'a'),
                                           ('á', 'a'), ('â', 'a'), ('é', 'e'), ('ê', 'e'),
                                           ('í', 'i'), ('ó', 'o'), ('ô', 'o'), ('ú', 'u'), ('º', '')]:
                                _n = _n.replace(_f, _t)
                            _hl.append(_n)
                        _EMP_STRONG = ('empenho', 'dotacao', 'subelemento', 'unidade_gestora',
                                       'unidade_orc', 'funcao', 'subfuncao', 'fonte_recurso',
                                       'modalidade_lic', 'acao_orc', 'nota_empenho', 'num_emp',
                                       'nro_emp', 'nr_emp')
                        _DES_STRONG = ('nota_pag', 'nota_liq', 'data_pag', 'data_liq',
                                       'vlr_pago', 'valor_pago', 'valor_liq', 'vlr_liq',
                                       'secretaria', 'departamento', 'tipo_despesa',
                                       'categoria_econ', 'grupo_desp')
                        _EMP_WEAK   = ('credor', 'favorecido', 'processo', 'licitacao')
                        _DES_WEAK   = ('saldo', 'orgao', 'competencia', 'mes_ref')
                        _score_emp = (sum(2 for h in _hl if any(t in h for t in _EMP_STRONG)) +
                                      sum(1 for h in _hl if any(t in h for t in _EMP_WEAK)))
                        _score_des = (sum(2 for h in _hl if any(t in h for t in _DES_STRONG)) +
                                      sum(1 for h in _hl if any(t in h for t in _DES_WEAK)))

                        if _score_emp > 0 or _score_des > 0:
                            tipo = 'empenho' if _score_emp >= _score_des else 'despesa'
                            _tipo_detectado = tipo
                            linhas_csv = []
                            for r_csv in reader:
                                if not r_csv:
                                    continue
                                r_dict = {}
                                for i, val in enumerate(r_csv):
                                    if i < len(headers):
                                        r_dict[headers[i]] = val.strip()
                                linhas_csv.append(r_dict)
                            
                            from datetime import datetime as _dt
                            now_str = _dt.now().strftime("%Y-%m-%d %H:%M:%S")
                            
                            # Check if table csv_importacoes exists
                            has_unified = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='csv_importacoes'").fetchone()
                            
                            if has_unified:
                                cur_u = conn.cursor()
                                cur_u.execute(
                                    "INSERT INTO csv_importacoes (tipo, periodo, descricao, arquivo, total_rows, colunas, importado_em) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                    (tipo, referencia, descricao, nome_sugerido, len(linhas_csv), json.dumps(headers, ensure_ascii=False), now_str)
                                )
                                imp_id = cur_u.lastrowid
                                cur_u.executemany(
                                    "INSERT INTO csv_linhas (importacao_id, dados) VALUES (?, ?)",
                                    [(imp_id, json.dumps(row_item, ensure_ascii=False)) for row_item in linhas_csv]
                                )
                            else:
                                # Fallback to old tables
                                old_table = "empenhos_importacoes" if tipo == "empenho" else "despesas_importacoes"
                                old_lines = "empenhos_linhas" if tipo == "empenho" else "despesas_linhas"
                                cur_u = conn.cursor()
                                if tipo == "empenho":
                                    cur_u.execute(
                                        f"INSERT INTO {old_table} (periodo, descricao, arquivo, total_rows, importado_em) VALUES (?, ?, ?, ?, ?)",
                                        (referencia, descricao, nome_sugerido, len(linhas_csv), now_str)
                                    )
                                else:
                                    cur_u.execute(
                                        f"INSERT INTO {old_table} (periodo, descricao, arquivo, total_rows, colunas, importado_em) VALUES (?, ?, ?, ?, ?, ?)",
                                        (referencia, descricao, nome_sugerido, len(linhas_csv), json.dumps(headers, ensure_ascii=False), now_str)
                                    )
                                imp_id = cur_u.lastrowid
                                cur_u.executemany(
                                    f"INSERT INTO {old_lines} (importacao_id, dados) VALUES (?, ?)",
                                    [(imp_id, json.dumps(row_item, ensure_ascii=False)) for row_item in linhas_csv]
                                )
                            
                            conn.execute(
                                "INSERT INTO logs (acao, detalhes) VALUES (?, ?)",
                                ("DOC_ATUALIZADO", f"CSV importado e integrado no banco automaticamente: '{nome_sugerido}' ({len(linhas_csv)} linhas)")
                            )
            except Exception as e_import:
                conn.execute(
                    "INSERT INTO logs (acao, detalhes) VALUES (?, ?)",
                    ("ERRO_SISTEMA", f"Falha na importação automática de CSV {doc_id}: {str(e_import)}")
                )
            
            conn.execute(
                "INSERT INTO logs (acao, detalhes) VALUES (?, ?)",
                ("DOC_ATUALIZADO", f"IA atualizou metadados do relatório CSV {doc_id}: '{nome_sugerido}' ({referencia})")
            )
            conn.commit()
            
            return jsonify({
                "ok": True,
                "referencia": referencia,
                "descricao": descricao,
                "nome_sugerido": nome_sugerido,
                "tipo": _tipo_detectado
            })
        else:
            return jsonify({"error": "Não foi possível obter sugestão da IA estruturada em JSON."}), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

