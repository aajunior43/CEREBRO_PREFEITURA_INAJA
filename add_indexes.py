"""
add_indexes.py — Adiciona índices otimizados ao banco empenhos.db

Novos índices para colunas mais consultadas:
  - credores(ativo, departamento)
  - credores(ativo, nome)
  - empenhos(ano, mes, empenhado, credor_id)
  - empenhos(credor_id, ano, mes, empenhado)
  - logs(data, acao)
  - logs(credor_id, data)
  - rpas(periodo_referencia, cpf_prestador)
  - documentos_centro(categoria, criado_em)
  - kanban_tasks(status, priority)
  - protocolos(status, data_protocolo)
  - fornecimento_solicitacoes(criado_em)
  - despesas_linhas(importacao_id, dados)

Uso:
  python add_indexes.py              # Adiciona índices
  python add_indexes.py --dry-run    # Mostra índices que seriam criados
  python add_indexes.py --drop       # Remove índices adicionados por este script
"""

import argparse
import sqlite3
import sys
import os
from pathlib import Path
from datetime import datetime

# ── Configuração ─────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "empenhos.db"

# ── Definição dos novos índices ──────────────────────────────
NEW_INDEXES = [
    # Índices compostos para credores
    (
        "idx_credores_ativo_departamento",
        "CREATE INDEX IF NOT EXISTS idx_credores_ativo_departamento ON credores(ativo, departamento)"
    ),
    (
        "idx_credores_ativo_nome",
        "CREATE INDEX IF NOT EXISTS idx_credores_ativo_nome ON credores(ativo, nome)"
    ),
    (
        "idx_credores_ativo_tipo_valor",
        "CREATE INDEX IF NOT EXISTS idx_credores_ativo_tipo_valor ON credores(ativo, tipo_valor)"
    ),
    
    # Índices compostos para empenhos (consultas mais frequentes)
    (
        "idx_empenhos_ano_mes_empenhado_credor",
        "CREATE INDEX IF NOT EXISTS idx_empenhos_ano_mes_empenhado_credor ON empenhos(ano, mes, empenhado, credor_id)"
    ),
    (
        "idx_empenhos_credor_ano_mes_empenhado",
        "CREATE INDEX IF NOT EXISTS idx_empenhos_credor_ano_mes_empenhado ON empenhos(credor_id, ano, mes, empenhado)"
    ),
    (
        "idx_empenhos_timestamp",
        "CREATE INDEX IF NOT EXISTS idx_empenhos_timestamp ON empenhos(timestamp)"
    ),
    
    # Índices compostos para logs (consultas com ORDER BY data)
    (
        "idx_logs_data_acao",
        "CREATE INDEX IF NOT EXISTS idx_logs_data_acao ON logs(data, acao)"
    ),
    (
        "idx_logs_credor_data",
        "CREATE INDEX IF NOT EXISTS idx_logs_credor_data ON logs(credor_id, data)"
    ),
    
    # Índices compostos para RPAs
    (
        "idx_rpas_periodo_cpf",
        "CREATE INDEX IF NOT EXISTS idx_rpas_periodo_cpf ON rpas(periodo_referencia, cpf_prestador)"
    ),
    (
        "idx_rpas_criado_em",
        "CREATE INDEX IF NOT EXISTS idx_rpas_criado_em ON rpas(criado_em)"
    ),
    
    # Índices compostos para documentos
    (
        "idx_docs_categoria_criado",
        "CREATE INDEX IF NOT EXISTS idx_docs_categoria_criado ON documentos_centro(categoria, criado_em)"
    ),
    (
        "idx_docs_referencia_criado",
        "CREATE INDEX IF NOT EXISTS idx_docs_referencia_criado ON documentos_centro(referencia, criado_em)"
    ),
    
    # Índices para kanban tasks
    (
        "idx_kanban_status_priority",
        "CREATE INDEX IF NOT EXISTS idx_kanban_status_priority ON kanban_tasks(status, priority)"
    ),
    (
        "idx_kanban_categoria_vencimento",
        "CREATE INDEX IF NOT EXISTS idx_kanban_categoria_vencimento ON kanban_tasks(categoria, data_vencimento)"
    ),
    (
        "idx_kanban_responsavel",
        "CREATE INDEX IF NOT EXISTS idx_kanban_responsavel ON kanban_tasks(responsavel)"
    ),
    
    # Índices para protocolos
    (
        "idx_protocolos_status_data",
        "CREATE INDEX IF NOT EXISTS idx_protocolos_status_data ON protocolos(status, data_protocolo)"
    ),
    (
        "idx_protocolos_tipo_direcao",
        "CREATE INDEX IF NOT EXISTS idx_protocolos_tipo_direcao ON protocolos(tipo, direcao)"
    ),
    
    # Índices para fornecimento
    (
        "idx_fornecimento_criado_em",
        "CREATE INDEX IF NOT EXISTS idx_fornecimento_criado_em ON fornecimento_solicitacoes(criado_em)"
    ),
    (
        "idx_fornecimento_solicitante",
        "CREATE INDEX IF NOT EXISTS idx_fornecimento_solicitante ON fornecimento_solicitacoes(solicitante)"
    ),
    
    # Índices para despesas
    (
        "idx_despesas_linhas_importacao_id",
        "CREATE INDEX IF NOT EXISTS idx_despesas_linhas_importacao_id ON despesas_linhas(importacao_id, id)"
    ),
    
    # Índices para autentique
    (
        "idx_autentique_envios_status",
        "CREATE INDEX IF NOT EXISTS idx_autentique_envios_status ON autentique_envios(status)"
    ),
    (
        "idx_autentique_envios_documento",
        "CREATE INDEX IF NOT EXISTS idx_autentique_envios_documento ON autentique_envios(documento_centro_id)"
    ),
    (
        "idx_autentique_contatos_phone",
        "CREATE INDEX IF NOT EXISTS idx_autentique_contatos_phone ON autentique_contatos(phone)"
    ),
    
    # Índices para empenho assistente
    (
        "idx_empenho_hist_action_created",
        "CREATE INDEX IF NOT EXISTS idx_empenho_hist_action_created ON empenho_assistente_historico(action, criado_em)"
    ),
    
    # Índices para classificador
    (
        "idx_classificador_item",
        "CREATE INDEX IF NOT EXISTS idx_classificador_item ON classificador_despesa_historico(item)"
    ),
    (
        "idx_classificador_codigo",
        "CREATE INDEX IF NOT EXISTS idx_classificador_codigo ON classificador_despesa_historico(codigo_completo)"
    ),
    (
        "idx_classificador_created",
        "CREATE INDEX IF NOT EXISTS idx_classificador_created ON classificador_despesa_historico(criado_em)"
    ),
    
    # Índices para configurações
    (
        "idx_configuracoes_chave",
        "CREATE INDEX IF NOT EXISTS idx_configuracoes_chave ON configuracoes(chave)"
    ),
    
    # Índices para fornecimento dados
    (
        "idx_fornecimento_dados_tipo",
        "CREATE INDEX IF NOT EXISTS idx_fornecimento_dados_tipo ON fornecimento_dados(tipo)"
    ),
    
    # Índices para empenhos importações
    (
        "idx_empenhos_importacoes_periodo_importado",
        "CREATE INDEX IF NOT EXISTS idx_empenhos_importacoes_periodo_importado ON empenhos_importacoes(periodo, importado_em)"
    ),
    
    # Índices para despesas importações
    (
        "idx_despesas_importacoes_periodo_importado",
        "CREATE INDEX IF NOT EXISTS idx_despesas_importacoes_periodo_importado ON despesas_importacoes(periodo, importado_em)"
    ),
    
    # Índices para protocolo anexos
    (
        "idx_protocolo_anexos_protocolo",
        "CREATE INDEX IF NOT EXISTS idx_protocolo_anexos_protocolo ON protocolo_anexos(protocolo_id)"
    ),
]

