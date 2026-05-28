"""
backup_db.py — Backup automático dos bancos de dados para o GitHub.

Funcionamento:
  1. Faz WAL checkpoint para garantir consistência do SQLite
  2. Exporta um dump SQL (texto) de cada banco — menor e diff-friendly
  3. Trabalha na branch 'backups' via git worktree, sem interferir na main
  4. Commita e faz push para o GitHub a cada execução com alterações

Uso manual:   python backup_db.py
Agendamento:  executar backup_db.bat pelo Windows Task Scheduler
"""

import sqlite3
import subprocess
import shutil
import sys
import os
from pathlib import Path
from datetime import datetime

# ─── Configuração ────────────────────────────────────────────────────────────
BASE_DIR      = Path(__file__).resolve().parent
DATABASES     = [BASE_DIR / "empenhos.db"]          # adicione outros .db aqui se necessário
BACKUP_BRANCH = "backups"
WORKTREE_DIR  = BASE_DIR / ".backup_worktree"
LOG_FILE      = BASE_DIR / "backup_db.log"
# ─────────────────────────────────────────────────────────────────────────────


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def run(cmd: list, cwd=None, check=False) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(cwd or BASE_DIR),
        capture_output=True,
        text=True,
        check=check,
    )


def wal_checkpoint(db_path: Path):
    """Força o SQLite a consolidar o WAL antes de copiar."""
    try:
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA wal_checkpoint(FULL)")
        conn.commit()
        conn.close()
    except Exception as e:
        log(f"  WAL checkpoint aviso ({db_path.name}): {e}")


def sql_dump(db_path: Path, dest_path: Path):
    """Exporta o banco como dump SQL puro (texto, comprime bem no git)."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = None
    with open(dest_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"-- Backup automático: {datetime.now().isoformat()} \n")
        f.write(f"-- Banco: {db_path.name}\n")
        f.write("PRAGMA foreign_keys=OFF;\nBEGIN TRANSACTION;\n")
        for line in conn.iterdump():
            # iterdump já inclui BEGIN/COMMIT — pulamos os duplicados
            if line.startswith("BEGIN TRANSACTION") or line.startswith("COMMIT"):
                continue
            f.write(line + "\n")
        f.write("COMMIT;\n")
    conn.close()
    size = dest_path.stat().st_size / 1024
    log(f"  Dump: {db_path.name} → {dest_path.name} ({size:.0f} KB)")


def ensure_backup_branch():
    """Garante que a branch 'backups' existe localmente e no remoto."""
    # verifica se existe no remoto
    r = run(["git", "ls-remote", "--heads", "origin", BACKUP_BRANCH])
    if BACKUP_BRANCH in r.stdout:
        run(["git", "fetch", "origin", BACKUP_BRANCH])
        return

    log(f"  Criando branch '{BACKUP_BRANCH}' (orphan)...")
    # Salva estado atual
    current = run(["git", "branch", "--show-current"]).stdout.strip() or "main"

    # Cria a branch sem histórico
    run(["git", "checkout", "--orphan", BACKUP_BRANCH])
    run(["git", "rm", "-rf", "."])

    readme = BASE_DIR / "README.md"
    readme.write_text(
        "# Backups Automáticos\n\n"
        "Esta branch contém dumps SQL do banco de dados,\n"
        "gerados automaticamente a cada 30 minutos.\n\n"
        "Para restaurar: `sqlite3 novo.db < backups/empenhos.db.sql`\n"
    )

    run(["git", "add", "README.md"])
    run(["git", "commit", "-m", "init: backup branch"])
    run(["git", "push", "-u", "origin", BACKUP_BRANCH])

    # Volta para a branch original
    run(["git", "checkout", current])
    log(f"  Branch '{BACKUP_BRANCH}' criada e enviada ao GitHub.")


def setup_worktree():
    """Cria o worktree para a branch backups (não altera a main)."""
    if WORKTREE_DIR.exists():
        # Atualiza
        run(["git", "fetch", "origin", BACKUP_BRANCH])
        run(["git", "reset", "--hard", f"origin/{BACKUP_BRANCH}"], cwd=WORKTREE_DIR)
        return

    log(f"  Configurando worktree em '{WORKTREE_DIR.name}'...")
    result = run([
        "git", "worktree", "add",
        str(WORKTREE_DIR),
        f"origin/{BACKUP_BRANCH}",
        "--track", "-b", BACKUP_BRANCH,
    ])
    if result.returncode != 0:
        # Worktree já existe com outro estado — remove e recria
        run(["git", "worktree", "remove", str(WORKTREE_DIR), "--force"])
        run([
            "git", "worktree", "add",
            str(WORKTREE_DIR),
            BACKUP_BRANCH,
        ])


def backup():
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log("=" * 52)
    log(f"Iniciando backup — {ts}")

    # 1. Checkpoint dos WALs
    for db in DATABASES:
        if db.exists():
            wal_checkpoint(db)

    # 2. Garante branch e worktree
    ensure_backup_branch()
    setup_worktree()

    # 3. Exporta dumps na pasta do worktree
    dump_dir = WORKTREE_DIR / "backups"
    dump_dir.mkdir(exist_ok=True)

    dumped = []
    for db in DATABASES:
        if not db.exists():
            log(f"  Banco não encontrado: {db.name}")
            continue
        dest = dump_dir / (db.name + ".sql")
        sql_dump(db, dest)
        dumped.append(db.name)

    if not dumped:
        log("Nenhum banco disponível. Backup abortado.")
        return

    # 4. Commit no worktree
    run(["git", "config", "user.email", "backup@sistema.local"], cwd=WORKTREE_DIR)
    run(["git", "config", "user.name",  "Backup Auto"],          cwd=WORKTREE_DIR)
    run(["git", "add", "-A"], cwd=WORKTREE_DIR)

    diff = run(["git", "diff", "--cached", "--quiet"], cwd=WORKTREE_DIR)
    if diff.returncode == 0:
        log("Banco sem alterações desde o último backup. Nenhum commit criado.")
        return

    commit_msg = f"backup(db): {ts}"
    c = run(["git", "commit", "-m", commit_msg], cwd=WORKTREE_DIR)
    if c.returncode != 0:
        log(f"  ERRO no commit: {c.stderr.strip()}")
        return

    # 5. Push para o GitHub
    p = run(["git", "push", "origin", BACKUP_BRANCH], cwd=WORKTREE_DIR)
    if p.returncode == 0:
        log(f"✅ Backup enviado: branch '{BACKUP_BRANCH}' no GitHub.")
    else:
        log(f"❌ Erro no push: {p.stderr.strip()}")

    log("Backup concluído.")


if __name__ == "__main__":
    try:
        backup()
    except Exception as exc:
        log(f"ERRO inesperado: {exc}")
        sys.exit(1)
