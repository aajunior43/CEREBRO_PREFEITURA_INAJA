import time
import requests
import json
from datetime import date

api_key = "sk-WAJDuy9DGzpE7lHv3IM6Mn3jCQodeAgRxObjprhzwBokz9xn4uwk7cLfkx3T0nVg"
endpoint = "https://opencode.ai/zen/go/v1/chat/completions"

models = ["deepseek-v4-flash", "qwen3.6-plus", "qwen3.5-plus"]

# Simple mock context
contexto = """
=== CONTEXTO DO EMPENHO ===
Secretaria/Setor: Secretaria de Saúde
Fornecedor/Credor: Farmácia Inajá Ltda
Tipo da despesa: Material de Consumo
Finalidade/necessidade: Aquisição de medicamentos básicos para postos de saúde.
Valor: R$ 12.500,00
Competencia/periodo: 06/2026
Processo: 045/2026
Pregao/licitacao: Pregão Eletrônico 012/2026
Contrato: 089/2026
Nota fiscal/OS/referencia: NF 5543
"""

system_prompt = (
    "Você é um redator técnico especializado em notas de empenho municipais. Hoje é 11/06/2026. "
    "Idioma: pt-BR. Tom: formal, objetivo e técnico. Responda sem markdown. "
    "Escreva a descrição de uma nota de empenho usando exclusivamente caixa alta. "
    "O texto deve começar exatamente com 'PELA DESPESA EMPENHADA REFERENTE A'. "
    "Inclua secretaria, objeto, finalidade, período e referências como processo, pregão, contrato ou nota fiscal quando existirem."
)

for model in models:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": contexto}
        ],
        "temperature": 0.3,
        "max_tokens": 500
    }
    
    print(f"\n--- Testando {model} ---")
    start = time.perf_counter()
    try:
        response = requests.post(endpoint, headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, json=payload, timeout=45)
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
                print(f"Reasoning length: {len(reasoning)} chars")
                print(f"Content length: {len(content)} chars")
                print(f"Content snippet: {content[:150]}")
            else:
                print("No choices returned.")
        else:
            print("Response:", response.text)
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        print(f"Falha apos {latency:.1f}ms: {e}")
