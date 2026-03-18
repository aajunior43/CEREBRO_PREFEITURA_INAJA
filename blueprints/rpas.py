from flask import Blueprint, request, jsonify, current_app
from database import get_db, row_to_dict

bp = Blueprint('rpas', __name__)


@bp.route('/rpas', methods=['GET'])
def get_rpas():
    try:
        conn = get_db()
        rows = conn.execute("SELECT * FROM rpas ORDER BY criado_em DESC").fetchall()
        return jsonify([row_to_dict(r) for r in rows])
    except Exception as e:
        current_app.logger.error('GET /api/rpas: %s', e)
        return jsonify({'error': str(e)}), 500


@bp.route('/rpas', methods=['POST'])
def create_rpa():
    try:
        data = request.get_json() or {}
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO rpas (
                numero_rpa, nome_prestador, cpf_prestador, endereco_prestador,
                descricao_servico, periodo_referencia, carga_horaria, local_execucao,
                valor_bruto, num_dependentes, pensao_alimenticia, inss, iss,
                deducao_dependentes, base_calculo_irrf, aliquota_irrf,
                parcela_deduzir_irrf, ir, valor_liquido, observacoes, data_emissao
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            data.get('numeroRPA'), data.get('nomePrestador', ''), data.get('cpfPrestador'),
            data.get('enderecoPrestador'), data.get('descricaoServico'), data.get('periodoReferencia'),
            data.get('cargaHoraria'), data.get('localExecucao'),
            data.get('valorBruto', 0), data.get('numDependentes', 0),
            data.get('pensaoAlimenticia', 0), data.get('inss', 0), data.get('iss', 0),
            data.get('deducaoDependentes', 0), data.get('baseCalculoIRRF', 0),
            data.get('aliquotaIRRF', 0), data.get('parcelaDeduzirIRRF', 0),
            data.get('ir', 0), data.get('valorLiquido', 0),
            data.get('observacoes'), data.get('dataEmissao')
        ))
        conn.commit()
        row = conn.execute("SELECT * FROM rpas WHERE id=?", (cur.lastrowid,)).fetchone()
        return jsonify(row_to_dict(row)), 201
    except Exception as e:
        current_app.logger.error('POST /api/rpas: %s', e)
        return jsonify({'error': str(e)}), 500


@bp.route('/rpas/<int:rpa_id>', methods=['PUT'])
def update_rpa(rpa_id):
    try:
        data = request.get_json() or {}
        conn = get_db()
        conn.execute("""
            UPDATE rpas SET
                numero_rpa=?, nome_prestador=?, cpf_prestador=?, endereco_prestador=?,
                descricao_servico=?, periodo_referencia=?, carga_horaria=?, local_execucao=?,
                valor_bruto=?, num_dependentes=?, pensao_alimenticia=?, inss=?, iss=?,
                deducao_dependentes=?, base_calculo_irrf=?, aliquota_irrf=?,
                parcela_deduzir_irrf=?, ir=?, valor_liquido=?, observacoes=?, data_emissao=?
            WHERE id=?
        """, (
            data.get('numeroRPA'), data.get('nomePrestador', ''), data.get('cpfPrestador'),
            data.get('enderecoPrestador'), data.get('descricaoServico'), data.get('periodoReferencia'),
            data.get('cargaHoraria'), data.get('localExecucao'),
            data.get('valorBruto', 0), data.get('numDependentes', 0),
            data.get('pensaoAlimenticia', 0), data.get('inss', 0), data.get('iss', 0),
            data.get('deducaoDependentes', 0), data.get('baseCalculoIRRF', 0),
            data.get('aliquotaIRRF', 0), data.get('parcelaDeduzirIRRF', 0),
            data.get('ir', 0), data.get('valorLiquido', 0),
            data.get('observacoes'), data.get('dataEmissao'),
            rpa_id
        ))
        conn.commit()
        row = conn.execute("SELECT * FROM rpas WHERE id=?", (rpa_id,)).fetchone()
        if not row:
            return jsonify({'error': 'RPA não encontrado'}), 404
        return jsonify(row_to_dict(row))
    except Exception as e:
        current_app.logger.error('PUT /api/rpas/%s: %s', rpa_id, e)
        return jsonify({'error': str(e)}), 500


@bp.route('/rpas/<int:rpa_id>', methods=['DELETE'])
def delete_rpa(rpa_id):
    try:
        conn = get_db()
        conn.execute("DELETE FROM rpas WHERE id=?", (rpa_id,))
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        current_app.logger.error('DELETE /api/rpas/%s: %s', rpa_id, e)
        return jsonify({'error': str(e)}), 500
