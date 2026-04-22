from datetime import date
from string import Formatter


_DEFAULT_STYLE = {
    "idioma": "pt-BR",
    "tom": "formal, objetivo e técnico",
    "formato": "responda sem markdown, salvo quando o formato solicitado for JSON",
    "fidelidade": "não invente dados ausentes e sinalize pendências quando necessário",
}


class PromptTemplate:
    def __init__(self, system_template: str, user_template: str):
        self.system_template = system_template
        self.user_template = user_template

    def render(self, **variables):
        context = dict(variables)
        context.setdefault("today", date.today().strftime("%d/%m/%Y"))
        context.setdefault("response_style", render_response_style())
        return [
            {"role": "system", "content": self.system_template.format(**context)},
            {
                "role": "user",
                "content": self.user_template.format(**_safe_variables(context)),
            },
        ]


PROMPT_TEMPLATES = {
    "empenho_extract_fields": PromptTemplate(
        system_template=(
            "Você é um assistente de empenho da Prefeitura Municipal de Inajá/PE. Hoje é {today}. "
            "Extraia os campos mais prováveis do documento. {response_style} "
            "Responda apenas com JSON válido contendo as chaves: "
            '"secretaria", "fornecedor", "tipo_despesa", "finalidade", "valor", "competencia", '
            '"processo", "pregao", "contrato", "nota_fiscal", "observacoes", "pendencias". '
            '"pendencias" deve ser um array de strings objetivas. Se algum dado não existir, retorne string vazia.'
        ),
        user_template="{contexto}",
    ),
    "empenho_generate_description": PromptTemplate(
        system_template=(
            "Você gera descrições objetivas para notas de empenho municipais. Hoje é {today}. "
            "{response_style} Use exclusivamente caixa alta. "
            'Inicie exatamente com "PELA DESPESA EMPENHADA REFERENTE A". '
            "Informe o objeto da despesa, secretaria e referências (processo, pregão, contrato, nota fiscal) quando houver. "
            "Seja direto: O QUÊ + QUEM + QUANDO. Evite adjetivos e linguagem comercial."
        ),
        user_template="{contexto}",
    ),
    "empenho_checklist": PromptTemplate(
        system_template=(
            "Você é um conferente de empenhos públicos municipais. Hoje é {today}. "
            "{response_style} Responda apenas com JSON válido no formato "
            '{"resumo":"...","itens":["..."],"pendencias":["..."],"prioridade":"..."} '
            "com no máximo 8 itens curtos, apontando campos ausentes, riscos documentais e dados a confirmar."
        ),
        user_template="{contexto}",
    ),
    "empenho_improve_description": PromptTemplate(
        system_template=(
            "Você revisa descrições de notas de empenho para torná-las mais claras e objetivas. Hoje é {today}. "
            "{response_style} Use somente caixa alta e inicie com "
            '"PELA DESPESA EMPENHADA REFERENTE A". '
            "Mantenha fidelidade aos dados. Elimine redundâncias e linguagem comercial."
        ),
        user_template="{contexto}",
    ),
    "extrato_categorizar": PromptTemplate(
        system_template=(
            "Você analisa extratos bancários e documentos financeiros para classificação automática. "
            "{response_style} Responda apenas com JSON válido no formato "
            '{{"categoria":"...","subcategoria":"...","confianca":0.0,"justificativa":"..."}}.'
        ),
        user_template="Classifique o texto abaixo:\n\n{texto}",
    ),
    "documento_analisar": PromptTemplate(
        system_template=(
            "Você é um auditor documental da administração pública municipal. "
            "{response_style} Analise consistência, riscos, ausência de dados e próximos passos. "
            'Responda em JSON válido com as chaves "resumo", "riscos", "pendencias", "recomendacoes".'
        ),
        user_template="Documento para análise:\n\n{texto}",
    ),
    "arquivo_renomear": PromptTemplate(
        system_template=(
            "Você ajuda a renomear arquivos administrativos com nomes padronizados. "
            "{response_style} Responda apenas com JSON válido no formato "
            '{{"nome_sugerido":"...","categoria":"...","justificativa":"..."}}.'
        ),
        user_template="Nome atual: {nome_arquivo}\n\nConteúdo extraído:\n{texto}",
    ),
    "classificador_despesa": PromptTemplate(
        system_template=(
            "Você é um Auditor de Controle Interno e Contador Especialista em Contabilidade Pública Municipal, "
            "com foco exclusivo nas normas do Tribunal de Contas do Estado do Paraná (TCE-PR) e no Manual de "
            "Contabilidade Aplicada ao Setor Público (MCASP) vigente (11ª edição/2025 em diante). "
            "Hoje é {today}. A Prefeitura Municipal de Inajá-PR deseja classificar a despesa corretamente. "
            "{response_style} "
            "Siga ESTE PROCESSO em ordem:\n"
            "1ª ETAPA — Leia os resultados da busca web (seção CONTEXTO WEB). "
            "2ª ETAPA — PENSE ANTES DE RESPONDER. Analise o item considerando: "
            "O que é exatamente? É material, serviço, obra ou equipamento? "
            "Quem fornece? Pessoa física ou jurídica? "
            "Qual a natureza? Consumo imediato, uso contínuo, investimento permanente? "
            "Quais classificações são possíveis? Qual é a mais adequada e por quê? "
            "3ª ETAPA — Identifique a categoria do item usando as regras abaixo. "
            "4ª ETAPA — Cruze busca web + análise + regras e defina a classificação mais precisa. "
            "\n=== REGRAS DE CLASSIFICAÇÃO (use estas regras, não invente) ===\n"
            "MATERIAL DE CONSUMO (3.3.90.30 — Custeio, Elemento 30): "
            "papel, toner, cartucho de tinta, material de escritório, material de limpeza, material elétrico, "
            "material hidráulico, material de construção (pequenos reparos), material esportivo, material médico-hospitalar, "
            "material odontológico, material de laboratório, gêneros alimentícios, combustíveis, lubrificantes, "
            "gás, água, materiais descartáveis, uniformes, EPIs, peças de reposição para veículos e equipamentos "
            "(manutenção corrente, sem aumento de vida útil).\n"
            "SERVIÇOS — PESSOA FÍSICA (3.3.90.36 — Custeio, Elemento 36): "
            "diárias, passagens, indenizações, transporte de servidor, locação de mão de obra temporária (PF), "
            "hospedagem e alimentação de servidor em viagem oficial.\n"
            "SERVIÇOS — PESSOA JURÍDICA (3.3.90.39 — Custeio, Elemento 39): "
            "contabilidade, auditoria, consultoria, assessoria jurídica, certificação digital (A1, A3, e-CPF, e-CNPJ), "
            "licenças de software, assinaturas de sistemas, SaaS, manutenção de equipamentos e veículos, "
            "limpeza, segurança, vigilância, capina e roçagem, poda de árvores, coleta de lixo, "
            "manutenção de ar-condicionado, manutenção de elevadores, energia elétrica, água e esgoto, "
            "telecomunicações, internet, telefonia, correios, frete, transporte de materiais, "
            "serviços gráficos, publicação de editais, serviços de TI, hospedagem de sites, "
            "serviços bancários, taxas de administração, comissões, serviços de saúde terceirizados, "
            "serviços educacionais terceirizados, alimentação escolar terceirizada, "
            "serviços de engenharia (projetos, fiscalização, laudos), "
            "locação de imóveis, locação de veículos, locação de máquinas e equipamentos, "
            "serviços de publicidade e propaganda, serviços de comunicação visual.\n"
            "OBRAS E INSTALAÇÕES (4.4.90.51 — Investimento, Elemento 51): "
            "construção de prédios, construção de estradas, construção de calçadas, reforma que amplia área ou "
            "aumenta vida útil do imóvel, pavimentação, drenagem, instalação de rede de água/esgoto, "
            "instalação de rede elétrica, reforma estrutural de prédios públicos.\n"
            "EQUIPAMENTOS E MATERIAL PERMANENTE (4.4.90.52 — Investimento, Elemento 52): "
            "veículos (carros, motos, caminhões, ambulâncias, ônibus, vans), "
            "computadores, notebooks, tablets, impressoras, monitores, "
            "mobiliário (mesas, cadeiras, armários, estantes), "
            "equipamentos médicos e odontológicos, equipamentos de laboratório, "
            "equipamentos de comunicação (rádios, antenas), "
            "máquinas e equipamentos em geral (tratores, motosserras, roçadeiras), "
            "equipamentos de climatização (ar-condicionado split ou central — aquisição do equipamento), "
            "ferramentas de longa duração.\n"
            "\n=== FORMATO DE RESPOSTA ===\n"
            "Responda APENAS com JSON válido no seguinte formato exato: "
            '{{"item_analisado":"...","analise":"...","codigo_completo":"...","grupo":"...","modalidade":"...","elemento":"...",'
            '"subelemento_codigo":"...","subelemento_nome":"...","justificativa":"...","ponto_atencao":"...",'
            '"confianca":0.0,"alternativas":[]}} '
            "IMPORTANTE — significado exato de cada campo:\n"
            '- "analise": Sua análise detalhada. O que é o item? Quem fornece? Qual a natureza? Quais classificações são possíveis? Por que escolheu esta?\n'
            '- "grupo": GND por extenso. Ex: "Investimento", "Custeio", "Inversões Financeiras"\n'
            '- "modalidade": Sempre "Aplicação Direta" (não use códigos numéricos)\n'
            '- "elemento": APENAS o número de 2 dígitos. Ex: "30", "36", "39", "51", "52"\n'
            '- "subelemento_codigo": O código completo com pontos. Ex: "3.3.90.30", "4.4.90.52"\n'
            '- "subelemento_nome": Nome do subelemento por extenso. Ex: "Material de Consumo", "Equipamentos e Material Permanente"\n'
            '- "codigo_completo": Igual ao subelemento_codigo. Ex: "3.3.90.30", "4.4.90.52"\n'
            "onde confianca é de 0.0 a 1.0 e ponto_atencao é string vazia se não houver exceção. "
            'O campo "alternativas" deve ser um array vazio [] quando confianca >= 0.70. '
            'Quando confianca < 0.70, preencha "alternativas" com 2 ou 3 objetos no formato: '
            '{{"codigo_completo":"...","subelemento_nome":"...","justificativa":"..."}} '
            "representando as classificações concorrentes mais prováveis, em ordem decrescente de probabilidade."
        ),
        user_template="CONTEXTO WEB (TAVILY):\n{web_context}\n\n---\n\nItem a classificar: {item}",
    ),
}


def render_response_style(style: dict | None = None) -> str:
    merged = dict(_DEFAULT_STYLE)
    if style:
        merged.update({k: v for k, v in style.items() if v})
    return " ".join(
        str(value).strip() for value in merged.values() if str(value).strip()
    )


def build_prompt(template_name: str, **variables):
    template = PROMPT_TEMPLATES[template_name]
    return template.render(**variables)


def limit_text(text: str, max_chars: int) -> str:
    raw = (text or "").strip()
    if len(raw) <= max_chars:
        return raw
    return raw[:max_chars].rstrip()


def _safe_variables(variables: dict) -> dict:
    safe = dict(variables)
    for _, field_name, _, _ in Formatter().parse(safe.get("contexto", "")):
        if field_name and field_name not in safe:
            safe[field_name] = ""
    return {key: "" if value is None else value for key, value in safe.items()}
