import time
import requests
import json

api_key = "sk-WAJDuy9DGzpE7lHv3IM6Mn3jCQodeAgRxObjprhzwBokz9xn4uwk7cLfkx3T0nVg"
endpoint = "https://opencode.ai/zen/go/v1/chat/completions"
model = "deepseek-v4-flash"

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

payload = {
    "model": model,
    "messages": [{"role": "user", "content": "Olá, responda apenas com a palavra TESTE."}],
    "temperature": 0.2,
    "max_tokens": 10
}

print(f"Testando conexao com {endpoint}...")
print(f"Modelo: {model}")

start = time.perf_counter()
try:
    response = requests.post(endpoint, headers=headers, json=payload, timeout=20)
    latency = (time.perf_counter() - start) * 1000
    print(f"Status Code: {response.status_code}")
    print(f"Latency: {latency:.1f}ms")
    print(f"Response: {response.text}")
except Exception as e:
    latency = (time.perf_counter() - start) * 1000
    print(f"Falha na conexao apos {latency:.1f}ms: {e}")
