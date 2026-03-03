"""
Benchmark de Performance - Sistema de Empenhos
Executar com: python benchmark.py
"""

import time
import json
import urllib.request
import urllib.error

BASE_URL = "http://127.0.0.1:5000"

def request(method, path, data=None):
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    
    body = json.dumps(data).encode() if data else None
    if data:
        headers["Content-Type"] = "application/json"
    
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    
    try:
        start = time.perf_counter()
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read()
            elapsed = (time.perf_counter() - start) * 1000
            return elapsed, json.loads(content) if content else None
    except urllib.error.HTTPError as e:
        elapsed = (time.perf_counter() - start) * 1000
        return elapsed, {"error": e.code, "msg": e.reason}
    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000
        return elapsed, {"error": str(e)}

def run_benchmark(name, iterations, func):
    print(f"\n{'='*50}")
    print(f"TESTE: {name}")
    print(f"Iterações: {iterations}")
    print(f"{'='*50}")
    
    times = []
    errors = 0
    
    for i in range(iterations):
        elapsed, resp = func()
        times.append(elapsed)
        if isinstance(resp, dict) and "error" in resp:
            errors += 1
    
    times.sort()
    avg = sum(times) / len(times)
    p50 = times[len(times)//2]
    p95 = times[int(len(times)*0.95)]
    p99 = times[int(len(times)*0.99)]
    min_t = min(times)
    max_t = max(times)
    
    print(f"Resultados (ms):")
    print(f"  Média:  {avg:>8.2f}")
    print(f"  P50:    {p50:>8.2f}")
    print(f"  P95:    {p95:>8.2f}")
    print(f"  P99:    {p99:>8.2f}")
    print(f"  Min:    {min_t:>8.2f}")
    print(f"  Max:    {max_t:>8.2f}")
    print(f"  Erros:  {errors}/{iterations}")
    
    return {
        "name": name,
        "iterations": iterations,
        "avg_ms": avg,
        "p50_ms": p50,
        "p95_ms": p95,
        "p99_ms": p99,
        "errors": errors
    }

def main():
    print("="*60)
    print("BENCHMARK - Sistema de Empenhos Mensais")
    print("="*60)
    
    results = []
    
    # Teste 1: GET /api/credores
    results.append(run_benchmark(
        "GET /api/credores (lista credores)",
        20,
        lambda: request("GET", "/api/credores")
    ))
    
    # Teste 2: GET /api/credores com paginação
    results.append(run_benchmark(
        "GET /api/credores?limit=100 (paginado)",
        20,
        lambda: request("GET", "/api/credores?limit=100")
    ))
    
    # Teste 3: GET /api/empenhos/2026/3
    results.append(run_benchmark(
        "GET /api/empenhos/2026/3 (empenhos março)",
        20,
        lambda: request("GET", "/api/empenhos/2026/3")
    ))
    
    # Teste 4: GET /api/logs
    results.append(run_benchmark(
        "GET /api/logs (últimas ações)",
        20,
        lambda: request("GET", "/api/logs")
    ))
    
    # Teste 5: GET /api/rpas
    results.append(run_benchmark(
        "GET /api/rpas (lista RPAs)",
        20,
        lambda: request("GET", "/api/rpas")
    ))
    
    # Teste 6: GET /api/kanban
    results.append(run_benchmark(
        "GET /api/kanban (tarefas)",
        20,
        lambda: request("GET", "/api/kanban")
    ))
    
    # Resumo final
    print("\n" + "="*60)
    print("RESUMO FINAL")
    print("="*60)
    print(f"{'Teste':<40} {'Média (ms)':>10} {'P95 (ms)':>10}")
    print("-"*60)
    for r in results:
        print(f"{r['name']:<40} {r['avg_ms']:>10.2f} {r['p95_ms']:>10.2f}")
    
    total_errors = sum(r['errors'] for r in results)
    print("-"*60)
    print(f"Total de erros: {total_errors}")
    
    # Classificação
    print("\nClassificação de Performance:")
    for r in results:
        if r['p95_ms'] < 50:
            status = "EXCELENTE"
        elif r['p95_ms'] < 100:
            status = "BOM"
        elif r['p95_ms'] < 200:
            status = "REGULAR"
        else:
            status = "LENTO"
        print(f"  {status}: {r['name']}")

if __name__ == "__main__":
    main()
