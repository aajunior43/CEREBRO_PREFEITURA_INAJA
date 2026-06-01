"""
backup_db.py — Backup automático dos bancos de dados para o GitHub.

Estratégia segura:
  - NUNCA altera o branch do repositório principal
  - Cria a branch 'backups' via git plumbing (sem checkout)
  - Usa git worktree para trabalhar na branch separada
  - Exporta dump SQL (texto compressível pelo git)
  - Commita e faz push a cada execução com alterações

Uso manual:   python backup_db.py
Agendamento:  executar backup_db.bat pelo Windows Task Scheduler
"""

import sqlite3
import subprocess
import shutil
import sys
import os
import tempfile
from pathlib import Path
from datetime import datetime

# ─── Configuração ────────────────────────────────────────────────────────────
BASE_DIR      = Path(__file__).resolve().parent
DATABASES     = [BASE_DIR / "empenhos.db"]
BACKUP_BRANCH = "backups"
WORKTREE_DIR  = BASE_DIR / ".backup_worktree"
LOG_FILE      = BASE_DIR / "backup_db.log"
# ─────────────────────────────────────────────────────────────────────────────


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def run(cmd: list, cwd=None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(cwd or BASE_DIR),
        capture_output=True,
        text=True,
    )


def current_branch() -> str:
    r = run(["git", "branch", "--show-current"])
    return r.stdout.strip() or "main"


def remote_branch_exists() -> bool:
    run(["git", "fetch", "origin", "--prune"])
    r = run(["git", "ls-remote", "--heads", "origin", BACKUP_BRANCH])
    return BACKUP_BRANCH in r.stdout


def local_branch_exists() -> bool:
    r = run(["git", "branch", "--list", BACKUP_BRANCH])
    return bool(r.stdout.strip())


def create_backup_branch_safe():
    """
    Cria a branch 'backups' SEM fazer checkout no working dir principal.
    Usa git plumbing: hash-object + mktree + commit-tree + update-ref.
    """
    log(f"  Criando branch '{BACKUP_BRANCH}' (sem alterar branch atual)...")

    readme_content = (
        "# Backups Automáticos\n\n"
        "Dumps SQL do banco de dados gerados automaticamente a cada 30 minutos.\n\n"
        "## Restaurar\n```bash\nsqlite3 novo.db < backups/empenhos.db.sql\n```\n"
    )

    with tempfile.NamedTemporaryFile(mode='w', suffix='.md',
                                     delete=False, encoding='utf-8') as tmp:
        tmp.write(readme_content)
        tmp_path = tmp.name

    try:
        r = run(["git", "hash-object", "-w", tmp_path])
        blob_sha = r.stdout.strip()
        if not blob_sha:
            raise RuntimeError("Falha ao criar blob: " + r.stderr)

        tree_input = f"100644 blob {blob_sha}\tREADME.md\n"
        r = subprocess.run(
            ["git", "mktree"],
            input=tree_input,
            cwd=str(BASE_DIR),
            capture_output=True, text=True,
        )
        tree_sha = r.stdout.strip()
        if not tree_sha:
            raise RuntimeError("Falha ao criar tree: " + r.stderr)

        env = {**os.environ,
               "GIT_AUTHOR_NAME": "Backup Auto",
               "GIT_AUTHOR_EMAIL": "backup@sistema.local",
               "GIT_COMMITTER_NAME": "Backup Auto",
               "GIT_COMMITTER_EMAIL": "backup@sistema.local"}

        r = subprocess.run(
            ["git", "commit-tree", tree_sha, "-m", "init: backup branch"],
            cwd=str(BASE_DIR), capture_output=True, text=True, env=env,
        )
        commit_sha = r.stdout.strip()
        if not commit_sha:
            raise RuntimeError("Falha ao criar commit: " + r.stderr)

        r = run(["git", "update-ref", f"refs/heads/{BACKUP_BRANCH}", commit_sha])
        if r.returncode != 0:
            raise RuntimeError("Falha ao criar branch local: " + r.stderr)

        r = run(["git", "push", "-u", "origin", BACKUP_BRANCH])
        if r.returncode != 0:
            raise RuntimeError("Falha ao fazer push: " + r.stderr)

        log(f"  Branch '{BACKUP_BRANCH}' criada e enviada ao GitHub.")

    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


