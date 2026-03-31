"""
app/routes/rpas.py — Rotas de gestão de RPA
"""

from flask import Blueprint, request, jsonify
from app.utils.db import get_db
from app.utils.helpers import row_to_dict

bp = Blueprint('rpas', __name__)


@bp.route('/rpas', methods=['GET'])
def listar_rpas():
    """Lista todos os RPAs."""
    try:
        conn = get_db()
        rows = conn.execute("SELECT * FROM rpas ORDER BY criado_em DESC").fetchall()
        return jsonify([row_to_dict(r) for r in rows])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/rpas', methods=['POST'])
def criar_rpa():
    """Cria novo RPA."""
    data = request.get_json(silent=True) or {}
    
    try:
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
            data.get('numero_rpa', ''),
            data.get('nome_prestador', ''),
            data.get('cpf_prestador', ''),
            data.get('endereco_prestador', ''),
            data.get('descricao_servico', ''),
            data.get('periodo_referencia', ''),
            data.get('carga_horaria', ''),
            data.get('local_execucao', ''),
            data.get('valor_bruto', 0),
            data.get('num_dependentes', 0),
            data.get('pensao_alimenticia', 0),
            data.get('inss', 0),
            data.get('iss', 0),
            data.get('deducao_dependentes', 0),
            data.get('base_calculo_irrf', 0),
            data.get('aliquota_irrf', 0),
            data.get('parcela_deduzir_irrf', 0),
            data.get('ir', 0),
            data.get('valor_liquido', 0),
            data.get('observacoes', ''),
            data.get('data_emissao', ''),
        ))
        
        new_id = cur.lastrowid
        conn.commit()
        
        row = conn.execute("SELECT * FROM rpas WHERE id=?", (new_id,)).fetchone()
        return jsonify(row_to_dict(row)), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/rpas/<int:rid>', methods=['PUT'])
def atualizar_rpa(rid):
    """Atualiza RPA existente."""
    data = request.get_json(silent=True) or {}
    
    try:
        conn = get_db()
        
        existing = conn.execute("SELECT * FROM rpas WHERE id=?", (rid,)).fetchone()
        if not existing:
            return jsonify({'error': 'RPA não encontrado'}), 404
        
        fields = []
        values = []
        
        for key in [
            'numero_rpa', 'nome_prestador', 'cpf_prestador', 'endereco_prestador',
            'descricao_servico', 'periodo_referencia', 'carga_horaria', 'local_execucao',
            'valor_bruto', 'num_dependentes', 'pensao_alimenticia', 'inss', 'iss',
            'deducao_dependentes', 'base_calculo_irrf', 'aliquota_irrf',
            'parcela_deduzir_irrf', 'ir', 'valor_liquido', 'observacoes', 'data_emissao'
        ]:
            if key in data:
                fields.append(f"{key}=?")
                values.append(data.get(key))
        
        if fields:
            values.append(rid)
            conn.execute(f"""
                UPDATE rpas SET {','.join(fields)}, atualizado_em=datetime('now','localtime')
                WHERE id=?
            """, values)
            conn.commit()
        
        row = conn.execute("SELECT * FROM rpas WHERE id=?", (rid,)).fetchone()
        return jsonify(row_to_dict(row))
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/rpas/<int:rid>', methods=['DELETE'])
def excluir_rpa(rid):
    """Exclui RPA."""
    try:
        conn = get_db()
        
        row = conn.execute("SELECT * FROM rpas WHERE id=?", (rid,)).fetchone()
        if not row:
            return jsonify({'error': 'RPA não encontrado'}), 404
        
        conn.execute("DELETE FROM rpas WHERE id=?", (rid,))
        conn.commit()
        
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
