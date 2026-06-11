import requests

api_key = "sk-WAJDuy9DGzpE7lHv3IM6Mn3jCQodeAgRxObjprhzwBokz9xn4uwk7cLfkx3T0nVg"
endpoint = "https://opencode.ai/zen/go/v1/models"

headers = {
    "Authorization": f"Bearer {api_key}"
}

try:
    response = requests.get(endpoint, headers=headers, timeout=15)
    print("Status:", response.status_code)
    data = response.json()
    models = [m["id"] for m in data.get("data", [])]
    print("Modelos disponíveis:")
    for m in models:
        print(f" - {m}")
except Exception as e:
    print("Erro:", e)
