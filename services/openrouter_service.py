import json
import urllib.error
import urllib.request
from typing import Any


def listar_modelos(api_key: str) -> list[dict[str, Any]]:
    req = urllib.request.Request(
        'https://openrouter.ai/api/v1/models',
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        },
    )
    with urllib.request.urlopen(req, timeout=15) as response:
        data = json.loads(response.read().decode())
    return data.get('data', [])


def chat_completion(api_key: str, model: str, messages: list[dict[str, Any]], max_tokens: int, temperature: float, referer: str, title: str) -> dict[str, Any]:
    payload = json.dumps({
        'model': model,
        'messages': messages,
        'max_tokens': max_tokens,
        'temperature': temperature,
    }).encode('utf-8')
    req = urllib.request.Request(
        'https://openrouter.ai/api/v1/chat/completions',
        data=payload,
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            'HTTP-Referer': referer,
            'X-Title': title,
        },
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=60) as response:
        return json.loads(response.read().decode())


def parse_http_error(error: urllib.error.HTTPError) -> dict[str, Any]:
    body = error.read().decode('utf-8', errors='replace')
    try:
        return json.loads(body)
    except Exception:
        return {'message': body}
