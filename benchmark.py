"""
Benchmark de Performance - Sistema de Empenhos
Executar com: python benchmark.py
"""

import time
import json
import urllib.request
import urllib.error
import threading
import random
import string

BASE_URL = "http://127.0.0.1:5000"

def do_request(method, path, data=None):
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    body = json.dumps(data).encode() if data else None
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

def stats(times):
    times = sorted(times)
    n = len(times)
    return {
        "avg": sum(times)/n,
        "min": times[0],
        "p50": times[n//2],
        "p95": times[int(n*0.95)],
        "p99": times[int(n*0.99)] if n >= 100 else times[-1],
        "max": times[-1],
    }

def run_sequential(name, iterations, func):
    times, errors = [], 0
    for _ in range(iterations):
        elapsed, resp = func()
        times.append(elapsed)
        if isinstance(resp, dict) and "error" in resp:
            errors += 1
    s = stats(times)
    print(f"\n[SEQUENCIAL] {name}  ({iterations}x)")
    print(f"  Avg={s['avg']:.1f}ms  P50={s['p50']:.1f}ms  P95={s['p95']:.1f}ms  Min={s['min']:.1f}ms  Max={s['max']:.1f}ms  Erros={errors}/{iterations}")
    return {**s, "name": name, "errors": errors, "mode": "seq"}

def run_concurrent(name, workers, requests_per_worker, func):
    all_times = []
    all_errors = []
    lock = threading.Lock()

    def worker():
        local_t, local_e = [], 0
        for _ in range(requests_per_worker):
            elapsed, resp = func()
            local_t.append(elapsed)
            if isinstance(resp, dict) and "error" in resp:
                local_e += 1
        with lock:
            all_times.extend(local_t)
            all_errors.append(local_e)

    threads = [threading.Thread(target=worker) for _ in range(workers)]
    wall_start = time.perf_counter()
    for t in threads: t.start()
    for t in threads: t.join()
    wall_ms = (time.perf_counter() - wall_start) * 1000

    total = workers * requests_per_worker
    errors = sum(all_errors)
    s = stats(all_times)
    rps = total / (wall_ms / 1000)
    print(f"\n[CONCORRENTE {workers} threads] {name}  ({total} reqs total)")
    print(f"  Avg={s['avg']:.1f}ms  P50={s['p50']:.1f}ms  P95={s['p95']:.1f}ms  Max={s['max']:.1f}ms  Erros={errors}/{total}  Throughput={rps:.0f} req/s")
    return {**s, "name": name, "errors": errors, "mode": f"conc{workers}", "rps": rps}

def classify(p95):
    if p95 < 30:   return "✅ EXCELENTE"
    if p95 < 80:   return "🟢 BOM"
    if p95 < 200:  return "🟡 REGULAR"
    return "🔴 LENTO"

def main():
    year = time.localtime().tm_year
    month = time.localtime().tm_mon

    print("=" * 65)
    print("  BENCHMARK — Sistema de Empenhos Mensais")
    print(f"  Servidor: {BASE_URL}")
    print("=" * 65)

    # Verificar servidor
    try:
        do_request("GET", "/api/ping")
        print("  Servidor: OK\n")
    except Exception as e:
        print(f"  ERRO: Servidor não responde ({e})")
        return

    results = []

    # ── Leituras sequenciais ──────────────────────────────────
    print("\n━━━ LEITURAS SEQUENCIAIS ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    results.append(run_sequential("GET /api/credores",           30, lambda: do_request("GET", "/api/credores")))
    results.append(run_sequential("GET /api/empenhos/ano/mes",   30, lambda: do_request("GET", f"/api/empenhos/{year}/{month}")))
    results.append(run_sequential("GET /api/logs",               30, lambda: do_request("GET", "/api/logs")))
    results.append(run_sequential("GET /api/rpas",               20, lambda: do_request("GET", "/api/rpas")))
    results.append(run_sequential("GET /api/kanban",             20, lambda: do_request("GET", "/api/kanban")))
    results.append(run_sequential("GET /api/fornecimento/dados", 20, lambda: do_request("GET", "/api/fornecimento/dados")))

    # ── Escritas sequenciais ──────────────────────────────────
    print("\n━━━ ESCRITAS (INSERT + DELETE) ━━━━━━━━━━━━━━━━━━━━━━━━━")
    created_ids = []

    def write_credor():
        name = ''.join(random.choices(string.ascii_uppercase, k=8))
        elapsed, resp = do_request("POST", "/api/credores", {
            "nome": f"TESTE_{name}", "valor": 100.0,
            "descricao": "benchmark", "departamento": "TESTE"
        })
        if resp and "id" in resp:
            created_ids.append(resp["id"])
        return elapsed, resp

    results.append(run_sequential("POST /api/credores (insert)", 15, write_credor))

    def delete_credor():
        if created_ids:
            cid = created_ids.pop()
            return do_request("DELETE", f"/api/credores/{cid}")
        return do_request("GET", "/api/ping")

    results.append(run_sequential("DELETE /api/credores/:id",    15, delete_credor))

    # ── Leituras concorrentes ─────────────────────────────────
    print("\n━━━ LEITURAS CONCORRENTES (múltiplos usuários) ━━━━━━━━━")
    results.append(run_concurrent("GET /api/credores",         workers=5,  requests_per_worker=10, func=lambda: do_request("GET", "/api/credores")))
    results.append(run_concurrent("GET /api/empenhos/ano/mes", workers=5,  requests_per_worker=10, func=lambda: do_request("GET", f"/api/empenhos/{year}/{month}")))
    results.append(run_concurrent("GET /api/credores",         workers=10, requests_per_worker=5,  func=lambda: do_request("GET", "/api/credores")))

    # ── Resumo ────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print(f"{'RESUMO GERAL':<40} {'Avg':>7} {'P95':>7} {'Status'}")
    print("-" * 65)
    for r in results:
        mode = f"[{r['mode']}]"
        print(f"{mode:<10} {r['name']:<30} {r['avg']:>6.1f}ms {r['p95']:>6.1f}ms  {classify(r['p95'])}")

    print("=" * 65)
    total_errors = sum(r['errors'] for r in results)
    all_p95 = [r['p95'] for r in results]
    overall = sum(all_p95) / len(all_p95)
    print(f"  P95 médio geral: {overall:.1f}ms  |  Total de erros: {total_errors}  |  {classify(overall)}")
    print("=" * 65)

if __name__ == "__main__":
    main()
