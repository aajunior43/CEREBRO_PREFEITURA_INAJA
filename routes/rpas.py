"""Blueprint: RPAs"""

from flask import Blueprint, request, jsonify

bp = Blueprint("rpas", __name__)


def get_db():
    from flask import g
    return g._get_db()


def row_to_dict(row):
    return dict(row)


@bp.route("/api/rpas", methods=["GET"])
def get_rpas():
    try:
        limit = max(1, min(request.args.get("limit", 100, type=int), 1000))
        offset = max(0, request.args.get("offset", 0, type=int))
        conn = get_db()
        total = conn.execute("SELECT COUNT(*) AS total FROM rpas").fetchone()["total"]
        rows = conn.execute(
            "SELECT * FROM rpas ORDER BY criado_em DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
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


@bp.route("/api/rpas", methods=["POST"])
def create_rpa():
    try:
        data = request.get_json() or {}
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO rpas (numero_rpa,nome_prestador,cpf_prestador,endereco_prestador,descricao_servico,periodo_referencia,carga_horaria,local_execucao,valor_bruto,num_dependentes,pensao_alimenticia,inss,iss,deducao_dependentes,base_calculo_irrf,aliquota_irrf,parcela_deduzir_irrf,ir,valor_liquido,observacoes,data_emissao) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                data.get("numeroRPA"),
                data.get("nomePrestador", ""),
                data.get("cpfPrestador"),
                data.get("enderecoPrestador"),
                data.get("descricaoServico"),
                data.get("periodoReferencia"),
                data.get("cargaHoraria"),
                data.get("localExecucao"),
                data.get("valorBruto", 0),
                data.get("numDependentes", 0),
                data.get("pensaoAlimenticia", 0),
                data.get("inss", 0),
                data.get("iss", 0),
                data.get("deducaoDependentes", 0),
                data.get("baseCalculoIRRF", 0),
                data.get("aliquotaIRRF", 0),
                data.get("parcelaDeduzirIRRF", 0),
                data.get("ir", 0),
                data.get("valorLiquido", 0),
                data.get("observacoes"),
                data.get("dataEmissao"),
            ),
        )
        conn.commit()
        return jsonify(
            row_to_dict(
                conn.execute(
                    "SELECT * FROM rpas WHERE id=?", (cur.lastrowid,)
                ).fetchone()
            )
        ), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/rpas/<int:rpa_id>", methods=["PUT"])
def update_rpa(rpa_id):
    try:
        data = request.get_json() or {}
        conn = get_db()
        conn.execute(
            "UPDATE rpas SET numero_rpa=?,nome_prestador=?,cpf_prestador=?,endereco_prestador=?,descricao_servico=?,periodo_referencia=?,carga_horaria=?,local_execucao=?,valor_bruto=?,num_dependentes=?,pensao_alimenticia=?,inss=?,iss=?,deducao_dependentes=?,base_calculo_irrf=?,aliquota_irrf=?,parcela_deduzir_irrf=?,ir=?,valor_liquido=?,observacoes=?,data_emissao=? WHERE id=?",
            (
                data.get("numeroRPA"),
                data.get("nomePrestador", ""),
                data.get("cpfPrestador"),
                data.get("enderecoPrestador"),
                data.get("descricaoServico"),
                data.get("periodoReferencia"),
                data.get("cargaHoraria"),
                data.get("localExecucao"),
                data.get("valorBruto", 0),
                data.get("numDependentes", 0),
                data.get("pensaoAlimenticia", 0),
                data.get("inss", 0),
                data.get("iss", 0),
                data.get("deducaoDependentes", 0),
                data.get("baseCalculoIRRF", 0),
                data.get("aliquotaIRRF", 0),
                data.get("parcelaDeduzirIRRF", 0),
                data.get("ir", 0),
                data.get("valorLiquido", 0),
                data.get("observacoes"),
                data.get("dataEmissao"),
                rpa_id,
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM rpas WHERE id=?", (rpa_id,)).fetchone()
        if not row:
            return jsonify({"error": "RPA não encontrado"}), 404
        return jsonify(row_to_dict(row))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/rpas/<int:rpa_id>", methods=["DELETE"])
def delete_rpa(rpa_id):
    try:
        conn = get_db()
        conn.execute("DELETE FROM rpas WHERE id=?", (rpa_id,))
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
