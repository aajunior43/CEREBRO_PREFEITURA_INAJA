import time
import requests
import json

api_key = "sk-WAJDuy9DGzpE7lHv3IM6Mn3jCQodeAgRxObjprhzwBokz9xn4uwk7cLfkx3T0nVg"
endpoint = "https://opencode.ai/zen/go/v1/chat/completions"

# Let's test a few promising models
test_models = ["deepseek-v4-flash", "qwen3.6-plus", "kimi-k2.5", "minimax-m2.7"]

system_prompt = "Você é um assistente rápido. Escreva uma descrição curta de empenho."
user_prompt = "Secretaria: Saúde. Objeto: Compra de dipirona."

for model in test_models:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.2,
        "max_tokens": 1000
    }
    
    print(f"\n--- Testando {model} ---")
    start = time.perf_counter()
    try:
        response = requests.post(endpoint, headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, json=payload, timeout=30)
        latency = (time.perf_counter() - start) * 1000
        print(f"Status: {response.status_code}")
        print(f"Latency: {latency:.1f}ms")
        if response.status_code == 200:
            data = response.json()
            choices = data.get("choices") or []
            if choices:
                msg = choices[0].get("message", {})
                content = msg.get("content") or ""
                reasoning = msg.get("reasoning_content") or ""
                print(f"Reasoning length: {len(reasoning)}")
                print(f"Content length: {len(content)}")
                print(f"Content: {content}")
            else:
                print("No choices.")
        else:
            print("Error:", response.text)
    except Exception as e:
        print(f"Erro no modelo {model}: {e}")
