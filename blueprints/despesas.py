import json

from flask import Blueprint, request, jsonify, current_app
from database import get_db, row_to_dict
from services.openrouter_service import AIServiceError

bp = Blueprint('despesas', __name__)


@bp.route('/despesas/importacoes', methods=['GET'])
def despesas_listar_importacoes():
    conn = get_db()
    rows = conn.execute(
        "SELECT id, periodo, descricao, arquivo, total_rows, importado_em "
        "FROM despesas_importacoes ORDER BY importado_em DESC"
    ).fetchall()

    return jsonify([row_to_dict(r) for r in rows])


@bp.route('/despesas/importar', methods=['POST'])
def despesas_importar():
    try:
        d = request.get_json(force=True)
        if not d:
            return jsonify({'error': 'JSON inválido ou vazio'}), 400
        periodo  = (d.get('periodo') or '').strip()
        descricao = (d.get('descricao') or '').strip()
        arquivo  = (d.get('arquivo') or '').strip()
        linhas   = d.get('linhas', [])
        colunas  = d.get('colunas', [])

        if not periodo:
            return jsonify({'error': 'Período obrigatório'}), 400
        if not linhas:
            return jsonify({'error': 'Nenhuma linha recebida'}), 400

        from datetime import datetime as _dt_now
        now = _dt_now.now().strftime('%Y-%m-%d %H:%M:%S')

        conn = get_db()
        cur  = conn.cursor()
        cur.execute(
            "INSERT INTO despesas_importacoes (periodo, descricao, arquivo, total_rows, colunas, importado_em) "
            "VALUES (?,?,?,?,?,?)",
            (periodo, descricao, arquivo, len(linhas), json.dumps(colunas, ensure_ascii=False), now)
        )
        imp_id = cur.lastrowid

        cur.executemany(
            "INSERT INTO despesas_linhas (importacao_id, dados) VALUES (?,?)",
            [(imp_id, json.dumps(row, ensure_ascii=False)) for row in linhas]
        )

        conn.commit()
        row = conn.execute(
            "SELECT id, periodo, descricao, arquivo, total_rows, importado_em "
            "FROM despesas_importacoes WHERE id=?", (imp_id,)
        ).fetchone()

        return jsonify(row_to_dict(row)), 201
    except Exception as e:
        return jsonify({'error': 'Erro ao salvar no banco', 'detail': str(e)}), 500


@bp.route('/despesas/importacoes/<int:imp_id>', methods=['GET'])
def despesas_carregar(imp_id):
    conn = get_db()
    imp = conn.execute(
        "SELECT id, periodo, descricao, arquivo, total_rows, colunas, importado_em "
        "FROM despesas_importacoes WHERE id=?", (imp_id,)
    ).fetchone()
    if not imp:

        return jsonify({'error': 'Importação não encontrada'}), 404

    linhas_rows = conn.execute(
        "SELECT dados FROM despesas_linhas WHERE importacao_id=? ORDER BY id",
        (imp_id,)
    ).fetchall()

    imp_dict = row_to_dict(imp)
    imp_dict['colunas'] = json.loads(imp_dict['colunas'] or '[]')
    linhas = [json.loads(r['dados']) for r in linhas_rows]
    return jsonify({'importacao': imp_dict, 'linhas': linhas})


@bp.route('/despesas/importacoes/<int:imp_id>', methods=['DELETE'])
def despesas_excluir(imp_id):
    conn = get_db()
    conn.execute("DELETE FROM despesas_linhas WHERE importacao_id=?", (imp_id,))
    conn.execute("DELETE FROM despesas_importacoes WHERE id=?", (imp_id,))
    conn.commit()

    return jsonify({'ok': True})


