"""Blueprint: RPAs"""

from flask import Blueprint, request, jsonify
from routes._shared import registrar_auditoria, require_login

bp = Blueprint("rpas", __name__)


def get_db():
    from flask import g
    return g._get_db()


def row_to_dict(row):
    return dict(row)


@bp.route("/api/rpas", methods=["GET"])
@require_login
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
@require_login
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
        new_id = cur.lastrowid
        row = conn.execute("SELECT * FROM rpas WHERE id=?", (new_id,)).fetchone()
        registrar_auditoria(conn, "rpas", new_id, "CRIAR", None, row_to_dict(row))
        conn.commit()
        return jsonify(row_to_dict(row)), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/rpas/<int:rpa_id>", methods=["PUT"])
@require_login
def update_rpa(rpa_id):
    try:
        data = request.get_json() or {}
        conn = get_db()
        anterior = conn.execute("SELECT * FROM rpas WHERE id=?", (rpa_id,)).fetchone()
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
        row = conn.execute("SELECT * FROM rpas WHERE id=?", (rpa_id,)).fetchone()
        if not row:
            return jsonify({"error": "RPA não encontrado"}), 404
        registrar_auditoria(conn, "rpas", rpa_id, "EDITAR",
                            row_to_dict(anterior) if anterior else None, row_to_dict(row))
        conn.commit()
        return jsonify(row_to_dict(row))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/rpas/<int:rpa_id>", methods=["DELETE"])
@require_login
def delete_rpa(rpa_id):
    try:
        conn = get_db()
        anterior = conn.execute("SELECT * FROM rpas WHERE id=?", (rpa_id,)).fetchone()
        conn.execute("DELETE FROM rpas WHERE id=?", (rpa_id,))
        registrar_auditoria(conn, "rpas", rpa_id, "EXCLUIR",
                            row_to_dict(anterior) if anterior else None, None)
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