# Lista de índices que este script adiciona (para remoção)
ADDED_INDEX_NAMES = [idx[0] for idx in NEW_INDEXES]


def get_db():
    """Conecta ao banco de dados."""
    if not DB_PATH.exists():
        print(f"ERRO: Banco de dados não encontrado: {DB_PATH}")
        sys.exit(1)
    
    conn = sqlite3.connect(str(DB_PATH), timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn


def get_existing_indexes(conn):
    """Retorna lista de índices existentes."""
    rows = conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL"
    ).fetchall()
    return {row["name"]: row["sql"] for row in rows}


def analyze_index_usage(conn):
    """Analisa uso de índices existentes."""
    print("\n📊 Análise de Uso de Índices:")
    print("-" * 60)
    
    # Tenta obter estatísticas de uso de índices
    try:
        # SQLite não tem estatísticas nativas de uso de índices
        # Mas podemos verificar tamanho das tabelas
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        
        print(f"\nTabelas no banco:")
        for table in tables:
            count = conn.execute(f"SELECT COUNT(*) FROM {table['name']}").fetchone()[0]
            print(f"  {table['name']:<40} {count:>8} registros")
    except Exception as e:
        print(f"  Erro ao analisar tabelas: {e}")


def add_indexes(conn, dry_run=False):
    """Adiciona novos índices ao banco."""
    existing = get_existing_indexes(conn)
    
    print("\n" + "=" * 60)
    print("  Adicionar Índices Otimizados")
    print("=" * 60)
    
    if dry_run:
        print("\n🔍 MODO DRY-RUN — Nenhuma alteração será feita\n")
    
    created = 0
    skipped = 0
    errors = 0
    
    for index_name, index_sql in NEW_INDEXES:
        if index_name in existing:
            skipped += 1
            print(f"  ⏭️  {index_name} (já existe)")
            continue
        
        if dry_run:
            print(f"  ➕ {index_name} (seria criado)")
            created += 1
            continue
        
        try:
            conn.execute(index_sql)
            conn.commit()
            created += 1
            print(f"  ✅ {index_name}")
        except Exception as e:
            errors += 1
            print(f"  ❌ {index_name}: {e}")
    
    print("\n" + "-" * 60)
    print(f"  Resumo:")
    print(f"    Criados: {created}")
    print(f"    Ignorados (já existem): {skipped}")
    print(f"    Erros: {errors}")
    print(f"    Total verificado: {len(NEW_INDEXES)}")
    print("=" * 60)
    
    return created, skipped, errors


