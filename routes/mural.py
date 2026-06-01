"""Blueprint: Mural de Recados e Tarefas Compartilhadas"""

import time as _time
import io
import queue
import json
import threading
from functools import wraps
from flask import Blueprint, request, jsonify, session, send_file, Response, stream_with_context
from werkzeug.utils import secure_filename
from routes._shared import get_db

bp = Blueprint("mural", __name__)

_mural_listeners = []
_mural_listeners_lock = threading.Lock()
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
VALID_PRIORIDADES = {"baixa", "media", "alta", "urgente"}
VALID_CATEGORIAS = {"aviso", "tarefa", "lembrete", "conquista"}
VALID_CORES = {"yellow", "blue", "green", "pink", "purple", "orange"}
VALID_STATUS = {"a_fazer", "em_andamento", "concluido"}


def _require_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "usuario_id" not in session:
            return jsonify({"error": "Nao autorizado"}), 403
        return fn(*args, **kwargs)

    return wrapper


def _pode_modificar(autor_recado: str) -> bool:
    """Autor do recado ou administrador podem editar/excluir."""
    if session.get("usuario_nivel") == "admin":
        return True
    nome = (session.get("usuario_nome") or "").strip().lower()
    return bool(nome) and nome == (autor_recado or "").strip().lower()


def _parse_valor(valor_raw) -> float:
    if valor_raw is None:
        return 0.0
    try:
        if isinstance(valor_raw, (int, float)):
            return float(valor_raw)
        cleaned = str(valor_raw).replace("R$", "").replace(" ", "")
        if "," in cleaned:
            cleaned = cleaned.replace(".", "").replace(",", ".")
        return float(cleaned) if cleaned else 0.0
    except (TypeError, ValueError):
        return 0.0


def _parse_credor_id(valor_raw):
    if valor_raw is None:
        return None
    try:
        cid = int(valor_raw)
        return cid if cid > 0 else None
    except (TypeError, ValueError):
        return None


def _normalize_choice(value, allowed, default):
    normalized = (value or default).strip().lower()
    if normalized == "media":
        normalized = "media"
    return normalized if normalized in allowed else default

def broadcast_mural_event(event_type, data):
    payload = f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
    dead = []
    with _mural_listeners_lock:
        listeners = list(_mural_listeners)
    for q in listeners:
        try:
            q.put_nowait(payload)
        except queue.Full:
            pass  # slow client: keep connection, drop only this message
        except Exception:
            dead.append(q)
    if dead:
        with _mural_listeners_lock:
            for q in dead:
                if q in _mural_listeners:
                    _mural_listeners.remove(q)


@bp.route("/api/mural", methods=["GET"])
@_require_auth
def mural_listar():
    try:
        conn = get_db()
        status_f = request.args.get("status")
        categoria = request.args.get("categoria")
        prioridade = request.args.get("prioridade")
        try:
            page = max(1, int(request.args.get("page", 1)))
            limit = min(200, max(1, int(request.args.get("limit", 100))))
        except (TypeError, ValueError):
            page, limit = 1, 100
        offset = (page - 1) * limit

        clauses, params = [], []
        if status_f:
            status_f = _normalize_choice(status_f, VALID_STATUS, "")
            if not status_f:
                return jsonify({"error": "Status invalido"}), 400
            clauses.append("status=?")
            params.append(status_f)
        if categoria:
            categoria = _normalize_choice(categoria, VALID_CATEGORIAS, "")
            if not categoria:
                return jsonify({"error": "Categoria invalida"}), 400
            clauses.append("categoria=?")
            params.append(categoria)
        if prioridade:
            prioridade = _normalize_choice(prioridade, VALID_PRIORIDADES, "")
            if not prioridade:
                return jsonify({"error": "Prioridade invalida"}), 400
            clauses.append("prioridade=?")
            params.append(prioridade)

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = conn.execute(
            "SELECT m.*, c.nome AS credor_nome, c.valor AS credor_valor, c.tipo_valor AS credor_tipo_valor "
            "FROM mural_recados m LEFT JOIN credores c ON m.credor_id=c.id " +
            where +
            " ORDER BY prioridade='urgente' DESC, prioridade='alta' DESC, prioridade='media' DESC, prioridade='baixa' DESC, m.criado_em DESC LIMIT ? OFFSET ?",
            params + [limit, offset]
        ).fetchall()

        recados = [dict(r) for r in rows]
        if recados:
            recado_ids = [r["id"] for r in recados]
            placeholders = ",".join("?" for _ in recado_ids)
            attachments = conn.execute(
                f"SELECT id, recado_id, file_name, mime_type, file_size, criado_em FROM mural_anexos WHERE recado_id IN ({placeholders}) ORDER BY criado_em DESC",
                recado_ids
            ).fetchall()

            from collections import defaultdict
            attachments_by_recado = defaultdict(list)
            for att in attachments:
                attachments_by_recado[att["recado_id"]].append(dict(att))

            for r in recados:
                r["attachments"] = attachments_by_recado[r["id"]]
        else:
            for r in recados:
                r["attachments"] = []

        return jsonify(recados)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/mural", methods=["POST"])
