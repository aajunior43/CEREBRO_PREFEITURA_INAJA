"""Blueprint: Protocolos"""

import io as _io
import time as _time
from flask import Blueprint, request, jsonify, send_file

bp = Blueprint("protocolos", __name__)


def get_db():
    from flask import g
    return g._get_db()


def _proximo_numero_protocolo(conn):
    ano = _time.strftime("%Y")
    ultimo = conn.execute(
        "SELECT numero FROM protocolos WHERE numero LIKE ? ORDER BY id DESC LIMIT 1",
        (f"PROT-{ano}-%",),
    ).fetchone()
    if ultimo:
        try:
            seq = int(ultimo["numero"].split("-")[-1]) + 1
        except Exception:
            seq = 1
    else:
        seq = 1
    return f"PROT-{ano}-{seq:04d}"


@bp.route("/api/protocolos/proximo-numero", methods=["GET"])
def protocolo_proximo_numero():
    try:
        return jsonify({"numero": _proximo_numero_protocolo(get_db())})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/protocolos", methods=["GET"])
def protocolos_listar():
    try:
        limit = max(1, min(request.args.get("limit", 100, type=int), 1000))
        offset = max(0, request.args.get("offset", 0, type=int))
        conn = get_db()
        clauses, params = [], []
        for field in ("tipo", "status", "direcao"):
            val = request.args.get(field, "")
            if val:
                clauses.append(f"{field}=?")
                params.append(val)
        busca = request.args.get("busca", "").strip()
        if busca:
            # Try FTS5 first
            fts_exists = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='protocolos_fts'").fetchone()
            if fts_exists:
                clauses.append("id IN (SELECT rowid FROM protocolos_fts WHERE protocolos_fts MATCH ?)")
                params.append(busca)
            else:
                like = f"%{busca.lower()}%"
                clauses.append(
                    "(LOWER(assunto) LIKE ? OR LOWER(origem_destino) LIKE ? OR numero LIKE ?)"
                )
                params.extend([like, like, like])
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        total = conn.execute(
            f"SELECT COUNT(*) FROM protocolos {where}", params
        ).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM protocolos {where} ORDER BY id DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()
        return jsonify({"items": [dict(r) for r in rows], "total": total, "limit": limit, "offset": offset})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/protocolos", methods=["POST"])
def protocolos_criar():
    try:
        data = request.get_json(force=True) or {}
        assunto = (data.get("assunto") or "").strip()
        tipo = (data.get("tipo") or "").strip()
        data_protocolo = (data.get("data_protocolo") or "").strip()
        if not assunto or not tipo or not data_protocolo:
            return jsonify(
                {"error": "assunto, tipo e data_protocolo são obrigatórios"}
            ), 400
        conn = get_db()
        numero = data.get("numero") or _proximo_numero_protocolo(conn)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO protocolos (numero,tipo,direcao,origem_destino,assunto,data_protocolo,prazo_resposta,status,observacoes) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                numero,
                tipo,
                (data.get("direcao") or "recebido").strip(),
                (data.get("origem_destino") or "").strip(),
                assunto,
                data_protocolo,
                (data.get("prazo_resposta") or "").strip(),
                (data.get("status") or "recebido").strip(),
                (data.get("observacoes") or "").strip(),
            ),
        )
        conn.commit()
        return jsonify(
            dict(
                conn.execute(
                    "SELECT * FROM protocolos WHERE id=?", (cur.lastrowid,)
                ).fetchone()
            )
        ), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/protocolos/<int:prot_id>", methods=["PUT"])