def drop_indexes(conn):
    """Remove índices adicionados por este script."""
    existing = get_existing_indexes(conn)
    
    print("\n" + "=" * 60)
    print("  Remover Índices Adicionados por Este Script")
    print("=" * 60)
    
    removed = 0
    not_found = 0
    
    for index_name in ADDED_INDEX_NAMES:
        if index_name in existing:
            try:
                conn.execute(f"DROP INDEX IF EXISTS {index_name}")
                conn.commit()
                removed += 1
                print(f"  🗑️  {index_name}")
            except Exception as e:
                print(f"  ❌ {index_name}: {e}")
        else:
            not_found += 1
            print(f"  ⏭️  {index_name} (não encontrado)")
    
    print("\n" + "-" * 60)
    print(f"  Resumo:")
    print(f"    Removidos: {removed}")
    print(f"    Não encontrados: {not_found}")
    print(f"    Total verificado: {len(ADDED_INDEX_NAMES)}")
    print("=" * 60)
    
    return removed, not_found


def verify_indexes(conn):
    """Verifica todos os índices no banco."""
    existing = get_existing_indexes(conn)
    
    print("\n" + "=" * 60)
    print("  Índices no Banco de Dados")
    print("=" * 60)
    
    # Agrupar por tabela
    by_table = {}
    for name, sql in existing.items():
        # Extrair nome da tabela do SQL
        parts = sql.split("ON ")
        if len(parts) > 1:
            table_part = parts[1].split("(")[0].strip()
            if table_part not in by_table:
                by_table[table_part] = []
            by_table[table_part].append((name, sql))
    
    for table in sorted(by_table.keys()):
        print(f"\n  📁 {table}:")
        for name, sql in sorted(by_table[table]):
            print(f"    • {name}")
    
    print(f"\n{'-' * 60}")
    print(f"  Total de índices: {len(existing)}")
    print("=" * 60)