@bp.route('/despesas/importacoes/<int:imp_id>/resumo', methods=['GET'])
def despesas_resumo(imp_id):
    conn = get_db()
    imp = conn.execute(
        "SELECT id, periodo, descricao, arquivo, total_rows, colunas, importado_em "
        "FROM despesas_importacoes WHERE id=?", (imp_id,)
    ).fetchone()
    if not imp:

        return jsonify({'error': 'Importação não encontrada'}), 404

    linhas_rows = conn.execute(
        "SELECT dados FROM despesas_linhas WHERE importacao_id=?", (imp_id,)
    ).fetchall()

    colunas = json.loads(imp['colunas'] or '[]')
    linhas = [json.loads(r['dados']) for r in linhas_rows]

    def parse_val(v):
        if not v:
            return 0.0
        s = str(v).replace('.', '').replace(',', '.').strip()
        try:
            return float(s)
        except Exception:
            return 0.0

    val_cols = [c for c in colunas if any(k in c.lower() for k in ['saldo', 'valor', 'empenhado', 'liquidado', 'pago'])]
    totais = {c: sum(parse_val(r.get(c, 0)) for r in linhas) for c in val_cols}

    def agrupar(col_key):
        grupos = {}
        for r in linhas:
            k = r.get(col_key) or '(Sem valor)'
            grupos[k] = grupos.get(k, 0) + 1
        return dict(sorted(grupos.items(), key=lambda x: -x[1])[:20])

    secretaria_col = next((c for c in colunas if 'organograma' in c.lower()), None)
    funcao_col     = next((c for c in colunas if 'função' in c.lower() or 'funcao' in c.lower()), None)
    natureza_col   = next((c for c in colunas if 'natureza' in c.lower() and 'descrição' not in c.lower() and 'descricao' not in c.lower()), None)
    recurso_col    = next((c for c in colunas if 'recurso' in c.lower() and 'descrição' not in c.lower()), None)

    saldo_col = next((c for c in colunas if 'saldo' in c.lower()), None)
    por_secretaria_valor = {}
    if secretaria_col and saldo_col:
        for r in linhas:
            k = r.get(secretaria_col) or '(Sem valor)'
            por_secretaria_valor[k] = por_secretaria_valor.get(k, 0) + parse_val(r.get(saldo_col, 0))
        por_secretaria_valor = dict(sorted(por_secretaria_valor.items(), key=lambda x: -x[1])[:15])

    return jsonify({
        'importacao': {
            'id': imp['id'],
            'periodo': imp['periodo'],
            'descricao': imp['descricao'],
            'arquivo': imp['arquivo'],
            'total_rows': imp['total_rows'],
            'importado_em': imp['importado_em'],
        },
        'totais': totais,
        'por_secretaria_contagem': agrupar(secretaria_col) if secretaria_col else {},
        'por_secretaria_valor': por_secretaria_valor,
        'por_funcao': agrupar(funcao_col) if funcao_col else {},
        'por_natureza': agrupar(natureza_col) if natureza_col else {},
        'por_recurso': agrupar(recurso_col) if recurso_col else {},
        'saldo_col': saldo_col,
        'colunas': colunas,
    })


