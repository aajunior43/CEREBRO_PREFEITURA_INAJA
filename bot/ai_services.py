import requests
import asyncio
from bot.config import get_config, SERVER_URL, logger

async def run_async(func, *args, **kwargs):
    return await asyncio.to_thread(func, *args, **kwargs)

def _generate_empenho(text: str) -> str:
    api_key = get_config('api_openrouter_key')
    if not api_key:
        raise ValueError("Chave OpenRouter não configurada no sistema web.")
    
    EMP_PROMPT = '''Analise o seguinte texto extraído de um documento (fatura, contrato, ordem de serviço, ou requisição).
O seu objetivo é gerar o texto da "Descrição" para uma Nota de Empenho (NE) do setor público.

Regras Estritas:
1. A saída deve estar EXCLUSIVAMENTE em CAIXA ALTA (letras maiúsculas).
2. O texto deve começar OBRIGATORIAMENTE com a frase exata: "PELA DESPESA EMPENHADA REFERENTE A".
3. Identifique o objeto da despesa de forma sucinta mas completa.
4. Se houver número de processo, pregão, contrato ou nota fiscal visível, inclua-os no texto.
5. Não use markdown, apenas texto puro.

Texto do documento:
---
{TEXT}
---'''
    prompt = EMP_PROMPT.replace('{TEXT}', text)
    url = 'https://openrouter.ai/api/v1/chat/completions'
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    payload = {
        'model': get_config('api_openrouter_modelo') or 'meta-llama/llama-3.3-70b-instruct:free',
        'messages': [{'role': 'user', 'content': prompt}],
        'temperature': 0.2
    }
    r = requests.post(url, headers=headers, json=payload, timeout=60)
    if r.status_code != 200:
        raise ValueError(f"Erro na API OpenRouter: {r.status_code} - {r.text}")
    ans = r.json()
    content = ans.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
    return content

def _call_local_ai(prompt: str) -> str:
    resp = requests.post(
        f'{SERVER_URL}/api/ia/chat',
        json={'messages': [{'role': 'user', 'content': prompt}], 'temperature': 0.1, 'max_tokens': 1500},
        timeout=60
    )
    if not resp.ok:
        try:
            data = resp.json()
            err = data.get('error') or data
            raise ValueError(str(err))
        except Exception:
            raise ValueError(resp.text)
    data = resp.json()
    return data.get('choices', [{}])[0].get('message', {}).get('content', '')

# ==============================================================================
# WRAPPERS ASSÍNCRONOS
# ==============================================================================

async def generate_empenho_text(text: str) -> str:
    return await run_async(_generate_empenho, text)

async def call_local_ai(prompt: str) -> str:
    return await run_async(_call_local_ai, prompt)
