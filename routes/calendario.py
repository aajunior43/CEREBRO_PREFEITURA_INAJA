"""Blueprint: Calendário de Pagamentos — persistência no SQLite"""

from flask import Blueprint, g, request, jsonify

bp = Blueprint("calendario", __name__)


def _db():
    return g._get_db()


# ── GET /api/calendario ─────────────────────────────────────────────────────
# Retorna eventos, overrides e regras.
# Query param opcional: ?mes=YYYY-MM  → filtra eventos do mês
@bp.route("/api/calendario", methods=["GET"])
def calendario_get():
    conn = _db()
    mes = request.args.get("mes", "")  # "YYYY-MM" ou vazio = tudo

    if mes and len(mes) == 7:
        # Filtra eventos do mês
        eventos_rows = conn.execute(
            "SELECT id, data, tipo, texto FROM calendario_eventos WHERE data LIKE ? ORDER BY data, id",
            (mes + "-%",),
        ).fetchall()
        # Filtra overrides do mês
        overrides_rows = conn.execute(
            "SELECT data FROM calendario_overrides WHERE data LIKE ?",
            (mes + "-%",),
        ).fetchall()
    else:
        eventos_rows = conn.execute(
            "SELECT id, data, tipo, texto FROM calendario_eventos ORDER BY data, id"
        ).fetchall()
        overrides_rows = conn.execute(
            "SELECT data FROM calendario_overrides"
        ).fetchall()

    regras_rows = conn.execute(
        "SELECT chave, valor FROM calendario_regras"
    ).fetchall()

    return jsonify(
        {
            "eventos": [dict(r) for r in eventos_rows],
            "overrides": [r["data"] for r in overrides_rows],
            "regras": {r["chave"]: r["valor"] for r in regras_rows},
        }
    )


# ── POST /api/calendario/eventos ────────────────────────────────────────────
@bp.route("/api/calendario/eventos", methods=["POST"])
def calendario_evento_criar():
    conn = _db()
    data_body = request.get_json(silent=True) or {}

    data = (data_body.get("data") or "").strip()
    tipo = (data_body.get("tipo") or "").strip().upper()
    texto = (data_body.get("texto") or "").strip()

    if not data or not tipo or not texto:
        return jsonify({"error": "Campos data, tipo e texto são obrigatórios"}), 400
    if tipo not in ("PAYMENT", "COMMITMENT", "HOLIDAY", "NOTE"):
        return jsonify({"error": "Tipo inválido"}), 400

    # Marca o dia como override (eventos automáticos ficam suprimidos)
    conn.execute(
        "INSERT OR IGNORE INTO calendario_overrides (data) VALUES (?)", (data,)
    )
    cur = conn.execute(
        "INSERT INTO calendario_eventos (data, tipo, texto) VALUES (?, ?, ?)",
        (data, tipo, texto),
    )
    conn.commit()

    return jsonify(
        {"id": cur.lastrowid, "data": data, "tipo": tipo, "texto": texto}
    ), 201


# ── PUT /api/calendario/eventos/<id> ────────────────────────────────────────
@bp.route("/api/calendario/eventos/<int:evento_id>", methods=["PUT"])
def calendario_evento_atualizar(evento_id):
    conn = _db()
    row = conn.execute(
        "SELECT id, data FROM calendario_eventos WHERE id=?", (evento_id,)
    ).fetchone()
    if not row:
        return jsonify({"error": "Evento não encontrado"}), 404

    data_body = request.get_json(silent=True) or {}
    old_data = row["data"]
    new_data = (data_body.get("data") or old_data).strip()
    tipo = (data_body.get("tipo") or "").strip().upper()
    texto = (data_body.get("texto") or "").strip()

    if not tipo or not texto:
        return jsonify({"error": "Campos tipo e texto são obrigatórios"}), 400
    if tipo not in ("PAYMENT", "COMMITMENT", "HOLIDAY", "NOTE"):
        return jsonify({"error": "Tipo inválido"}), 400

    conn.execute(
        "UPDATE calendario_eventos SET data=?, tipo=?, texto=? WHERE id=?",
        (new_data, tipo, texto, evento_id),
    )
    # Garante que a nova data também tem override
    conn.execute(
        "INSERT OR IGNORE INTO calendario_overrides (data) VALUES (?)", (new_data,)
    )
    conn.commit()

    return jsonify({"id": evento_id, "data": new_data, "tipo": tipo, "texto": texto})


# ── DELETE /api/calendario/eventos/<id> ─────────────────────────────────────
@bp.route("/api/calendario/eventos/<int:evento_id>", methods=["DELETE"])
def calendario_evento_excluir(evento_id):
    conn = _db()
    row = conn.execute(
        "SELECT data FROM calendario_eventos WHERE id=?", (evento_id,)
    ).fetchone()
    if not row:
        return jsonify({"error": "Evento não encontrado"}), 404

    conn.execute("DELETE FROM calendario_eventos WHERE id=?", (evento_id,))
    conn.commit()
    return jsonify({"ok": True})


# ── POST /api/calendario/override ───────────────────────────────────────────
# Marca uma data como "override" (suprime eventos automáticos mesmo sem eventos customizados)
@bp.route("/api/calendario/override", methods=["POST"])
def calendario_override_criar():
    conn = _db()
    data_body = request.get_json(silent=True) or {}
    data = (data_body.get("data") or "").strip()
    if not data:
        return jsonify({"error": "Campo data é obrigatório"}), 400

    conn.execute(
        "INSERT OR IGNORE INTO calendario_overrides (data) VALUES (?)", (data,)
    )
    conn.commit()
    return jsonify({"ok": True, "data": data})


# ── DELETE /api/calendario/override/<data> ──────────────────────────────────
# Remove override e eventos customizados do dia → volta ao padrão automático
@bp.route("/api/calendario/override/<string:data>", methods=["DELETE"])
def calendario_override_excluir(data):
    conn = _db()
    conn.execute("DELETE FROM calendario_overrides WHERE data=?", (data,))
    conn.execute("DELETE FROM calendario_eventos WHERE data=?", (data,))
    conn.commit()
    return jsonify({"ok": True, "data": data})


# ── POST /api/calendario/regras ─────────────────────────────────────────────
# Salva regras em bulk: { chave: valor, ... }
@bp.route("/api/calendario/regras", methods=["POST"])
def calendario_regras_salvar():
    conn = _db()
    data_body = request.get_json(silent=True) or {}

    for chave, valor in data_body.items():
        chave = str(chave).strip()
        valor = str(valor).strip()
        if not chave:
            continue
        if valor:
            conn.execute(
                "INSERT INTO calendario_regras (chave, valor) VALUES (?, ?) "
                "ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor",
                (chave, valor),
            )
        else:
            conn.execute("DELETE FROM calendario_regras WHERE chave=?", (chave,))

    conn.commit()
    return jsonify({"ok": True})
