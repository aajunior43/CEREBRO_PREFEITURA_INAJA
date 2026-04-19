"""
apply_constraints.py — Aplica constraints de integridade no banco existente

Como o banco já está em produção com dados, este script:
1. Verifica se constraints existem
2. Adiciona constraints ausentes via ALTER TABLE
3. Valida dados existentes antes de adicionar constraints
4. Reporta violações encontradas

Uso:
  python apply_constraints.py              # Aplica todas as constraints
  python apply_constraints.py --dry-run    # Mostra o que seria feito
  python apply_constraints.py --verify     # Verifica constraints existentes
"""

import argparse
import sqlite3
import sys
from pathlib import Path
from datetime import datetime

# ── Configuração ─────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "empenhos.db"


def get_db():
    """Conecta ao banco de dados."""
    if not DB_PATH.exists():
        print(f"ERRO: Banco de dados não encontrado: {DB_PATH}")
        sys.exit(1)
    
    conn = sqlite3.connect(str(DB_PATH), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def get_table_info(conn, table_name):
    """Retorna informações de colunas de uma tabela."""
    return conn.execute(f"PRAGMA table_info({table_name})").fetchall()


def get_table_constraints(conn, table_name):
    """Retorna constraints existentes de uma tabela."""
    # SQLite não tem uma visão direta de constraints
    # Precisamos verificar o SQL da tabela
    sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    ).fetchone()
    return sql["sql"] if sql else ""


def check_constraint_exists(conn, table_name, constraint_name):
    """Verifica se constraint existe."""
    sql = get_table_constraints(conn, table_name)
    return constraint_name in sql if sql else False


def validate_data(conn, table_name, constraint_sql):
    """Valida dados existentes antes de adicionar constraint."""
    violations = []
    
    # Extrair tipo de constraint do SQL
    if 'CHECK' in constraint_sql.upper():
        # Extrair condição CHECK
        import re
        match = re.search(r"CHECK\s*\((.+?)\)", constraint_sql, re.IGNORECASE)
        if match:
            condition = match.group(1)
            # Verificar violações
            try:
                query = f"SELECT COUNT(*) as cnt FROM {table_name} WHERE NOT ({condition})"
                result = conn.execute(query).fetchone()
                if result and result["cnt"] > 0:
                    violations.append(f"{result['cnt']} registro(s) violam: {condition}")
            except Exception as e:
                violations.append(f"Erro ao validar: {e}")
    
    return violations


