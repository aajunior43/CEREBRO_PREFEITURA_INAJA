# -*- coding: utf-8 -*-
import os

base = r'J:\CEREBRO_PREFEITURA_INAJA-main\CEREBRO_PREFEITURA_INAJA-main'

# ── services/ai_prompts.py — add 2 new templates ──
fpath = os.path.join(base, 'services', 'ai_prompts.py')
with open(fpath, 'r', encoding='utf-8') as f:
    content = f.read()

# Find insertion point after empenho_improve_description
marker = '        user_template="{contexto}",\n    ),\n    "extrato_categorizar":'
new_templates = '''        user_template="{contexto}",
    ),
    "empenho_suggest_options": PromptTemplate(
        system_template=(
            "Você é um assistente de empenho da Prefeitura Municipal de Inajá/PE. Hoje é {today}. "
            "{response_style} "
            "Analise o texto base e os campos já preenchidos. "
            "Para os campos pendentes listados, gere de 3 a 5 opções de múltipla escolha "
            "contextualmente relevantes baseadas no conteúdo do documento. "
            "Se algum campo puder ser inferido com alta confiança do texto (>=90%), coloque-o em 'inferidos'. "
            "Responda APENAS com JSON válido no formato exato:\\n"
            '{{"inferidos":{{"campo":"valor",...}},"perguntas":[\\n'
            '  {{"campo":"secretaria","pergunta":"Qual a secretaria responsável?","opcoes":["Secretaria de Saúde","Secretaria de Educação","Secretaria de Obras"],"inferida":"Secretaria de Saúde"}},\\n'
            '  ...\\n'
            ']}}\\n'
            "Cada pergunta deve ter 3 a 5 opções realistas e plausíveis para administração municipal. "
            "A opção 'inferida' (se houver) deve ser a primeira da lista. "
            "Use somente português do Brasil. Se não houver perguntas a fazer, retorne perguntas como array vazio."
        ),
        user_template="{contexto}",
    ),
    "latex_suggest_options": PromptTemplate(
        system_template=(
            "Você é um assistente de documentos oficiais em LaTeX para prefeitura municipal. Hoje é {today}. "
            "{response_style} "
            "Analise o tipo de documento, o prompt do usuário e os dados já preenchidos. "
            "Para os campos pendentes listados, gere de 3 a 5 opções de múltipla escolha "
            "contextualmente relevantes para o tipo de documento solicitado. "
            "Se algum campo puder ser inferido com alta confiança (>=90%) do prompt ou dos dados, coloque-o em 'inferidos'. "
            "Responda APENAS com JSON válido no formato exato:\\n"
            '{{"inferidos":{{"campo":"valor",...}},"perguntas":[\\n'
            '  {{"campo":"destinatario","pergunta":"Quem é o destinatário do ofício?","opcoes":["Secretaria Estadual de Saúde","Ministério Público","Tribunal de Contas"],"inferida":"Secretaria Estadual de Saúde"}},\\n'
            '  ...\\n'
            ']}}\\n'
            "Cada pergunta deve ter 3 a 5 opções realistas para administração pública municipal. "
            "A opção 'inferida' (se houver) deve ser a primeira da lista. "
            "Use somente português do Brasil. Se não houver perguntas a fazer, retorne perguntas como array vazio."
        ),
        user_template=(
            "=== TIPO DE DOCUMENTO ===\\n{tipo}\\n\\n"
            "=== ESTILO ===\\n{estilo}\\n\\n"
            "=== PROMPT / CONTEÚDO ===\\n{prompt}\\n\\n"
            "=== DADOS JÁ PREENCHIDOS ===\\n{dados_preenchidos}\\n\\n"
            "=== CAMPOS PENDENTES ===\\n{campos_pendentes}"
        ),
    ),
    "extrato_categorizar":'''

if marker in content:
    content = content.replace(marker, new_templates, 1)
    with open(fpath, 'w', encoding='utf-8') as f:
        f.write(content)
    print('ai_prompts.py: OK')
else:
    print('ai_prompts.py: MARKER NOT FOUND')
    # Try alternative marker
    print('Looking for alternatives...')
    for i, line in enumerate(content.split('\n')):
        if 'extrato_categorizar' in line:
            print(f'  Found at line {i+1}: {line.strip()[:80]}')