@_require_auth
def mural_criar():
    try:
        data = request.get_json(force=True) or {}
        titulo = (data.get("titulo") or "").strip()
        conteudo = (data.get("conteudo") or "").strip()

        if not titulo or not conteudo:
            return jsonify({"error": "Titulo e conteudo sao obrigatorios"}), 400

        autor = (data.get("autor") or session.get("usuario_nome") or "Servidor").strip()
        destinatario = (data.get("destinatario") or "Todos").strip()
        prioridade = _normalize_choice(data.get("prioridade"), VALID_PRIORIDADES, "media")
        categoria = _normalize_choice(data.get("categoria"), VALID_CATEGORIAS, "tarefa")
        cor = _normalize_choice(data.get("cor"), VALID_CORES, "yellow")

        credor_id = _parse_credor_id(data.get("credor_id"))
        valor = _parse_valor(data.get("valor"))

        conn = get_db()

        # Auto-populate valor from credores if credor_id given and no explicit valor key
        if credor_id is not None and "valor" not in data:
            credor_row = conn.execute(
                "SELECT valor FROM credores WHERE id=? AND ativo=1", (credor_id,)
            ).fetchone()
            if credor_row:
                valor = credor_row["valor"]

        cur = conn.cursor()
        cur.execute(
            "INSERT INTO mural_recados (titulo, conteudo, autor, destinatario, prioridade, categoria, cor, status, valor, credor_id) VALUES (?, ?, ?, ?, ?, ?, ?, 'a_fazer', ?, ?)",
            (titulo, conteudo, autor, destinatario, prioridade, categoria, cor, valor, credor_id)
        )
        conn.commit()

        # Re-read with LEFT JOIN to include credor info in response/SSE
        row = conn.execute(
            "SELECT m.*, c.nome AS credor_nome, c.valor AS credor_valor, c.tipo_valor AS credor_tipo_valor "
            "FROM mural_recados m LEFT JOIN credores c ON m.credor_id=c.id WHERE m.id=?",
            (cur.lastrowid,)
        ).fetchone()
        res = dict(row)
        res["attachments"] = []
        broadcast_mural_event("create", res)
        return jsonify(res), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/mural/<int:recado_id>", methods=["PUT"])
