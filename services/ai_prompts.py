from datetime import date
from string import Formatter


_DEFAULT_STYLE = {
    'idioma': 'pt-BR',
    'tom': 'formal, objetivo e técnico',
    'formato': 'responda sem markdown, salvo quando o formato solicitado for JSON',
    'fidelidade': 'não invente dados ausentes e sinalize pendências quando necessário',
}


class PromptTemplate:
    def __init__(self, system_template: str, user_template: str):
        self.system_template = system_template
        self.user_template = user_template

    def render(self, **variables):
        context = dict(variables)
        context.setdefault('today', date.today().strftime('%d/%m/%Y'))
        context.setdefault('response_style', render_response_style())
        return [
            {'role': 'system', 'content': self.system_template.format(**context)},
            {'role': 'user', 'content': self.user_template.format(**_safe_variables(context))},
        ]


PROMPT_TEMPLATES = {
    'empenho_extract_fields': PromptTemplate(
        system_template=(
            'Você é um assistente de empenho da Prefeitura Municipal de Inajá/PE. Hoje é {today}. '
            'Extraia os campos mais prováveis do documento. {response_style} '
            'Responda apenas com JSON válido contendo as chaves: '
            '"secretaria", "fornecedor", "tipo_despesa", "finalidade", "valor", "competencia", '
            '"processo", "pregao", "contrato", "nota_fiscal", "observacoes", "pendencias". '
            '"pendencias" deve ser um array de strings objetivas. Se algum dado não existir, retorne string vazia.'
        ),
        user_template='{contexto}',
    ),
    'empenho_generate_description': PromptTemplate(
        system_template=(
            'Você é um redator técnico especializado em notas de empenho municipais. Hoje é {today}. '
            '{response_style} Escreva a descrição de uma nota de empenho usando exclusivamente caixa alta. '
            'O texto deve começar exatamente com "PELA DESPESA EMPENHADA REFERENTE A". '
            'Inclua secretaria, objeto, finalidade, período e referências como processo, pregão, contrato ou nota fiscal quando existirem.'
        ),
        user_template='{contexto}',
    ),
    'empenho_checklist': PromptTemplate(
        system_template=(
            'Você é um conferente de empenhos públicos municipais. Hoje é {today}. '
            '{response_style} Gere um checklist objetivo com no máximo 8 itens curtos, apontando campos ausentes, riscos documentais e dados a confirmar.'
        ),
        user_template='{contexto}',
    ),
    'empenho_improve_description': PromptTemplate(
        system_template=(
            'Você é um revisor técnico de notas de empenho municipais. Hoje é {today}. '
            '{response_style} Reescreva a descrição para ficar mais clara, formal e completa, mantendo fidelidade aos dados informados. '
            'Use somente caixa alta e inicie exatamente com "PELA DESPESA EMPENHADA REFERENTE A".'
        ),
        user_template='{contexto}',
    ),
    'extrato_categorizar': PromptTemplate(
        system_template=(
            'Você analisa extratos bancários e documentos financeiros para classificação automática. '
            '{response_style} Responda apenas com JSON válido no formato '
            '{{"categoria":"...","subcategoria":"...","confianca":0.0,"justificativa":"..."}}.'
        ),
        user_template='Classifique o texto abaixo:\n\n{texto}',
    ),
    'documento_analisar': PromptTemplate(
        system_template=(
            'Você é um auditor documental da administração pública municipal. '
            '{response_style} Analise consistência, riscos, ausência de dados e próximos passos. '
            'Responda em JSON válido com as chaves "resumo", "riscos", "pendencias", "recomendacoes".'
        ),
        user_template='Documento para análise:\n\n{texto}',
    ),
    'arquivo_renomear': PromptTemplate(
        system_template=(
            'Você ajuda a renomear arquivos administrativos com nomes padronizados. '
            '{response_style} Responda apenas com JSON válido no formato '
            '{{"nome_sugerido":"...","categoria":"...","justificativa":"..."}}.'
        ),
        user_template='Nome atual: {nome_arquivo}\n\nConteúdo extraído:\n{texto}',
    ),
}


def render_response_style(style: dict | None = None) -> str:
    merged = dict(_DEFAULT_STYLE)
    if style:
        merged.update({k: v for k, v in style.items() if v})
    return ' '.join(str(value).strip() for value in merged.values() if str(value).strip())


def build_prompt(template_name: str, **variables):
    template = PROMPT_TEMPLATES[template_name]
    return template.render(**variables)


def limit_text(text: str, max_chars: int) -> str:
    raw = (text or '').strip()
    if len(raw) <= max_chars:
        return raw
    return raw[:max_chars].rstrip()


def _safe_variables(variables: dict) -> dict:
    safe = dict(variables)
    for _, field_name, _, _ in Formatter().parse(safe.get('contexto', '')):
        if field_name and field_name not in safe:
            safe[field_name] = ''
    return {key: '' if value is None else value for key, value in safe.items()}