def ensure_backup_branch():
    """Garante que a branch backups existe localmente e no remoto."""
    if remote_branch_exists():
        if not local_branch_exists():
            run(["git", "branch", "--track",
                 BACKUP_BRANCH, f"origin/{BACKUP_BRANCH}"])
        return
    create_backup_branch_safe()


def setup_worktree():
    """Adiciona ou atualiza worktree para a branch backups."""
    if WORKTREE_DIR.exists() and (WORKTREE_DIR / ".git").exists():
        run(["git", "fetch", "origin", BACKUP_BRANCH])
        run(["git", "reset", "--hard", f"origin/{BACKUP_BRANCH}"], cwd=WORKTREE_DIR)
        return

    if WORKTREE_DIR.exists():
        run(["git", "worktree", "remove", str(WORKTREE_DIR), "--force"])
        shutil.rmtree(WORKTREE_DIR, ignore_errors=True)

    run(["git", "worktree", "prune"])

    log(f"  Adicionando worktree '{WORKTREE_DIR.name}'...")
    r = run(["git", "worktree", "add", str(WORKTREE_DIR), BACKUP_BRANCH])
    if r.returncode != 0:
        raise RuntimeError(f"Erro ao criar worktree: {r.stderr.strip()}")


def wal_checkpoint(db_path: Path):
    try:
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA wal_checkpoint(FULL)")
        conn.commit()
        conn.close()
    except Exception as e:
        log(f"  WAL checkpoint ({db_path.name}): {e}")


def sql_dump(db_path: Path, dest_path: Path):
    conn = sqlite3.connect(str(db_path))
    with open(dest_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"-- Backup: {datetime.now().isoformat()}\n")
        f.write(f"-- Banco: {db_path.name}\n")
        f.write("PRAGMA foreign_keys=OFF;\nBEGIN TRANSACTION;\n")
        for line in conn.iterdump():
            if line.startswith(("BEGIN TRANSACTION", "COMMIT")):
                continue
            f.write(line + "\n")
        f.write("COMMIT;\n")
    conn.close()
    size = dest_path.stat().st_size / 1024
    log(f"  Dump: {db_path.name} -> {dest_path.name} ({size:.0f} KB)")


def backup():
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log("=" * 52)
    log(f"Iniciando backup — {ts}")

    branch = current_branch()
    if branch != "main":
        log(f"  AVISO: branch atual '{branch}' nao e main.")
        log("  Continuando; backup usa worktree separada.")

    for db in DATABASES:
        if db.exists():
            wal_checkpoint(db)

    ensure_backup_branch()
    setup_worktree()

    dump_dir = WORKTREE_DIR / "backups"
    dump_dir.mkdir(parents=True, exist_ok=True)

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

    env = {**os.environ,
           "GIT_AUTHOR_NAME": "Backup Auto",
           "GIT_AUTHOR_EMAIL": "backup@sistema.local",
           "GIT_COMMITTER_NAME": "Backup Auto",
           "GIT_COMMITTER_EMAIL": "backup@sistema.local"}

    subprocess.run(["git", "add", "-A"], cwd=str(WORKTREE_DIR),
                   env=env, capture_output=True)

    diff = run(["git", "diff", "--cached", "--quiet"], cwd=WORKTREE_DIR)
    if diff.returncode == 0:
        log("Banco sem alterações. Nenhum commit criado.")
        return

    c = subprocess.run(
        ["git", "commit", "-m", f"backup(db): {ts}"],
        cwd=str(WORKTREE_DIR), env=env, capture_output=True, text=True,
    )
    if c.returncode != 0:
        log(f"  ERRO no commit: {c.stderr.strip()}")
        return

    p = run(["git", "push", "origin", BACKUP_BRANCH], cwd=WORKTREE_DIR)
    if p.returncode == 0:
        log(f"OK: Backup enviado para branch '{BACKUP_BRANCH}' no GitHub.")
    else:
        log(f"ERRO push: {p.stderr.strip()}")

    log("Backup concluído.")


if __name__ == "__main__":
    try:
        backup()
    except Exception as exc:
        log(f"ERRO inesperado: {exc}")
        sys.exit(1)