def benchmark_query(conn, query, params=(), iterations=10):
    """Faz benchmark de uma consulta."""
    import time
    
    # Warm up
    conn.execute(query, params).fetchall()
    
    # Benchmark
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        conn.execute(query, params).fetchall()
        elapsed = (time.perf_counter() - start) * 1000  # ms
        times.append(elapsed)
    
    avg_ms = sum(times) / len(times)
    min_ms = min(times)
    max_ms = max(times)
    
    return avg_ms, min_ms, max_ms


def run_benchmarks(conn):
    """Executa benchmarks de consultas comuns."""
    print("\n" + "=" * 60)
    print("  Benchmark de Consultas Comuns")
    print("=" * 60)
    
    benchmarks = [
        (
            "Listar credores ativos por departamento",
            "SELECT * FROM credores WHERE ativo=1 ORDER BY departamento, nome"
        ),
        (
            "Listar empenhos do mês",
            "SELECT * FROM empenhos WHERE ano=2026 AND mes=4 AND empenhado=1"
        ),
        (
            "Histórico de empenhos de credor",
            "SELECT * FROM empenhos WHERE credor_id=? ORDER BY ano DESC, mes DESC",
            (1,)
        ),
        (
            "Últimos logs",
            "SELECT * FROM logs ORDER BY data DESC LIMIT 100"
        ),
        (
            "Logs por ação",
            "SELECT * FROM logs WHERE acao=? ORDER BY data DESC LIMIT 50",
            ("CRIAR",)
        ),
        (
            "Documentos por categoria",
            "SELECT * FROM documentos_centro WHERE categoria=? ORDER BY criado_em DESC",
            ("Contratos",)
        ),
        (
            "Tarefas Kanban por status",
            "SELECT * FROM kanban_tasks WHERE status=? ORDER BY priority, data_vencimento",
            ("todo",)
        ),
    ]
    
    print(f"\n{'Consulta':<50} {'Média':>8} {'Mín':>8} {'Máx':>8}")
    print("-" * 60)
    
    for benchmark in benchmarks:
        name = benchmark[0]
        query = benchmark[1]
        params = benchmark[2] if len(benchmark) > 2 else ()
        
        try:
            avg, min_t, max_t = benchmark_query(conn, query, params)
            print(f"{name:<50} {avg:>6.2f}ms {min_t:>6.2f}ms {max_t:>6.2f}ms")
        except Exception as e:
            print(f"{name:<50} {'ERRO':>8} ({str(e)[:20]})")
    
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Adiciona índices otimizados ao empenhos.db")
    parser.add_argument("--dry-run", action="store_true", help="Mostra índices que seriam criados")
    parser.add_argument("--drop", action="store_true", help="Remove índices adicionados por este script")
    parser.add_argument("--verify", action="store_true", help="Verifica todos os índices")
    parser.add_argument("--benchmark", action="store_true", help="Executa benchmarks de consultas")
    parser.add_argument("--all", action="store_true", help="Adiciona índices e executa benchmark")
    args = parser.parse_args()
    
    print(f"\n{'=' * 60}")
    print(f"  Gerenciador de Índices — empenhos.db")
    print(f"  Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"{'=' * 60}")
    
    conn = get_db()
    
    try:
        if args.drop:
            drop_indexes(conn)
        elif args.verify:
            verify_indexes(conn)
        elif args.benchmark:
            analyze_index_usage(conn)
            run_benchmarks(conn)
        elif args.all:
            print("\n📌 Adicionando índices...")
            created, skipped, errors = add_indexes(conn)
            print("\n📊 Executando benchmarks...")
            run_benchmarks(conn)
        else:
            add_indexes(conn, dry_run=args.dry_run)
    
    finally:
        conn.close()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
