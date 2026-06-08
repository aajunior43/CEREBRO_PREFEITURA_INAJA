import time
import sys
import os

# Add root folder to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from server import create_app

def benchmark():
    app, _, init_db, migrate_db = create_app()
    client = app.test_client()
    
    # Authenticate client
    with client.session_transaction() as sess:
        sess["usuario_id"] = 1
        sess["usuario_nome"] = "Benchmark Admin"
        sess["usuario_nivel"] = "admin"

    print("==================================================")
    print("      BENCHMARK DE PERFORMANCE DOS ENDPOINTS      ")
    print("==================================================")

    # 1. Test latency of GET /api/documentos
    start = time.perf_counter()
    res = client.get("/api/documentos")
    elapsed_docs = (time.perf_counter() - start) * 1000
    print(f"GET /api/documentos:        {elapsed_docs:.2f} ms (Status: {res.status_code})")

    # 2. Test latency of GET /api/latex-pdf/status
    start = time.perf_counter()
    res = client.get("/api/latex-pdf/status")
    elapsed_latex = (time.perf_counter() - start) * 1000
    print(f"GET /api/latex-pdf/status:  {elapsed_latex:.2f} ms (Status: {res.status_code})")

    # 3. Test latency of GET /api/prazos
    start = time.perf_counter()
    res = client.get("/api/prazos")
    elapsed_prazos = (time.perf_counter() - start) * 1000
    print(f"GET /api/prazos:            {elapsed_prazos:.2f} ms (Status: {res.status_code})")

    # 4. Test latency of GET /api/fornecimento/dados
    start = time.perf_counter()
    res = client.get("/api/fornecimento/dados")
    elapsed_forn = (time.perf_counter() - start) * 1000
    print(f"GET /api/fornecimento/dados: {elapsed_forn:.2f} ms (Status: {res.status_code})")

    print("==================================================")

if __name__ == '__main__':
    benchmark()
