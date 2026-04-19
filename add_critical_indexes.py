"""
add_critical_indexes.py - Adiciona indices compostos criticos para performance

Uso:
    python add_critical_indexes.py              # Adiciona indices
    python add_critical_indexes.py --verify     # Verifica indices existentes
    python add_critical_indexes.py --benchmark  # Testa performance

Prefeitura Municipal de Inaja
"""

import sqlite3
import time
from pathlib import Path
import sys

DB_PATH = Path(__file__).parent / "empenhos.db"

# Indices compostos otimizados para queries mais frequentes
CRITICAL_INDEXES = [
    {
        "name": "idx_credores_filtros_principais",
        "sql": """CREATE INDEX IF NOT EXISTS idx_credores_filtros_principais
                  ON credores(ativo, departamento, tipo_valor, nome)""",
        "description": "Otimiza filtros combinados na tela principal"
    },
    {
        "name": "idx_credores_busca_paginada",
        "sql": """CREATE INDEX IF NOT EXISTS idx_credores_busca_paginada
                  ON credores(ativo, nome, departamento, id)""",
        "description": "Acelera busca por nome com paginacao"
    },
    {
        "name": "idx_empenhos_historico_credor",
        "sql": """CREATE INDEX IF NOT EXISTS idx_empenhos_historico_credor
                  ON empenhos(credor_id, ano DESC, mes DESC, empenhado)""",
        "description": "Otimiza consulta de historico de empenhos"
    },
    {
        "name": "idx_logs_recentes",
        "sql": """CREATE INDEX IF NOT EXISTS idx_logs_recentes
                  ON logs(data DESC, acao, credor_id)""",
        "description": "Acelera listagem de logs recentes"
    },
    {
        "name": "idx_rpas_periodo_completo",
        "sql": """CREATE INDEX IF NOT EXISTS idx_rpas_periodo_completo
                  ON rpas(periodo_referencia DESC, cpf_prestador, criado_em DESC)""",
        "description": "Otimiza consultas de RPAs por periodo"
    },
    {
        "name": "idx_docs_categoria_data",
        "sql": """CREATE INDEX IF NOT EXISTS idx_docs_categoria_data
                  ON documentos_centro(categoria, criado_em DESC, referencia)""",
        "description": "Acelera busca de documentos por categoria"
    },
    {
        "name": "idx_kanban_ativas",
        "sql": """CREATE INDEX IF NOT EXISTS idx_kanban_ativas
                  ON kanban_tasks(status, priority, data_vencimento, categoria)""",
        "description": "Otimiza visualizacao do Kanban"
    },
    {
        "name": "idx_protocolos_status_data",
        "sql": """CREATE INDEX IF NOT EXISTS idx_protocolos_status_data
                  ON protocolos(status, data_protocolo DESC, tipo)""",
        "description": "Acelera filtros de protocolos"
    },
]


def print_header(text):
    """Imprime cabecalho formatado."""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)