@_require_auth
def mural_atualizar(recado_id):
    try:
        data = request.get_json(force=True) or {}
        conn = get_db()
        row = conn.execute("SELECT * FROM mural_recados WHERE id=?", (recado_id,)).fetchone()
        if not row:
            return jsonify({"error": "Recado nao encontrado"}), 404

        # Status change (mover entre colunas) é permitido para todos os autenticados
        status_only = {"status", "concluido_por", "concluido_em"}
        if not data.keys() <= status_only and not _pode_modificar(row["autor"]):
            return jsonify({"error": "Sem permissao para editar este recado. Apenas o autor ou o administrador pode editar."}), 403

        fields = {}
        for k in ("titulo", "conteudo", "autor", "destinatario", "prioridade", "categoria", "cor", "status", "valor", "credor_id"):
            if k in data:
                if k == "valor":
                    fields[k] = _parse_valor(data[k])
                elif k == "credor_id":
                    fields[k] = _parse_credor_id(data[k])
                elif k == "prioridade":
                    fields[k] = _normalize_choice(data[k], VALID_PRIORIDADES, row["prioridade"] or "media")
                elif k == "categoria":
                    fields[k] = _normalize_choice(data[k], VALID_CATEGORIAS, row["categoria"] or "tarefa")
                elif k == "cor":
                    fields[k] = _normalize_choice(data[k], VALID_CORES, row["cor"] or "yellow")
                elif k == "status":
                    status = _normalize_choice(data[k], VALID_STATUS, "")
                    if not status:
                        return jsonify({"error": "Status invalido"}), 400
                    fields[k] = status
                else:
                    fields[k] = (data[k] or "").strip()

        # If credor_id changed and no explicit valor provided, auto-populate
        if "credor_id" in fields and "valor" not in data:
            cid = fields["credor_id"]
            if cid is not None:
                credor_row = conn.execute(
                    "SELECT valor FROM credores WHERE id=? AND ativo=1", (cid,)
                ).fetchone()
                if credor_row:
                    fields["valor"] = credor_row["valor"]

        # Status completion logic
        if "status" in data:
            new_status = fields.get("status", "")
            if new_status == "concluido" and row["status"] != "concluido":
                fields["concluido_por"] = session.get("usuario_nome") or "Servidor"
                fields["concluido_em"] = _time.strftime("%d/%m/%Y %H:%M")
            elif new_status != "concluido":
                fields["concluido_por"] = ""
                fields["concluido_em"] = ""

        if not fields:
            return jsonify(dict(row))

        fields["atualizado_em"] = _time.strftime("%Y-%m-%d %H:%M:%S")
        set_clause = ", ".join(f"{k}=?" for k in fields)
        conn.execute(
            f"UPDATE mural_recados SET {set_clause} WHERE id=?",
            list(fields.values()) + [recado_id]
        )
        conn.commit()

        updated = conn.execute(
            "SELECT m.*, c.nome AS credor_nome, c.valor AS credor_valor, c.tipo_valor AS credor_tipo_valor "
            "FROM mural_recados m LEFT JOIN credores c ON m.credor_id=c.id WHERE m.id=?",
            (recado_id,)
        ).fetchone()
        res = dict(updated)

        attachments = conn.execute(
            "SELECT id, recado_id, file_name, mime_type, file_size, criado_em FROM mural_anexos WHERE recado_id=? ORDER BY criado_em DESC",
            (recado_id,)
        ).fetchall()
        res["attachments"] = [dict(a) for a in attachments]

        broadcast_mural_event("update", res)
        return jsonify(res)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/mural/<int:recado_id>", methods=["DELETE"])
@_require_auth
def mural_excluir(recado_id):
    try:
        conn = get_db()
        row = conn.execute("SELECT autor FROM mural_recados WHERE id=?", (recado_id,)).fetchone()
        if not row:
            return jsonify({"error": "Recado nao encontrado"}), 404
        if not _pode_modificar(row["autor"]):
            return jsonify({"error": "Sem permissao para excluir este recado."}), 403
        conn.execute("DELETE FROM mural_recados WHERE id=?", (recado_id,))
        conn.commit()
        broadcast_mural_event("delete", {"id": recado_id})
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -- Mural Credores Dropdown --

@bp.route("/api/mural/credores", methods=["GET"])
@_require_auth
def mural_credores_dropdown():
    try:
        conn = get_db()
        q = request.args.get("q", "").strip()
        if q:
            rows = conn.execute(
                "SELECT id, nome, valor, tipo_valor, departamento FROM credores WHERE ativo=1 AND nome LIKE ? ORDER BY nome LIMIT 100",
                (f"%{q}%",)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, nome, valor, tipo_valor, departamento FROM credores WHERE ativo=1 ORDER BY nome LIMIT 200"
            ).fetchall()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -- Mural Attachments --

@bp.route("/api/mural/<int:recado_id>/attachments", methods=["POST"])
@_require_auth
def mural_anexo_criar(recado_id):
    try:
        conn = get_db()
        row = conn.execute("SELECT id FROM mural_recados WHERE id=?", (recado_id,)).fetchone()
        if not row:
            return jsonify({"error": "Recado nao encontrado"}), 404

        if "file" not in request.files:
            return jsonify({"error": "Nenhum arquivo enviado"}), 400

        f = request.files["file"]
        if not f or f.filename == "":
            return jsonify({"error": "Nome de arquivo invalido"}), 400

        file_name = secure_filename(f.filename)
        if not file_name:
            return jsonify({"error": "Nome de arquivo invalido"}), 400
        content = f.read()
        file_size = len(content)
        if file_size > MAX_ATTACHMENT_BYTES:
            return jsonify({"error": "Arquivo excede o limite de 10 MB"}), 413
        mime_type = f.mimetype or "application/octet-stream"

        cur = conn.cursor()
        cur.execute(
            "INSERT INTO mural_anexos (recado_id, file_name, mime_type, file_size) VALUES (?, ?, ?, ?)",
            (recado_id, file_name, mime_type, file_size)
        )
        attachment_id = cur.lastrowid
        cur.execute(
            "INSERT INTO mural_anexo_contents (attachment_id, content) VALUES (?, ?)",
            (attachment_id, content)
        )
        conn.commit()

        return jsonify({
            "id": attachment_id,
            "recado_id": recado_id,
            "file_name": file_name,
            "mime_type": mime_type,
            "file_size": file_size
        }), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/mural/<int:recado_id>/attachments/<int:attachment_id>/download", methods=["GET"])