def protocolos_atualizar(prot_id):
    try:
        data = request.get_json(force=True) or {}
        conn = get_db()
        if not conn.execute(
            "SELECT * FROM protocolos WHERE id=?", (prot_id,)
        ).fetchone():
            return jsonify({"error": "Protocolo não encontrado"}), 404
        fields = {}
        for k in (
            "tipo",
            "direcao",
            "origem_destino",
            "assunto",
            "data_protocolo",
            "prazo_resposta",
            "status",
            "observacoes",
        ):
            if k in data:
                fields[k] = (data[k] or "").strip()
        if not fields:
            return jsonify(
                dict(
                    conn.execute(
                        "SELECT * FROM protocolos WHERE id=?", (prot_id,)
                    ).fetchone()
                )
            )
        set_clause = ", ".join(f"{k}=?" for k in fields)
        conn.execute(
            f"UPDATE protocolos SET {set_clause} WHERE id=?",
            list(fields.values()) + [prot_id],
        )
        conn.commit()
        return jsonify(
            dict(
                conn.execute(
                    "SELECT * FROM protocolos WHERE id=?", (prot_id,)
                ).fetchone()
            )
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/protocolos/<int:prot_id>", methods=["DELETE"])
def protocolos_excluir(prot_id):
    try:
        conn = get_db()
        if not conn.execute(
            "SELECT id FROM protocolos WHERE id=?", (prot_id,)
        ).fetchone():
            return jsonify({"error": "Protocolo não encontrado"}), 404
        conn.execute("DELETE FROM protocolos WHERE id=?", (prot_id,))
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/protocolos/<int:prot_id>/anexos", methods=["GET"])
def protocolo_anexos_listar(prot_id):
    try:
        conn = get_db()
        rows = conn.execute(
            "SELECT id,protocolo_id,file_name,mime_type,file_size,criado_em FROM protocolo_anexos WHERE protocolo_id=? ORDER BY id",
            (prot_id,),
        ).fetchall()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/protocolos/<int:prot_id>/anexos", methods=["POST"])
def protocolo_anexos_upload(prot_id):
    try:
        conn = get_db()
        if not conn.execute(
            "SELECT id FROM protocolos WHERE id=?", (prot_id,)
        ).fetchone():
            return jsonify({"error": "Protocolo não encontrado"}), 404
        file = request.files.get("arquivo")
        if not file:
            return jsonify({"error": "Nenhum arquivo enviado"}), 400
        content = file.read()
        if not content:
            return jsonify({"error": "Arquivo vazio"}), 400
        if len(content) > 20 * 1024 * 1024:
            return jsonify({"error": "Arquivo excede 20 MB"}), 413
        cur = conn.execute(
            "INSERT INTO protocolo_anexos (protocolo_id,file_name,mime_type,file_size) VALUES (?,?,?,?)",
            (
                prot_id,
                file.filename,
                file.mimetype or "application/octet-stream",
                len(content),
            ),
        )
        anexo_id = cur.lastrowid
        conn.execute(
            "INSERT INTO protocolo_anexo_contents (anexo_id, content) VALUES (?, ?)",
            (anexo_id, content),
        )
        conn.commit()
        return jsonify(
            dict(
                conn.execute(
                    "SELECT id,protocolo_id,file_name,mime_type,file_size,criado_em FROM protocolo_anexos WHERE id=?",
                    (cur.lastrowid,),
                ).fetchone()
            )
        ), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route(
    "/api/protocolos/<int:prot_id>/anexos/<int:anexo_id>/download", methods=["GET"]
)
def protocolo_anexo_download(prot_id, anexo_id):
    try:
        conn = get_db()
        row = conn.execute(
            "SELECT a.file_name, a.mime_type, c.content "
            "FROM protocolo_anexos a "
            "JOIN protocolo_anexo_contents c ON a.id = c.anexo_id "
            "WHERE a.id=? AND a.protocolo_id=?",
            (anexo_id, prot_id),
        ).fetchone()
        if not row:
            return jsonify({"error": "Anexo não encontrado"}), 404
        return send_file(
            _io.BytesIO(row["content"]),
            mimetype=row["mime_type"] or "application/octet-stream",
            as_attachment=True,
            download_name=row["file_name"],
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route(
    "/api/protocolos/<int:prot_id>/anexos/<int:anexo_id>", methods=["DELETE"]
)
def protocolo_anexo_excluir(prot_id, anexo_id):
    try:
        conn = get_db()
        if not conn.execute(
            "SELECT id FROM protocolo_anexos WHERE id=? AND protocolo_id=?",
            (anexo_id, prot_id),
        ).fetchone():
            return jsonify({"error": "Anexo não encontrado"}), 404
        conn.execute("DELETE FROM protocolo_anexos WHERE id=?", (anexo_id,))
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