@bp.route('/despesas/ia', methods=['POST'])
def despesas_ia():
    data = request.get_json(silent=True) or {}
    action   = (data.get('action') or '').strip()
    contexto = data.get('contexto') or {}
    pergunta = (data.get('pergunta') or '').strip()

    from blueprints.ia import _get_openrouter_config, _build_ai_service
    conn = get_db()
    api_key, model = _get_openrouter_config(conn)
    if not api_key:
        return jsonify({'error': 'Chave do OpenRouter não configurada. Acesse ADM → Configurações → Chaves de API.'}), 400

    today = __import__('datetime').date.today().strftime('%d/%m/%Y')

    def _fmt_brl(v):
        try:
            return f"R$ {float(v):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        except Exception:
            return str(v)

    def _build_ctx_text(ctx):
        lines = [
            '=== DADOS DE DOTAÇÕES ORÇAMENTÁRIAS ===',
            f'Prefeitura Municipal de Inajá – PE',
            f'Período: {ctx.get("periodo", "?")} | Total de dotações: {ctx.get("total_rows", "?")}',
        ]
        totais = ctx.get('totais') or {}
        if totais:
            lines.append('\nTotais Financeiros:')
            for k, v in totais.items():
                lines.append(f'  {k}: {_fmt_brl(v)}')
        sec = ctx.get('por_secretaria') or {}
        if sec:
            lines.append('\nSaldo por Secretaria/Órgão (top 12):')
            for k, v in list(sec.items())[:12]:
                lines.append(f'  {k}: {_fmt_brl(v)}')
        nat = ctx.get('por_natureza') or {}
        if nat:
            lines.append('\nDistribuição por Natureza de Despesa (top 10):')
            for k, v in list(nat.items())[:10]:
                lines.append(f'  {k}: {v} dotações')
        func = ctx.get('por_funcao') or {}
        if func:
            lines.append('\nDistribuição por Função (top 8):')
            for k, v in list(func.items())[:8]:
                lines.append(f'  {k}: {v} dotações')
        criticos = ctx.get('criticos') or []
        if criticos:
            limite = ctx.get('limite_critico', 1000)
            lines.append(f'\nDotações com saldo crítico (abaixo de {_fmt_brl(limite)}): {len(criticos)}')
            for it in criticos[:8]:
                lines.append(f'  Nº {it.get("num","?")} – {it.get("desc","?")} → Saldo: {it.get("saldo","?")}')
        return '\n'.join(lines)

    system_prompts = {
        'analisar': (
            f'Você é um analista financeiro especializado em orçamento público municipal. Hoje é {today}. '
            'Com base nos dados de dotações orçamentárias da Prefeitura Municipal de Inajá/PE, '
            'faça uma análise completa e objetiva. Estruture sua resposta com: '
            '1) **Resumo Executivo** (2-3 frases objetivas), '
            '2) **Pontos de Atenção** (dotações críticas, riscos, alertas), '
            '3) **Destaques por Secretaria** (maiores e menores saldos), '
            '4) **Recomendações Práticas** (3-5 ações concretas e viáveis). '
            'Use linguagem formal adequada à gestão pública. Escreva em português do Brasil.'
        ),
        'chat': (
            f'Você é um assistente especializado em orçamento público da Prefeitura Municipal de Inajá/PE. Hoje é {today}. '
            'Responda perguntas sobre os dados de dotações orçamentárias fornecidos de forma objetiva e precisa. '
            'Use os dados concretos disponíveis. Se a informação não estiver nos dados, diga claramente. '
            'Escreva em português do Brasil.'
        ),
        'anomalias': (
            f'Você é um auditor de contas públicas municipais. Hoje é {today}. '
            'Analise os dados de dotações orçamentárias e identifique anomalias, inconsistências ou situações que merecem investigação. '
            'Para cada anomalia identificada, informe: **o que é**, **por que é suspeito** e **o que verificar**. '
            'Seja específico com nomes de secretarias e valores quando possível. '
            'Numere cada anomalia. Se não houver anomalias evidentes, diga que os dados parecem regulares. '
            'Escreva em português do Brasil.'
        ),
        'relatorio': (
            f'Você é um assessor técnico de finanças públicas. Hoje é {today}. '
            'Gere um relatório formal de execução orçamentária para a Prefeitura Municipal de Inajá/PE. '
            'Estruture o relatório com: '
            '1) Identificação (período, município, secretaria responsável), '
            '2) Síntese da Execução Orçamentária (totais, percentuais), '
            '3) Análise por Secretaria/Órgão, '
            '4) Dotações em Situação Crítica, '
            '5) Considerações Finais e Recomendações. '
            'Use linguagem formal de prestação de contas. Escreva em português do Brasil.'
        ),
        'remanejamento': (
            f'Você é um especialista em gestão orçamentária municipal. Hoje é {today}. '
            'Com base nos saldos disponíveis, sugira remanejamentos orçamentários estratégicos. '
            'Para cada sugestão indique: '
            '**Dotação de origem** (com saldo excedente), '
            '**Dotação de destino** (com saldo insuficiente ou necessidade identificada), '
            '**Valor sugerido para remanejamento** (estimado), '
            '**Justificativa técnica**. '
            'Priorize pessoal, saúde e serviços essenciais. '
            'Apresente como lista numerada com no máximo 6 sugestões. '
            'Escreva em português do Brasil.'
        ),
        'prioridades': (
            f'Você é um consultor de planejamento e execução orçamentária municipal. Hoje é {today}. '
            'Com base nas dotações, identifique as prioridades orçamentárias mais urgentes para reforço, proteção ou monitoramento intensivo. '
            'Estruture a resposta com: '
            '1) **Prioridades imediatas** (itens críticos), '
            '2) **Áreas que merecem reforço** (por secretaria, programa ou ação), '
            '3) **Riscos de descontinuidade** se nada for feito, '
            '4) **Plano de ação em 30 dias** com medidas objetivas. '
            'Use linguagem executiva, prática e voltada à gestão pública. Escreva em português do Brasil.'
        ),
        'cortes': (
            f'Você é um analista de eficiência do gasto público municipal. Hoje é {today}. '
            'Com base nos dados de dotações, identifique onde pode haver espaço para contenção, postergação, revisão ou realocação de recursos sem comprometer serviços essenciais. '
            'Estruture a resposta com: '
            '1) **Possíveis áreas de corte ou contenção**, '
            '2) **Justificativa técnica de cada oportunidade**, '
            '3) **Risco operacional do corte** (baixo, médio ou alto), '
            '4) **Recomendação final** separando o que pode ser cortado, revisto ou preservado. '
            'Não sugira cortes em áreas essenciais sem alertar claramente o risco. Escreva em português do Brasil.'
        ),
    }

    if action not in system_prompts:
        return jsonify({'error': f'Ação "{action}" não reconhecida. Use: analisar, chat, anomalias, relatorio, remanejamento, prioridades, cortes.'}), 400

    ctx_text = _build_ctx_text(contexto)
    user_content = ctx_text
    if pergunta:
        user_content += f'\n\nPergunta: {pergunta}'

    messages = [
        {'role': 'system', 'content': system_prompts[action]},
        {'role': 'user',   'content': user_content},
    ]

    try:
        response = _build_ai_service(api_key, model).chat_by_task(
            task_type='auditoria_documento',
            messages=messages,
            temperature=0.5,
            max_tokens=1800,
            use_cache=False,
            metadata={'feature': 'despesas_ia', 'action': action},
        )
        return jsonify({
            'resultado': response.text,
            'action': action,
            'meta': {
                'model': response.model,
                'cached': response.cached,
                'usage': response.usage,
            }
        })
    except AIServiceError as err:
        return jsonify(err.to_response()), err.status_code
    except Exception as err:
        current_app.logger.error('despesas_ia error (action=%s): %s', action, err)
        return jsonify({'error': str(err)}), 500


