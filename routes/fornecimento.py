"""Blueprint: Fornecimento"""

import re
from flask import Blueprint, request, jsonify
from routes._shared import require_login

bp = Blueprint("fornecimento", __name__)


def get_db():
    from flask import g
    return g._get_db()


def safe_float(v):
    try:
        return float(v)
    except (ValueError, TypeError):
        return 0.0


def parse_money(s):
    if not s:
        return 0.0
    s = str(s).strip()
    s = re.sub(r"[^\d,.-]", "", s)
    if not s:
        return 0.0
    if "," in s:
        if "." in s:
            if s.index(".") < s.index(","):
                s = s.replace(".", "").replace(",", ".")
            else:
                s = s.replace(",", "")
        else:
            s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


@bp.route("/api/fornecimento/dados", methods=["GET"])
@require_login
def get_fornecimento_dados():
    try:
        conn = get_db()
        rows = conn.execute(
            "SELECT tipo,valor FROM fornecimento_dados ORDER BY valor ASC"
        ).fetchall()
        result = {"solicitantes": [], "empresas": [], "observacoes": []}
        for row in rows:
            if row["tipo"] in result:
                result[row["tipo"]].append(row["valor"])
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/fornecimento/dados", methods=["POST"])
@require_login
def add_fornecimento_dado():
    try:
        data = request.get_json() or {}
        tipo = (data.get("tipo") or "").strip()
        valor = (data.get("valor") or "").strip()
        if not tipo or not valor:
            return jsonify({"error": "tipo e valor são obrigatórios"}), 400
        conn = get_db()
        conn.execute(
            "INSERT OR IGNORE INTO fornecimento_dados (tipo,valor) VALUES (?,?)",
            (tipo, valor),
        )
        conn.commit()
        return jsonify({"ok": True}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/fornecimento/dados", methods=["DELETE"])
@require_login
def del_fornecimento_dado():
    try:
        data = request.get_json() or {}
        tipo = (data.get("tipo") or "").strip()
        valor = (data.get("valor") or "").strip()
        if not tipo or not valor:
            return jsonify({"error": "tipo e valor são obrigatórios"}), 400
        conn = get_db()
        conn.execute(
            "DELETE FROM fornecimento_dados WHERE tipo=? AND valor=?", (tipo, valor)
        )
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/fornecimento/templates", methods=["GET"])
@require_login
def list_templates():
    try:
        import json as _json
        conn = get_db()
        rows = conn.execute(
            "SELECT id, nome, dados, criado_em, atualizado_em FROM fornecimento_templates ORDER BY nome ASC"
        ).fetchall()
        return jsonify([
            {"id": r["id"], "nome": r["nome"], "dados": _json.loads(r["dados"] or "{}"),
             "criado_em": r["criado_em"], "atualizado_em": r["atualizado_em"]}
            for r in rows
        ])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/fornecimento/templates", methods=["POST"])
@require_login
def save_template():
    try:
        import json as _json
        data = request.get_json() or {}
        nome = (data.get("nome") or "").strip()
        if not nome:
            return jsonify({"error": "nome é obrigatório"}), 400
        dados = _json.dumps(data.get("dados") or {}, ensure_ascii=False)
        conn = get_db()
        conn.execute(
            """INSERT INTO fornecimento_templates (nome, dados, atualizado_em)
               VALUES (?, ?, datetime('now','localtime'))
               ON CONFLICT(nome) DO UPDATE SET dados=excluded.dados, atualizado_em=excluded.atualizado_em""",
            (nome, dados)
        )
        conn.commit()
        row = conn.execute(
            "SELECT id FROM fornecimento_templates WHERE nome=?", (nome,)
        ).fetchone()
        return jsonify({"ok": True, "id": row["id"]}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/fornecimento/templates/<int:tid>", methods=["DELETE"])
@require_login
def delete_template(tid):
    try:
        conn = get_db()
        conn.execute("DELETE FROM fornecimento_templates WHERE id=?", (tid,))
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/fornecimento/solicitacoes", methods=["GET"])
@require_login
def list_solicitacoes():
    try:
        q = request.args.get("q", "").strip()
        conn = get_db()
        if q:
            rows = conn.execute(
                """SELECT * FROM fornecimento_solicitacoes 
                   WHERE solicitante LIKE ? OR empresa LIKE ? OR obs LIKE ?
                   ORDER BY id DESC""",
                (f"%{q}%", f"%{q}%", f"%{q}%"),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM fornecimento_solicitacoes ORDER BY id DESC"
            ).fetchall()

        result = []
        for r in rows:
            sol_id = r["id"]
            items_rows = conn.execute(
                "SELECT * FROM fornecimento_solicitacao_itens WHERE solicitacao_id = ? ORDER BY id ASC",
                (sol_id,),
            ).fetchall()

            items = []
            valor_total = 0.0
            for item_row in items_rows:
                items.append(
                    {
                        "id": item_row["id"],
                        "nome": item_row["nome"],
                        "desc": item_row["desc"],
                        "qtd": item_row["qtd"],
                        "preco": item_row["preco"],
                    }
                )
                qtd_f = safe_float(item_row["qtd"])
                preco_f = parse_money(item_row["preco"])
                valor_total += qtd_f * preco_f

            result.append(
                {
                    "id": r["id"],
                    "solicitante": r["solicitante"],
                    "empresa": r["empresa"],
                    "data": r["data"],
                    "obs": r["obs"],
                    "criado_em": r["criado_em"],
                    "atualizado_em": r["atualizado_em"],
                    "total_itens": len(items),
                    "valor_total": valor_total,
                    "items": items,
                }
            )
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/fornecimento/solicitacoes", methods=["POST"])
@require_login
def create_solicitacao():
    try:
        data = request.get_json() or {}
        solicitante = (data.get("solicitante") or "").strip()
        empresa = (data.get("empresa") or "").strip()
        data_sol = (data.get("data") or "").strip()
        obs = (data.get("obs") or "").strip()
        items_payload = data.get("items") or []

        if not solicitante:
            return jsonify({"error": "Informe o solicitante."}), 400
        if not items_payload:
            return jsonify({"error": "Adicione pelo menos um item."}), 400

        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO fornecimento_solicitacoes (solicitante, empresa, data, obs)
               VALUES (?, ?, ?, ?)""",
            (solicitante, empresa, data_sol, obs),
        )
        sol_id = cur.lastrowid

        for item in items_payload:
            cur.execute(
                """INSERT INTO fornecimento_solicitacao_itens (solicitacao_id, nome, desc, qtd, preco)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    sol_id,
                    (item.get("nome") or "").strip(),
                    (item.get("desc") or "").strip(),
                    (item.get("qtd") or "").strip(),
                    (item.get("preco") or "").strip(),
                ),
            )
        conn.commit()

        saved = conn.execute(
            "SELECT * FROM fornecimento_solicitacoes WHERE id = ?", (sol_id,)
        ).fetchone()

        items_rows = conn.execute(
            "SELECT * FROM fornecimento_solicitacao_itens WHERE solicitacao_id = ? ORDER BY id ASC",
            (sol_id,),
        ).fetchall()

        items = []
        valor_total = 0.0
        for item_row in items_rows:
            items.append(
                {
                    "id": item_row["id"],
                    "nome": item_row["nome"],
                    "desc": item_row["desc"],
                    "qtd": item_row["qtd"],
                    "preco": item_row["preco"],
                }
            )
            qtd_f = safe_float(item_row["qtd"])
            preco_f = parse_money(item_row["preco"])
            valor_total += qtd_f * preco_f

        return jsonify(
            {
                "id": saved["id"],
                "solicitante": saved["solicitante"],
                "empresa": saved["empresa"],
                "data": saved["data"],
                "obs": saved["obs"],
                "criado_em": saved["criado_em"],
                "atualizado_em": saved["atualizado_em"],
                "total_itens": len(items),
                "valor_total": valor_total,
                "items": items,
            }
        ), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/fornecimento/solicitacoes/<int:id>", methods=["PUT"])
