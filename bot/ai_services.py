import requests
import re
import json
import asyncio
from bot.config import get_config, SERVER_URL, logger


async def run_async(func, *args, **kwargs):
    return await asyncio.to_thread(func, *args, **kwargs)


def _generate_empenho(text: str) -> str:
    api_key = get_config("api_openrouter_key")
    if not api_key:
        raise ValueError("Chave OpenRouter não configurada no sistema web.")

    EMP_PROMPT = """Analise o seguinte texto extraído de um documento (fatura, contrato, ordem de serviço, ou requisição).
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
---"""
    prompt = EMP_PROMPT.replace("{TEXT}", text)
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": get_config("api_openrouter_modelo")
        or "meta-llama/llama-3.3-70b-instruct:free",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
    }
    r = requests.post(url, headers=headers, json=payload, timeout=60)
    if r.status_code != 200:
        raise ValueError(f"Erro na API OpenRouter: {r.status_code} - {r.text}")
    ans = r.json()
    content = ans.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    return content


def _call_local_ai(prompt: str) -> str:
    resp = requests.post(
        f"{SERVER_URL}/api/ia/chat",
        json={
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 1500,
        },
        timeout=60,
    )
    if not resp.ok:
        try:
            data = resp.json()
            err = data.get("error") or data
            raise ValueError(str(err))
        except Exception:
            raise ValueError(resp.text)
    data = resp.json()
    return data.get("choices", [{}])[0].get("message", {}).get("content", "")


def _extract_json(ai_response: str) -> dict:
    json_match = re.search(r"\{[\s\S]*\}", ai_response)
    if json_match:
        return json.loads(json_match.group(0))
    return json.loads(ai_response)


async def call_local_ai_with_retry(prompt: str, max_retries: int = 2) -> str:
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            return await call_local_ai(prompt)
        except Exception as e:
            last_error = e
            logger.warning(
                f"IA falhou (tentativa {attempt + 1}/{max_retries + 1}): {e}"
            )
            if attempt < max_retries:
                await asyncio.sleep(2)
    raise last_error


async def call_local_ai_json(prompt: str, max_retries: int = 2) -> dict:
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            raw = await call_local_ai(prompt)
            return _extract_json(raw)
        except json.JSONDecodeError as e:
            last_error = e
            logger.warning(
                f"JSON inválido da IA (tentativa {attempt + 1}/{max_retries + 1}): {e}"
            )
            if attempt < max_retries:
                await asyncio.sleep(1)
        except Exception as e:
            last_error = e
            logger.warning(
                f"IA falhou (tentativa {attempt + 1}/{max_retries + 1}): {e}"
            )
            if attempt < max_retries:
                await asyncio.sleep(2)
    raise last_error


# ==============================================================================
# WRAPPERS ASSÍNCRONOS
# ==============================================================================


async def generate_empenho_text(text: str) -> str:
    return await run_async(_generate_empenho, text)


async def call_local_ai(prompt: str) -> str:
    return await run_async(_call_local_ai, prompt)


def _call_local_ai_vision(prompt: str, image_base64: str) -> str:
    """Chama a IA local com imagem (base64) para análise visual."""
    resp = requests.post(
        f"{SERVER_URL}/api/ia/chat",
        json={
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}"
                            },
                        },
                    ],
                }
            ],
            "temperature": 0.1,
            "max_tokens": 2000,
        },
        timeout=90,
    )
    if not resp.ok:
        try:
            data = resp.json()
            err = data.get("error") or data
            raise ValueError(str(err))
        except Exception:
            raise ValueError(resp.text)
    data = resp.json()
    return data.get("choices", [{}])[0].get("message", {}).get("content", "")


async def call_local_ai_with_vision(
    prompt: str, image_base64: str, max_retries: int = 2
) -> dict:
    """Chama IA com imagem e retorna JSON parseado, com retry automático."""
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            raw = await run_async(_call_local_ai_vision, prompt, image_base64)
            return _extract_json(raw)
        except json.JSONDecodeError as e:
            last_error = e
            logger.warning(
                f"JSON inválido da IA visual (tentativa {attempt + 1}/{max_retries + 1}): {e}"
            )
            if attempt < max_retries:
                await asyncio.sleep(1)
        except Exception as e:
            last_error = e
            logger.warning(
                f"IA visual falhou (tentativa {attempt + 1}/{max_retries + 1}): {e}"
            )
            if attempt < max_retries:
                await asyncio.sleep(2)
    raise last_error