def add_indexes():
    """Adiciona indices criticos ao banco."""
    print_header("Adicionando Indices Criticos")

    if not DB_PATH.exists():
        print(f"[ERRO] Banco de dados nao encontrado: {DB_PATH}")
        return False

    print(f"[INFO] Conectando ao banco: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    print(f"\nAdicionando {len(CRITICAL_INDEXES)} indices...\n")

    success_count = 0
    for i, index in enumerate(CRITICAL_INDEXES, 1):
        try:
            start = time.perf_counter()
            cur.execute(index["sql"])
            elapsed_ms = (time.perf_counter() - start) * 1000

            print(f"[OK] [{i}/{len(CRITICAL_INDEXES)}] {index['name']}")
            print(f"     {index['description']}")
            print(f"     Tempo: {elapsed_ms:.1f}ms\n")
            success_count += 1
        except Exception as e:
            print(f"[ERRO] [{i}/{len(CRITICAL_INDEXES)}] {index['name']}")
            print(f"       Erro: {e}\n")

    conn.commit()
    conn.close()

    print_header("Resumo")
    print(f"Indices adicionados: {success_count}/{len(CRITICAL_INDEXES)}")

    return success_count == len(CRITICAL_INDEXES)


def verify_indexes():
    """Verifica indices existentes no banco."""
    print_header("Verificando Indices Existentes")

    if not DB_PATH.exists():
        print(f"[ERRO] Banco de dados nao encontrado: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Buscar todos os indices
    indexes = cur.execute("""
        SELECT name, tbl_name, sql
        FROM sqlite_master
        WHERE type='index' AND sql IS NOT NULL
        ORDER BY tbl_name, name
    """).fetchall()

    # Agrupar por tabela
    tables = {}
    for idx_name, tbl_name, sql in indexes:
        if tbl_name not in tables:
            tables[tbl_name] = []
        tables[tbl_name].append((idx_name, sql))

    # Exibir
    print(f"\nTotal de indices: {len(indexes)}\n")

    for tbl_name in sorted(tables.keys()):
        print(f"\n{tbl_name}:")
        for idx_name, sql in tables[tbl_name]:
            # Verificar se e um indice critico
            is_critical = any(idx['name'] == idx_name for idx in CRITICAL_INDEXES)
            marker = "[*]" if is_critical else "   "
            print(f"  {marker} {idx_name}")

    # Verificar indices criticos faltantes
    existing_names = {idx[0] for idx in indexes}
    critical_names = {idx['name'] for idx in CRITICAL_INDEXES}
    missing = critical_names - existing_names

    if missing:
        print("\n" + "!" * 70)
        print("Indices criticos FALTANDO:")
        for name in missing:
            print(f"  - {name}")
        print("\nExecute: python add_critical_indexes.py")
    else:
        print("\n[OK] Todos os indices criticos estao presentes!")

    conn.close()


def benchmark_queries():
    """Testa performance de queries comuns."""
    print_header("Benchmark de Queries")

    if not DB_PATH.exists():
        print(f"[ERRO] Banco de dados nao encontrado: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Queries de teste
    queries = [
        {
            "name": "Listar credores ativos por departamento",
            "sql": "SELECT * FROM credores WHERE ativo=1 AND departamento='SAUDE' ORDER BY nome LIMIT 50"
        },
        {
            "name": "Buscar credores por nome",
            "sql": "SELECT * FROM credores WHERE ativo=1 AND nome LIKE '%FORNECEDOR%' LIMIT 50"
        },
        {
            "name": "Historico de empenhos de um credor",
            "sql": "SELECT * FROM empenhos WHERE credor_id=1 ORDER BY ano DESC, mes DESC LIMIT 24"
        },
        {
            "name": "Ultimos 100 logs",
            "sql": "SELECT * FROM logs ORDER BY data DESC LIMIT 100"
        },
        {
            "name": "RPAs do ultimo mes",
            "sql": "SELECT * FROM rpas WHERE periodo_referencia >= '2026-03' ORDER BY criado_em DESC LIMIT 50"
        },
    ]

    print(f"\nExecutando {len(queries)} queries de teste...\n")

    results = []
    for i, query in enumerate(queries, 1):
        try:
            # Executar 3 vezes e pegar a media
            times = []
            for _ in range(3):
                start = time.perf_counter()
                cur.execute(query["sql"])
                rows = cur.fetchall()
                elapsed_ms = (time.perf_counter() - start) * 1000
                times.append(elapsed_ms)

            avg_time = sum(times) / len(times)
            results.append((query["name"], avg_time, len(rows)))

            print(f"[{i}/{len(queries)}] {query['name']}")
            print(f"    Tempo medio: {avg_time:.2f}ms ({len(rows)} resultados)")

            # Analise de performance
            if avg_time < 10:
                print("    Performance: [***] Excelente")
            elif avg_time < 50:
                print("    Performance: [** ] Boa")
            elif avg_time < 100:
                print("    Performance: [*  ] Aceitavel")
            else:
                print("    Performance: [   ] Precisa otimizacao")
            print()
        except Exception as e:
            print(f"[ERRO] [{i}/{len(queries)}] {query['name']}")
            print(f"       Erro: {e}\n")

    # Resumo
    print_header("Resumo de Performance")
    if results:
        avg_total = sum(r[1] for r in results) / len(results)
        print(f"\nTempo medio geral: {avg_total:.2f}ms")

        print("\nQueries mais lentas:")
        sorted_results = sorted(results, key=lambda x: x[1], reverse=True)[:3]
        for name, time_ms, rows in sorted_results:
            print(f"  - {name}: {time_ms:.2f}ms")

    conn.close()


def main():
    """Funcao principal."""
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()

        if arg in ['--verify', '-v']:
            verify_indexes()
        elif arg in ['--benchmark', '-b']:
            benchmark_queries()
        elif arg in ['--help', '-h']:
            print(__doc__)
        else:
            print(f"Argumento desconhecido: {arg}")
            print("Use --help para ver opcoes disponiveis")
    else:
        # Adicionar indices por padrao
        success = add_indexes()

        if success:
            print("\n" + "=" * 70)
            print("[OK] Indices adicionados com sucesso!")
            print("\nProximos passos:")
            print("  1. Reinicie o servidor: python server.py")
            print("  2. Teste a performance: python add_critical_indexes.py --benchmark")
            print("=" * 70)
        else:
            print("\n[ERRO] Alguns indices falharam. Verifique os erros acima.")
            sys.exit(1)


if __name__ == "__main__":
    main()