@require_login
def update_solicitacao(id):
    try:
        data = request.get_json() or {}
        solicitante = (data.get("solicitante") or "").strip()
        empresa = (data.get("empresa") or "").strip()
        data_sol = (data.get("data") or "").strip()
        obs = (data.get("obs") or "").strip()
        items_payload = data.get("items") or []

        if not solicitante:
            return jsonify({"error": "Informe o solicitante."}), 400
        if not items_payload:
            return jsonify({"error": "Adicione pelo menos um item."}), 400

        conn = get_db()
        cur = conn.cursor()

        curr = conn.execute(
            "SELECT id FROM fornecimento_solicitacoes WHERE id = ?", (id,)
        ).fetchone()
        if not curr:
            return jsonify({"error": "Solicitação não encontrada."}), 404

        cur.execute(
            """UPDATE fornecimento_solicitacoes 
               SET solicitante = ?, empresa = ?, data = ?, obs = ?, atualizado_em = datetime('now','localtime')
               WHERE id = ?""",
            (solicitante, empresa, data_sol, obs, id),
        )

        cur.execute(
            "DELETE FROM fornecimento_solicitacao_itens WHERE solicitacao_id = ?",
            (id,),
        )

        for item in items_payload:
            cur.execute(
                """INSERT INTO fornecimento_solicitacao_itens (solicitacao_id, nome, desc, qtd, preco)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    id,
                    (item.get("nome") or "").strip(),
                    (item.get("desc") or "").strip(),
                    (item.get("qtd") or "").strip(),
                    (item.get("preco") or "").strip(),
                ),
            )
        conn.commit()

        saved = conn.execute(
            "SELECT * FROM fornecimento_solicitacoes WHERE id = ?", (id,)
        ).fetchone()

        items_rows = conn.execute(
            "SELECT * FROM fornecimento_solicitacao_itens WHERE solicitacao_id = ? ORDER BY id ASC",
            (id,),
        ).fetchall()

        items = []
        valor_total = 0.0
        for item_row in items_rows:
            items.append(
                {
                    "id": item_row["id"],
                    "nome": item_row["nome"],
                    "desc": item_row["desc"],
                    "qtd": item_row["qtd"],
                    "preco": item_row["preco"],
                }
            )
            qtd_f = safe_float(item_row["qtd"])
            preco_f = parse_money(item_row["preco"])
            valor_total += qtd_f * preco_f

        return jsonify(
            {
                "id": saved["id"],
                "solicitante": saved["solicitante"],
                "empresa": saved["empresa"],
                "data": saved["data"],
                "obs": saved["obs"],
                "criado_em": saved["criado_em"],
                "atualizado_em": saved["atualizado_em"],
                "total_itens": len(items),
                "valor_total": valor_total,
                "items": items,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/fornecimento/solicitacoes/<int:id>", methods=["DELETE"])
@require_login
def delete_solicitacao(id):
    try:
        conn = get_db()
        cur = conn.cursor()

        curr = conn.execute(
            "SELECT id FROM fornecimento_solicitacoes WHERE id = ?", (id,)
        ).fetchone()
        if not curr:
            return jsonify({"error": "Solicitação não encontrada."}), 404

        cur.execute("DELETE FROM fornecimento_solicitacoes WHERE id = ?", (id,))
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/fornecimento/solicitacoes/<int:id>/duplicate", methods=["POST"])
@require_login
def duplicate_solicitacao(id):
    try:
        conn = get_db()
        cur = conn.cursor()

        orig = conn.execute(
            "SELECT * FROM fornecimento_solicitacoes WHERE id = ?", (id,)
        ).fetchone()
        if not orig:
            return jsonify({"error": "Solicitação original não encontrada."}), 404

        cur.execute(
            """INSERT INTO fornecimento_solicitacoes (solicitante, empresa, data, obs)
               VALUES (?, ?, ?, ?)""",
            (orig["solicitante"], orig["empresa"], orig["data"], orig["obs"]),
        )
        new_id = cur.lastrowid

        orig_items = conn.execute(
            "SELECT * FROM fornecimento_solicitacao_itens WHERE solicitacao_id = ?",
            (id,),
        ).fetchall()
        for item in orig_items:
            cur.execute(
                """INSERT INTO fornecimento_solicitacao_itens (solicitacao_id, nome, desc, qtd, preco)
                   VALUES (?, ?, ?, ?, ?)""",
                (new_id, item["nome"], item["desc"], item["qtd"], item["preco"]),
            )
        conn.commit()

        saved = conn.execute(
            "SELECT * FROM fornecimento_solicitacoes WHERE id = ?", (new_id,)
        ).fetchone()

        items_rows = conn.execute(
            "SELECT * FROM fornecimento_solicitacao_itens WHERE solicitacao_id = ? ORDER BY id ASC",
            (new_id,),
        ).fetchall()

        items = []
        valor_total = 0.0
        for item_row in items_rows:
            items.append(
                {
                    "id": item_row["id"],
                    "nome": item_row["nome"],
                    "desc": item_row["desc"],
                    "qtd": item_row["qtd"],
                    "preco": item_row["preco"],
                }
            )
            qtd_f = safe_float(item_row["qtd"])
            preco_f = parse_money(item_row["preco"])
            valor_total += qtd_f * preco_f

        return jsonify(
            {
                "id": saved["id"],
                "solicitante": saved["solicitante"],
                "empresa": saved["empresa"],
                "data": saved["data"],
                "obs": saved["obs"],
                "criado_em": saved["criado_em"],
                "atualizado_em": saved["atualizado_em"],
                "total_itens": len(items),
                "valor_total": valor_total,
                "items": items,
            }
        ), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

