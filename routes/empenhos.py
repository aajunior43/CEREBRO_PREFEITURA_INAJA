"""Blueprint: Empenhos"""

from flask import Blueprint, request, jsonify
import time as _time

bp = Blueprint("empenhos", __name__)


def get_db():
    from flask import g

    return g._get_db()


@bp.route("/api/empenhos/<int:ano>/<int:mes>", methods=["GET"])
def get_empenhos(ano, mes):
    try:
        from services.empenhos_service import listar_empenhos_mes

        return jsonify(listar_empenhos_mes(get_db(), ano, mes, dict))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/empenhos", methods=["POST"])
def toggle_empenho():
    d = request.get_json(force=True) or {}
    credor_id = d.get("credor_id")
    ano = d.get("ano")
    mes = d.get("mes")
    if not credor_id or not ano or not mes:
        return jsonify({"error": "credor_id, ano e mes são obrigatórios"}), 400
    try:
        from services.empenhos_service import persistir_empenho

        conn = get_db()
        result = persistir_empenho(
            conn, credor_id, ano, mes, _time.strftime("%Y-%m-%d %H:%M:%S")
        )
        conn.commit()
        return jsonify({"ok": True, "empenhado": result["empenhado"]})
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/empenhos/lote", methods=["POST"])
def empenho_lote():
    d = request.get_json(force=True) or {}
    itens = d.get("itens") or []
    if not itens:
        return jsonify({"error": "Nenhum item informado"}), 400
    try:
        from services.empenhos_service import persistir_empenho

        conn = get_db()
        resultados = []
        for item in itens:
            credor_id = item.get("credor_id")
            ano = item.get("ano")
            mes = item.get("mes")
            if not credor_id or not ano or not mes:
                return jsonify(
                    {"error": "Todos os itens devem conter credor_id, ano e mes"}
                ), 400
            resultados.append(
                persistir_empenho(
                    conn, credor_id, ano, mes, _time.strftime("%Y-%m-%d %H:%M:%S")
                )
            )
        conn.commit()
        return jsonify({"ok": True, "resultados": resultados})
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/credores/<int:cid>/historico", methods=["GET"])
def get_historico(cid):
    try:
        from services.empenhos_service import listar_historico_credor

        meses = request.args.get("meses", 6, type=int)
        meses = max(1, min(meses, 24))
        return jsonify(listar_historico_credor(get_db(), cid, meses, _time.localtime()))
    except Exception as e:
        return jsonify({"error": str(e)}), 500
