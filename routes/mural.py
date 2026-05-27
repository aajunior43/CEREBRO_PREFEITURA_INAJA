"""Blueprint: Mural de Recados e Tarefas Compartilhadas"""

import time as _time
from flask import Blueprint, request, jsonify, g, session
from routes._shared import get_db

bp = Blueprint("mural", __name__)


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
        
        return jsonify([dict(r) for r in rows])
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
            
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO mural_recados (titulo, conteudo, autor, destinatario, prioridade, categoria, cor, status) VALUES (?, ?, ?, ?, ?, ?, ?, 'a_fazer')",
            (titulo, conteudo, autor, destinatario, prioridade, categoria, cor)
        )
        conn.commit()
        
        row = conn.execute("SELECT * FROM mural_recados WHERE id=?", (cur.lastrowid,)).fetchone()
        return jsonify(dict(row)), 201
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
        for k in ("titulo", "conteudo", "autor", "destinatario", "prioridade", "categoria", "cor", "status"):
            if k in data:
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
        return jsonify(dict(updated))
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
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