@bp.route('/empenhos-csv/importar', methods=['POST'])
def empenhos_csv_importar():
    try:
        d = request.get_json(force=True)
        if not d:
            return jsonify({'error': 'JSON inválido'}), 400
        periodo  = (d.get('periodo') or '').strip()
        descricao = (d.get('descricao') or '').strip()
        arquivo  = (d.get('arquivo') or '').strip()
        linhas   = d.get('linhas', [])

        if not periodo:
            return jsonify({'error': 'Período obrigatório'}), 400
        if not linhas:
            return jsonify({'error': 'Nenhuma linha recebida'}), 400

        from datetime import datetime as _dt
        now = _dt.now().strftime('%Y-%m-%d %H:%M:%S')
        conn = get_db()
        cur  = conn.cursor()
        cur.execute(
            "INSERT INTO empenhos_importacoes (periodo, descricao, arquivo, total_rows, importado_em) VALUES (?,?,?,?,?)",
            (periodo, descricao, arquivo, len(linhas), now)
        )
        imp_id = cur.lastrowid
        cur.executemany(
            "INSERT INTO empenhos_linhas (importacao_id, dados) VALUES (?,?)",
            [(imp_id, json.dumps(row, ensure_ascii=False)) for row in linhas]
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, periodo, descricao, arquivo, total_rows, importado_em FROM empenhos_importacoes WHERE id=?", (imp_id,)
        ).fetchone()
        return jsonify(row_to_dict(row)), 201
    except Exception as e:
        return jsonify({'error': 'Erro ao salvar', 'detail': str(e)}), 500


@bp.route('/empenhos-csv/importacoes', methods=['GET'])
def empenhos_csv_listar():
    conn = get_db()
    rows = conn.execute(
        "SELECT id, periodo, descricao, arquivo, total_rows, importado_em FROM empenhos_importacoes ORDER BY importado_em DESC"
    ).fetchall()
    return jsonify([row_to_dict(r) for r in rows])


@bp.route('/empenhos-csv/importacoes/<int:imp_id>', methods=['GET'])
def empenhos_csv_carregar(imp_id):
    conn = get_db()
    imp = conn.execute(
        "SELECT id, periodo, descricao, arquivo, total_rows, importado_em FROM empenhos_importacoes WHERE id=?", (imp_id,)
    ).fetchone()
    if not imp:
        return jsonify({'error': 'Importação não encontrada'}), 404
    linhas_rows = conn.execute(
        "SELECT dados FROM empenhos_linhas WHERE importacao_id=? ORDER BY id", (imp_id,)
    ).fetchall()
    linhas = [json.loads(r['dados']) for r in linhas_rows]
    return jsonify({'importacao': row_to_dict(imp), 'linhas': linhas})


@bp.route('/empenhos-csv/importacoes/<int:imp_id>', methods=['DELETE'])
def empenhos_csv_excluir(imp_id):
    conn = get_db()
    conn.execute("DELETE FROM empenhos_linhas WHERE importacao_id=?", (imp_id,))
    conn.execute("DELETE FROM empenhos_importacoes WHERE id=?", (imp_id,))
    conn.commit()
    return jsonify({'ok': True})