@_require_auth
def mural_anexo_download(recado_id, attachment_id):
    try:
        conn = get_db()
        row = conn.execute(
            "SELECT a.file_name, a.mime_type, c.content FROM mural_anexos a "
            "JOIN mural_anexo_contents c ON a.id = c.attachment_id "
            "WHERE a.id=? AND a.recado_id=?",
            (attachment_id, recado_id)
        ).fetchone()

        if not row:
            return "Anexo nao encontrado", 404

        return send_file(
            io.BytesIO(row["content"]),
            mimetype=row["mime_type"],
            as_attachment=True,
            download_name=row["file_name"]
        )
    except Exception as e:
        return str(e), 500


@bp.route("/api/mural/<int:recado_id>/attachments/<int:attachment_id>", methods=["DELETE"])
@_require_auth
def mural_anexo_excluir(recado_id, attachment_id):
    try:
        conn = get_db()
        row = conn.execute("SELECT id FROM mural_anexos WHERE id=? AND recado_id=?", (attachment_id, recado_id)).fetchone()
        if not row:
            return jsonify({"error": "Anexo nao encontrado"}), 404

        conn.execute("DELETE FROM mural_anexos WHERE id=?", (attachment_id,))
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -- Mural Events (SSE) --

@bp.route("/api/mural/events", methods=["GET"])
@_require_auth
def mural_events():
    @stream_with_context
    def event_stream():
        q = queue.Queue(maxsize=100)
        with _mural_listeners_lock:
            _mural_listeners.append(q)
        yield b": connected\n\n"
        try:
            while True:
                try:
                    msg = q.get(timeout=5.0)
                    if isinstance(msg, str):
                        msg = msg.encode("utf-8")
                    yield msg
                except queue.Empty:
                    yield b"event: heartbeat\ndata: {}\n\n"
        except GeneratorExit:
            pass
        except Exception:
            pass
        finally:
            with _mural_listeners_lock:
                if q in _mural_listeners:
                    _mural_listeners.remove(q)

    resp = Response(
        event_stream(),
        mimetype="text/event-stream",
    )
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    resp.headers["X-Accel-Buffering"] = "no"
    resp.headers["Connection"] = "keep-alive"
    return resp


# -- Mural Comments --

@bp.route("/api/mural/<int:recado_id>/comments", methods=["GET"])
@_require_auth
def mural_comentarios_listar(recado_id):
    try:
        conn = get_db()
        rows = conn.execute(
            "SELECT id, recado_id, autor, texto, criado_em FROM mural_comentarios WHERE recado_id=? ORDER BY criado_em ASC",
            (recado_id,)
        ).fetchall()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/mural/<int:recado_id>/comments", methods=["POST"])
@_require_auth
def mural_comentario_criar(recado_id):
    try:
        data = request.get_json(force=True) or {}
        texto = (data.get("texto") or "").strip()
        if not texto:
            return jsonify({"error": "Texto do comentario e obrigatorio"}), 400

        autor = (data.get("autor") or session.get("usuario_nome") or "Servidor").strip()

        conn = get_db()
        if not conn.execute("SELECT id FROM mural_recados WHERE id=?", (recado_id,)).fetchone():
            return jsonify({"error": "Recado nao encontrado"}), 404
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO mural_comentarios (recado_id, autor, texto) VALUES (?, ?, ?)",
            (recado_id, autor, texto)
        )
        conn.commit()

        row = conn.execute("SELECT * FROM mural_comentarios WHERE id=?", (cur.lastrowid,)).fetchone()
        res = dict(row)

        broadcast_mural_event("comment", {"recado_id": recado_id, "comment": res})
        return jsonify(res), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500
