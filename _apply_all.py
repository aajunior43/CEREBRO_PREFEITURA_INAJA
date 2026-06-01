# -*- coding: utf-8 -*-
"""Apply all questionnaire feature changes to the codebase."""
import os, json

BASE = r'J:\CEREBRO_PREFEITURA_INAJA-main\CEREBRO_PREFEITURA_INAJA-main'

def read(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def write(path, content):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

# ═══════════════════════════════════════════════════════════════
# 1. services/ai_prompts.py — add empenho_suggest_options + latex_suggest_options
# ═══════════════════════════════════════════════════════════════
print('1. ai_prompts.py...')
fpath = os.path.join(BASE, 'services', 'ai_prompts.py')
c = read(fpath)

marker = '    "extrato_categorizar": PromptTemplate('
insertion = '''    "empenho_suggest_options": PromptTemplate(
        system_template=(
            "Voc\u00ea \u00e9 um assistente de empenho da Prefeitura Municipal de Inaj\u00e1/PE. Hoje \u00e9 {today}. "
            "{response_style} "
            "Analise o texto base e os campos j\u00e1 preenchidos. "
            "Para os campos pendentes listados, gere de 3 a 5 op\u00e7\u00f5es de m\u00faltipla escolha "
            "contextualmente relevantes baseadas no conte\u00fado do documento. "
            "Se algum campo puder ser inferido com alta confian\u00e7a do texto (>=90%), coloque-o em 'inferidos'. "
            "Responda APENAS com JSON v\u00e1lido no formato exato:\\n"
            '{{"inferidos":{{"campo":"valor",...}},"perguntas":[\\n'
            '  {{"campo":"secretaria","pergunta":"Qual a secretaria respons\u00e1vel?","opcoes":["Secretaria de Sa\u00fade","Secretaria de Educa\u00e7\u00e3o","Secretaria de Obras"],"inferida":"Secretaria de Sa\u00fade"}},\\n'
            '  ...\\n'
            ']}}\\n'
            "Cada pergunta deve ter 3 a 5 op\u00e7\u00f5es realistas e plaus\u00edveis para administra\u00e7\u00e3o municipal. "
            "A op\u00e7\u00e3o 'inferida' (se houver) deve ser a primeira da lista. "
            "Use somente portugu\u00eas do Brasil. Se n\u00e3o houver perguntas a fazer, retorne perguntas como array vazio."
        ),
        user_template="{contexto}",
    ),
    "latex_suggest_options": PromptTemplate(
        system_template=(
            "Voc\u00ea \u00e9 um assistente de documentos oficiais em LaTeX para prefeitura municipal. Hoje \u00e9 {today}. "
            "{response_style} "
            "Analise o tipo de documento, o prompt do usu\u00e1rio e os dados j\u00e1 preenchidos. "
            "Para os campos pendentes listados, gere de 3 a 5 op\u00e7\u00f5es de m\u00faltipla escolha "
            "contextualmente relevantes para o tipo de documento solicitado. "
            "Se algum campo puder ser inferido com alta confian\u00e7a (>=90%) do prompt ou dos dados, coloque-o em 'inferidos'. "
            "Responda APENAS com JSON v\u00e1lido no formato exato:\\n"
            '{{"inferidos":{{"campo":"valor",...}},"perguntas":[\\n'
            '  {{"campo":"destinatario","pergunta":"Quem \u00e9 o destinat\u00e1rio do of\u00edcio?","opcoes":["Secretaria Estadual de Sa\u00fade","Minist\u00e9rio P\u00fAblico","Tribunal de Contas"],"inferida":"Secretaria Estadual de Sa\u00fade"}},\\n'
            '  ...\\n'
            ']}}\\n'
            "Cada pergunta deve ter 3 a 5 op\u00e7\u00f5es realistas para administra\u00e7\u00e3o p\u00fAblica municipal. "
            "A op\u00e7\u00e3o 'inferida' (se houver) deve ser a primeira da lista. "
            "Use somente portugu\u00eas do Brasil. Se n\u00e3o houver perguntas a fazer, retorne perguntas como array vazio."
        ),
        user_template=(
            "=== TIPO DE DOCUMENTO ===\\n{tipo}\\n\\n"
            "=== ESTILO ===\\n{estilo}\\n\\n"
            "=== PROMPT / CONTE\u00daDO ===\\n{prompt}\\n\\n"
            "=== DADOS J\u00c1 PREENCHIDOS ===\\n{dados_preenchidos}\\n\\n"
            "=== CAMPOS PENDENTES ===\\n{campos_pendentes}"
        ),
    ),
    ''' + marker

if marker in c:
    c = c.replace(marker, insertion, 1)
    write(fpath, c)
    print('   ai_prompts.py: +empenho_suggest_options, +latex_suggest_options')
else:
    print('   ai_prompts.py: MARKER NOT FOUND')

# ═══════════════════════════════════════════════════════════════
# 2. services/ai_tasks.py — add suggest_options to template_map + handler
# ═══════════════════════════════════════════════════════════════
print('2. ai_tasks.py...')
fpath = os.path.join(BASE, 'services', 'ai_tasks.py')
c = read(fpath)

# Add suggest_options to template_map
old_map = '''            "improve_description": "empenho_improve_description",
        }'''
new_map = '''            "improve_description": "empenho_improve_description",
            "suggest_options": "empenho_suggest_options",
        }'''
if old_map in c:
    c = c.replace(old_map, new_map, 1)
    print('   template_map: +suggest_options')

# Add _ctx_lines_for_suggestions method
old_method = '''    def _ctx_lines(self, dados: dict) -> str:'''
new_method = '''    def _ctx_lines_for_suggestions(self, dados: dict, missing_fields: list) -> str:
        """Build context for suggest_options, focusing on what's missing."""
        parts = []
        filled = {k: self._clean(dados.get(k, '')) for k in (
            'secretaria','fornecedor','tipo_despesa','finalidade','valor',
            'competencia','processo','pregao','contrato','nota_fiscal'
        )}
        filled_nonempty = {k: v for k, v in filled.items() if v}
        missing = [f for f in missing_fields if f in filled and not filled[f]]
        parts.append('=== CAMPOS J\u00c1 PREENCHIDOS ===')
        if filled_nonempty:
            for k, v in filled_nonempty.items():
                parts.append(f'{k}: {v}')
        else:
            parts.append('(nenhum campo preenchido)')
        parts.append('')
        parts.append('=== CAMPOS PENDENTES (precisam de sugest\u00f5es) ===')
        for m in missing:
            parts.append(f'- {m}')
        parts.append('')
        texto = self._clean(dados.get('texto_base',''))
        if texto:
            parts.append('=== TEXTO BASE / DOCUMENTO ===')
            parts.append(texto[:3000])
        return '\\n'.join(parts)

    def _ctx_lines(self, dados: dict) -> str:'''
if old_method in c:
    c = c.replace(old_method, new_method, 1)
    print('   +_ctx_lines_for_suggestions()')

# Add suggest_options handler in gerar_texto_empenho
old_dispatch = '''        if acao == "review_bundle":
            return self._build_review_bundle(payload)

        template_name = self.template_map.get(acao)'''
new_dispatch = '''        if acao == "review_bundle":
            return self._build_review_bundle(payload)

        if acao == "suggest_options":
            missing = payload.get('__missing_fields', [])
            if isinstance(missing, str):
                import json as _json2
                try: missing = _json2.loads(missing)
                except: missing = [m.strip() for m in missing.split(',') if m.strip()]
            ctx = self._ctx_lines_for_suggestions(payload, missing)
            return self._handle_suggest_options(ctx, acao)

        template_name = self.template_map.get(acao)'''
if old_dispatch in c:
    c = c.replace(old_dispatch, new_dispatch, 1)
    print('   suggest_options dispatch added')

# Add _handle_suggest_options method
old_handle = '''    def _build_review_bundle(self, payload: dict) -> dict:'''
new_handle = '''    def _handle_suggest_options(self, ctx: str, acao: str = "suggest_options") -> dict:
        """Call AI and parse suggest_options response."""
        service, model = self._get_service()
        template_name = self.template_map.get(acao, "empenho_suggest_options")
        messages = build_prompt(template_name, contexto=ctx)
        result = service.chat_by_task(
            task_type="empenho",
            messages=messages,
            temperature=0.25,
            max_tokens=1200,
            use_cache=False,
            metadata={"feature": "empenho_suggest_options"},
        )
        text = (result.content or '').strip()
        text = text.replace('**','').replace('*','')
        parsed = extract_json_block(text)
        if isinstance(parsed, dict):
            default = {"inferidos": {}, "perguntas": []}
            default.update(parsed)
            if not isinstance(default.get('inferidos'), dict):
                default['inferidos'] = {}
            if not isinstance(default.get('perguntas'), list):
                default['perguntas'] = []
            for i, p in enumerate(default['perguntas']):
                if not isinstance(p, dict):
                    default['perguntas'][i] = {"campo":"","pergunta":"","opcoes":[],"inferida":""}
                if not isinstance(p.get('opcoes'), list):
                    p['opcoes'] = []
            return default
        return {"inferidos": {}, "perguntas": []}

    def _build_review_bundle(self, payload: dict) -> dict:'''
if old_handle in c:
    c = c.replace(old_handle, new_handle, 1)
    print('   +_handle_suggest_options()')

write(fpath, c)

# ═══════════════════════════════════════════════════════════════
# 3. routes/empenho_assistente.py — add suggest_options to allowed actions
# ═══════════════════════════════════════════════════════════════
print('3. empenho_assistente.py...')
fpath = os.path.join(BASE, 'routes', 'empenho_assistente.py')
c = read(fpath)

old_actions = '''    if action not in {
        "extract_fields",
        "generate_description",
        "checklist",
        "improve_description",
        "review_bundle",
    }:'''
new_actions = '''    if action not in {
        "extract_fields",
        "generate_description",
        "checklist",
        "improve_description",
        "review_bundle",
        "suggest_options",
    }:'''
if old_actions in c:
    c = c.replace(old_actions, new_actions, 1)
    print('   +suggest_options in allowed actions')

# Add result handling for suggest_options
old_result = '''        if isinstance(result, dict):'''
new_result = '''        if action == "suggest_options":
            return jsonify(
                {
                    "action": action,
                    "resultado": result if isinstance(result, dict) else {},
                    "history_id": history_id,
                    "meta": meta,
                }
            )
        if isinstance(result, dict):'''
if old_result in c:
    c = c.replace(old_result, new_result, 1)
    print('   +suggest_options result handler')

write(fpath, c)

# ═══════════════════════════════════════════════════════════════
# 4. routes/latex_pdf.py — add /api/latex-pdf/sugerir-opcoes endpoint
# ═══════════════════════════════════════════════════════════════
print('4. latex_pdf.py...')
fpath = os.path.join(BASE, 'routes', 'latex_pdf.py')
c = read(fpath)

# Find the last endpoint and add new one before it
insert_after = '# ── Rota de refinamento com IA ──'
if insert_after in c:
    suggestion_route = '''# ── Rota de question\u00e1rio / sugest\u00e3o de op\u00e7\u00f5es ──
@bp.route("/api/latex-pdf/sugerir-opcoes", methods=["POST"])
@require_login
def sugerir_opcoes_latex():
    """Gera perguntas de m\u00faltipla escolha para campos faltantes antes de gerar LaTeX."""
    data = request.get_json(silent=True) or {}
    tipo = (data.get("tipo") or "documento oficial").strip()
    estilo = (data.get("estilo") or "formal").strip()
    prompt_usuario = (data.get("prompt") or "").strip()
    detalhes = (data.get("detalhes") or "").strip()
    missing_fields = data.get("missing_fields") or []

    if isinstance(missing_fields, str):
        import json as _json_local
        try:
            missing_fields = _json_local.loads(missing_fields)
        except Exception:
            missing_fields = [m.strip() for m in missing_fields.split(",") if m.strip()]

    if not prompt_usuario:
        return jsonify({"error": "Prompt \u00e9 obrigat\u00f3rio para gerar sugest\u00f5es."}), 400

    conn = get_db()
    api_key, model = _get_openrouter_config(conn)

    if not api_key:
        return jsonify({"error": "Chave do OpenRouter n\u00e3o configurada."}), 400

    try:
        svc = _build_ai_service(api_key, model)
        from services.ai_prompts import build_prompt

        # Collect already-filled data
        dados_preenchidos = []
        if tipo: dados_preenchidos.append(f"Tipo: {tipo}")
        if estilo: dados_preenchidos.append(f"Estilo: {estilo}")
        if detalhes: dados_preenchidos.append(f"Dados adicionais: {detalhes}")

        campos_pendentes = "\\n".join(f"- {m}" for m in missing_fields) if missing_fields else "(todos preenchidos)"

        messages = build_prompt(
            "latex_suggest_options",
            tipo=tipo,
            estilo=estilo,
            prompt=prompt_usuario[:4000],
            dados_preenchidos="\\n".join(dados_preenchidos) if dados_preenchidos else "(nenhum)",
            campos_pendentes=campos_pendentes,
        )

        resp = svc.chat_by_task(
            task_type="chat",
            messages=messages,
            temperature=0.25,
            max_tokens=1500,
            use_cache=False,
            metadata={"feature": "latex_suggest_options"},
        )

        text = (resp.content or "").strip()
        text = text.replace("**", "").replace("*", "")

        from services.ai_tasks import extract_json_block
        parsed = extract_json_block(text)

        if isinstance(parsed, dict):
            default = {"inferidos": {}, "perguntas": []}
            default.update(parsed)
            if not isinstance(default.get("inferidos"), dict):
                default["inferidos"] = {}
            if not isinstance(default.get("perguntas"), list):
                default["perguntas"] = []
            for i, p in enumerate(default["perguntas"]):
                if not isinstance(p, dict):
                    default["perguntas"][i] = {"campo": "", "pergunta": "", "opcoes": [], "inferida": ""}
                if not isinstance(p.get("opcoes"), list):
                    p["opcoes"] = []
            return jsonify({
                "inferidos": default["inferidos"],
                "perguntas": default["perguntas"],
                "model": resp.model,
            })

        return jsonify({"inferidos": {}, "perguntas": [], "model": resp.model})
    except Exception as err:
        return jsonify({"error": str(err)}), 500

''' + insert_after
    c = c.replace(insert_after, suggestion_route, 1)
    print('   +/api/latex-pdf/sugerir-opcoes endpoint')

write(fpath, c)

print('\\nAll backend changes applied!')
