"""Blueprint: Mural de Recados e Tarefas Compartilhadas"""

import time as _time
import io
import queue
import json
from flask import Blueprint, request, jsonify, g, session, send_file, Response
from routes._shared import get_db

bp = Blueprint("mural", __name__)

_mural_listeners = []

def broadcast_mural_event(event_type, data):
    global _mural_listeners
    payload = f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
    active_listeners = []
    for q in _mural_listeners:
        try:
            q.put_nowait(payload)
            active_listeners.append(q)
        except queue.Full:
            pass
        except Exception:
            pass
    _mural_listeners = active_listeners


@bp.route("/api/mural", methods=["GET"])
def mural_listar():
    try:
        conn = get_db()
        status_f = request.args.get("status")
        categoria = request.args.get("categoria")
        prioridade = request.args.get("prioridade")
        
        clauses, params = [], []
        if status_f:
            clauses.append("status=?")
            params.append(status_f)
        if categoria:
            clauses.append("categoria=?")
            params.append(categoria)
        if prioridade:
            clauses.append("prioridade=?")
            params.append(prioridade)
            
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = conn.execute(
            f"SELECT * FROM mural_recados {where} ORDER BY prioridade='urgente' DESC, prioridade='alta' DESC, prioridade='media' DESC, prioridade='baixa' DESC, criado_em DESC",
            params
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
def mural_criar():
    try:
        data = request.get_json(force=True) or {}
        titulo = (data.get("titulo") or "").strip()
        conteudo = (data.get("conteudo") or "").strip()
        
        if not titulo or not conteudo:
            return jsonify({"error": "Título e conteúdo são obrigatórios"}), 400
            
        autor = (data.get("autor") or session.get("usuario_nome") or "Servidor").strip()
        destinatario = (data.get("destinatario") or "Todos").strip()
        prioridade = (data.get("prioridade") or "media").strip().lower()
        categoria = (data.get("categoria") or "tarefa").strip().lower()
        cor = (data.get("cor") or "yellow").strip().lower()
        
        if prioridade not in ("baixa", "média", "media", "alta", "urgente"):
            prioridade = "media"
        if categoria not in ("aviso", "tarefa", "lembrete", "conquista"):
            categoria = "tarefa"
            
        valor_raw = data.get("valor")
        valor = 0.0
        if valor_raw is not None:
            try:
                if isinstance(valor_raw, (int, float)):
                    valor = float(valor_raw)
                else:
                    cleaned = str(valor_raw).replace("R$", "").replace(" ", "")
                    if "," in cleaned:
                        cleaned = cleaned.replace(".", "").replace(",", ".")
                    valor = float(cleaned) if cleaned else 0.0
            except ValueError:
                valor = 0.0

        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO mural_recados (titulo, conteudo, autor, destinatario, prioridade, categoria, cor, status, valor) VALUES (?, ?, ?, ?, ?, ?, ?, 'a_fazer', ?)",
            (titulo, conteudo, autor, destinatario, prioridade, categoria, cor, valor)
        )
        conn.commit()
        
        row = conn.execute("SELECT * FROM mural_recados WHERE id=?", (cur.lastrowid,)).fetchone()
        res = dict(row)
        res["attachments"] = []
        broadcast_mural_event("create", res)
        return jsonify(res), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/mural/<int:recado_id>", methods=["PUT"])
def mural_atualizar(recado_id):
    try:
        data = request.get_json(force=True) or {}
        conn = get_db()
        row = conn.execute("SELECT * FROM mural_recados WHERE id=?", (recado_id,)).fetchone()
        if not row:
            return jsonify({"error": "Recado não encontrado"}), 404
            
        fields = {}
        for k in ("titulo", "conteudo", "autor", "destinatario", "prioridade", "categoria", "cor", "status", "valor"):
            if k in data:
                if k == "valor":
                    try:
                        val_raw = data[k]
                        if val_raw is None:
                            fields[k] = 0.0
                        elif isinstance(val_raw, (int, float)):
                            fields[k] = float(val_raw)
                        else:
                            cleaned = str(val_raw).replace("R$", "").replace(" ", "")
                            if "," in cleaned:
                                cleaned = cleaned.replace(".", "").replace(",", ".")
                            fields[k] = float(cleaned) if cleaned else 0.0
                    except ValueError:
                        fields[k] = 0.0
                else:
                    fields[k] = (data[k] or "").strip()
                
        # Status completion logic
        if "status" in data:
            new_status = data["status"].strip().lower()
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
        
        updated = conn.execute("SELECT * FROM mural_recados WHERE id=?", (recado_id,)).fetchone()
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
def mural_excluir(recado_id):
    try:
        conn = get_db()
        if not conn.execute("SELECT id FROM mural_recados WHERE id=?", (recado_id,)).fetchone():
            return jsonify({"error": "Recado não encontrado"}), 404
        conn.execute("DELETE FROM mural_recados WHERE id=?", (recado_id,))
        conn.commit()
        broadcast_mural_event("delete", {"id": recado_id})
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Mural Attachments ──

@bp.route("/api/mural/<int:recado_id>/attachments", methods=["POST"])
def mural_anexo_criar(recado_id):
    try:
        conn = get_db()
        row = conn.execute("SELECT id FROM mural_recados WHERE id=?", (recado_id,)).fetchone()
        if not row:
            return jsonify({"error": "Recado não encontrado"}), 404
            
        if "file" not in request.files:
            return jsonify({"error": "Nenhum arquivo enviado"}), 400
            
        f = request.files["file"]
        if not f or f.filename == "":
            return jsonify({"error": "Nome de arquivo inválido"}), 400
            
        file_name = f.filename
        content = f.read()
        file_size = len(content)
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
            return "Anexo não encontrado", 404
            
        return send_file(
            io.BytesIO(row["content"]),
            mimetype=row["mime_type"],
            as_attachment=True,
            download_name=row["file_name"]
        )
    except Exception as e:
        return str(e), 500


@bp.route("/api/mural/<int:recado_id>/attachments/<int:attachment_id>", methods=["DELETE"])
def mural_anexo_excluir(recado_id, attachment_id):
    try:
        conn = get_db()
        row = conn.execute("SELECT id FROM mural_anexos WHERE id=? AND recado_id=?", (attachment_id, recado_id)).fetchone()
        if not row:
            return jsonify({"error": "Anexo não encontrado"}), 404
            
        conn.execute("DELETE FROM mural_anexos WHERE id=?", (attachment_id,))
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Mural Events (SSE) ──

@bp.route("/api/mural/events", methods=["GET"])
def mural_events():
    def event_stream():
        q = queue.Queue(maxsize=100)
        _mural_listeners.append(q)
        try:
            while True:
                try:
                    msg = q.get(timeout=20.0)
                    yield msg
                except queue.Empty:
                    yield "event: heartbeat\ndata: {}\n\n"
        except GeneratorExit:
            if q in _mural_listeners:
                _mural_listeners.remove(q)
                
    return Response(event_stream(), mimetype="text/event-stream")


# ── Mural Comments ──

@bp.route("/api/mural/<int:recado_id>/comments", methods=["GET"])
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
def mural_comentario_criar(recado_id):
    try:
        data = request.get_json(force=True) or {}
        texto = (data.get("texto") or "").strip()
        if not texto:
            return jsonify({"error": "Texto do comentário é obrigatório"}), 400
            
        autor = (data.get("autor") or session.get("usuario_nome") or "Servidor").strip()
        
        conn = get_db()
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