def apply_constraints(conn, dry_run=False):
    """Aplica constraints de integridade no banco existente."""
    
    print("\n" + "=" * 70)
    print("  Aplicar Constraints de Integridade — empenhos.db")
    print("=" * 70)
    
    if dry_run:
        print("\n🔍 MODO DRY-RUN — Nenhuma alteração será feita\n")
    
    applied = 0
    skipped = 0
    violations = 0
    
    # ── Constraints para credores ────────────────────────────
    constraints = [
        # (tabela, constraint_name, SQL para adicionar, descrição)
        (
            "credores",
            "ck_credores_valor_positivo",
            "ALTER TABLE credores ADD CONSTRAINT ck_credores_valor_positivo CHECK (valor >= 0)",
            "Valor deve ser >= 0"
        ),
        (
            "credores",
            "ck_credores_ativo_boolean",
            "ALTER TABLE credores ADD CONSTRAINT ck_credores_ativo_boolean CHECK (ativo IN (0, 1))",
            "Ativo deve ser 0 ou 1"
        ),
        (
            "credores",
            "ck_credores_tipo_valor_valido",
            "ALTER TABLE credores ADD CONSTRAINT ck_credores_tipo_valor_valido CHECK (tipo_valor IN ('FIXO', 'VARIAVEL', 'VARIÁVEL', 'MENSAL', 'QUINZENAL'))",
            "Tipo de valor inválido"
        ),
    ]
    
    # ── Constraints para empenhos ───────────────────────────
    constraints += [
        (
            "empenhos",
            "ck_empenhos_ano_valido",
            "ALTER TABLE empenhos ADD CONSTRAINT ck_empenhos_ano_valido CHECK (ano >= 2000 AND ano <= 2100)",
            "Ano deve estar entre 2000 e 2100"
        ),
        (
            "empenhos",
            "ck_empenhos_mes_valido",
            "ALTER TABLE empenhos ADD CONSTRAINT ck_empenhos_mes_valido CHECK (mes >= 1 AND mes <= 12)",
            "Mês deve estar entre 1 e 12"
        ),
        (
            "empenhos",
            "ck_empenhos_empenhado_boolean",
            "ALTER TABLE empenhos ADD CONSTRAINT ck_empenhos_empenhado_boolean CHECK (empenhado IN (0, 1))",
            "Empenhado deve ser 0 ou 1"
        ),
    ]
    
    # ── Constraints para logs ───────────────────────────────
    constraints += [
        (
            "logs",
            "ck_logs_acao_valida",
            "ALTER TABLE logs ADD CONSTRAINT ck_logs_acao_valida CHECK (acao IN ('CRIAR', 'EDITAR', 'EXCLUIR', 'RESTAURAR', 'TELEGRAM_ENVIO'))",
            "Ação deve ser válida"
        ),
    ]
    
    # ── Constraints para rpas ──────────────────────────────
    constraints += [
        (
            "rpas",
            "ck_rpas_valor_bruto_positivo",
            "ALTER TABLE rpas ADD CONSTRAINT ck_rpas_valor_bruto_positivo CHECK (valor_bruto >= 0)",
            "Valor bruto deve ser >= 0"
        ),
        (
            "rpas",
            "ck_rpas_valor_liquido_positivo",
            "ALTER TABLE rpas ADD CONSTRAINT ck_rpas_valor_liquido_positivo CHECK (valor_liquido >= 0)",
            "Valor líquido deve ser >= 0"
        ),
    ]
    
    # ── Constraints para kanban_tasks ──────────────────────
    constraints += [
        (
            "kanban_tasks",
            "ck_kanban_status_valido",
            "ALTER TABLE kanban_tasks ADD CONSTRAINT ck_kanban_status_valido CHECK (status IN ('todo', 'doing', 'done', 'cancelled'))",
            "Status deve ser válido"
        ),
        (
            "kanban_tasks",
            "ck_kanban_priority_valida",
            "ALTER TABLE kanban_tasks ADD CONSTRAINT ck_kanban_priority_valida CHECK (priority IN ('low', 'medium', 'high', 'urgent'))",
            "Prioridade deve ser válida"
        ),
    ]
    
    # ── Constraints para prazos ────────────────────────────
    constraints += [
        (
            "prazos",
            "ck_prazos_resolvido_boolean",
            "ALTER TABLE prazos ADD CONSTRAINT ck_prazos_resolvido_boolean CHECK (resolvido IN (0, 1))",
            "Resolvido deve ser 0 ou 1"
        ),
    ]
    
    # ── Constraints para protocolos ────────────────────────
    constraints += [
        (
            "protocolos",
            "ck_protocolos_direcao_valida",
            "ALTER TABLE protocolos ADD CONSTRAINT ck_protocolos_direcao_valida CHECK (direcao IN ('recebido', 'enviado'))",
            "Direção deve ser válida"
        ),
        (
            "protocolos",
            "ck_protocolos_status_valido",
            "ALTER TABLE protocolos ADD CONSTRAINT ck_protocolos_status_valido CHECK (status IN ('recebido', 'em_andamento', 'respondido', 'arquivado'))",
            "Status deve ser válido"
        ),
    ]
    
    # ── Aplicar cada constraint ────────────────────────────
    for table, constraint_name, sql, description in constraints:
        # Verificar se constraint já existe
        if check_constraint_exists(conn, table, constraint_name):
            skipped += 1
            print(f"  ⏭️  {constraint_name} (já existe)")
            continue
        
        # Validar dados antes de adicionar
        viols = validate_data(conn, table, sql)
        if viols:
            violations += 1
            print(f"  ⚠️  {constraint_name}: {description}")
            for v in viols:
                print(f"       ↳ {v}")
            continue
        
        # Aplicar constraint
        if dry_run:
            print(f"  ➕ {constraint_name}: {description} (seria adicionada)")
            applied += 1
            continue
        
        try:
            conn.execute(sql)
            conn.commit()
            applied += 1
            print(f"  ✅ {constraint_name}: {description}")
        except Exception as e:
            print(f"  ❌ {constraint_name}: {e}")
            violations += 1
    
    # ── Resumo ─────────────────────────────────────────────
    print("\n" + "-" * 70)
    print(f"  Resumo:")
    print(f"    Aplicadas: {applied}")
    print(f"    Ignoradas (já existem): {skipped}")
    print(f"    Violações/Erros: {violations}")
    print(f"    Total verificadas: {len(constraints)}")
    print("=" * 70)
    
    return applied, skipped, violations


def verify_constraints(conn):
    """Verifica todas as constraints existentes."""
    
    print("\n" + "=" * 70)
    print("  Verificar Constraints de Integridade")
    print("=" * 70)
    
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    
    total_constraints = 0
    total_tables = 0
    
    for table in tables:
        table_name = table["name"]
        sql = get_table_constraints(conn, table_name)
        
        # Contar constraints
        constraints_count = sql.upper().count("CHECK") + sql.upper().count("UNIQUE") + sql.upper().count("FOREIGN KEY")
        
        if constraints_count > 0:
            total_tables += 1
            total_constraints += constraints_count
            print(f"\n  📁 {table_name} ({constraints_count} constraints):")
            
            # Extrair constraints do SQL
            import re
            checks = re.findall(r"CHECK\s*\((.+?)\)", sql, re.IGNORECASE)
            uniques = re.findall(r"UNIQUE\s*\((.+?)\)", sql, re.IGNORECASE)
            
            for c in checks:
                print(f"    • CHECK: {c[:60]}...")
            for u in uniques:
                print(f"    • UNIQUE: {u}")
    
    print(f"\n{'-' * 70}")
    print(f"  Total de tabelas com constraints: {total_tables}")
    print(f"  Total de constraints: {total_constraints}")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Aplica constraints de integridade no banco existente")
    parser.add_argument("--dry-run", action="store_true", help="Mostra o que seria feito")
    parser.add_argument("--verify", action="store_true", help="Verifica constraints existentes")
    args = parser.parse_args()
    
    print(f"\n{'=' * 70}")
    print(f"  Gerenciador de Constraints — empenhos.db")
    print(f"  Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"{'=' * 70}")
    
    conn = get_db()
    
    try:
        if args.verify:
            verify_constraints(conn)
        else:
            apply_constraints(conn, dry_run=args.dry_run)
    finally:
        conn.close()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
