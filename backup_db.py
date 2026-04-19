"""
backup_db.py — Backup automatizado do empenhos.db com rotação e logs

Uso:
  python backup_db.py              # Backup simples
  python backup_db.py --rotate 30  # Manter últimos 30 dias
  python backup_db.py --verify     # Verificar integridade do último backup

Task Scheduler (executar diariamente):
  schtasks /Create /TN "BackupEmpenhosDB" /TR "python C:\\caminho\\backup_db.py --rotate 30" /SC DAILY /ST 02:00
"""

import argparse
import hashlib
import logging
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# ── Configuração ─────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "empenhos.db"
BACKUP_DIR = BASE_DIR / "backups"
LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "backup.log"

# Manter backups dos últimos N dias (0 = infinito)
DEFAULT_RETENTION_DAYS = 30

# ── Logging ──────────────────────────────────────────────────
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)

logger = logging.getLogger("backup_db")
logger.setLevel(logging.INFO)

_file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
_file_handler.setFormatter(
    logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
)
logger.addHandler(_file_handler)

_console_handler = logging.StreamHandler(sys.stdout)
_console_handler.setFormatter(
    logging.Formatter("[%(levelname)s] %(message)s")
)
logger.addHandler(_console_handler)


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _human_timestamp() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")


def _backup_filename() -> str:
    return f"empenhos_backup_{_timestamp()}.db"


def _backup_path(filename: str) -> Path:
    return BACKUP_DIR / filename


# ── Verificação de integridade do SQLite ─────────────────────
def verify_db_integrity(db_path: Path) -> tuple[bool, str]:
    """
    Verifica integridade do banco via PRAGMA integrity_check.
    Retorna (ok, mensagem).
    """
    if not db_path.exists():
        return False, f"Arquivo não encontrado: {db_path}"

    if db_path.stat().st_size == 0:
        return False, f"Arquivo vazio: {db_path}"

    try:
        conn = sqlite3.connect(str(db_path), timeout=10)
        cursor = conn.cursor()

        # Integrity check
        result = cursor.execute("PRAGMA integrity_check").fetchall()
        conn.close()

        if result == [("ok",)]:
            size_mb = db_path.stat().st_size / (1024 * 1024)
            return True, f"Íntegro ({size_mb:.2f} MB)"
        else:
            errors = [r[0] for r in result[:5]]
            return False, f"Corrompido: {'; '.join(errors)}"

    except sqlite3.Error as e:
        return False, f"Erro SQLite: {e}"
    except Exception as e:
        return False, f"Erro inesperado: {e}"


# ── Cálculo de hash SHA256 ──────────────────────────────────
def calculate_sha256(file_path: Path) -> str:
    """Calcula hash SHA256 do arquivo."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


# ── Backup principal ────────────────────────────────────────
def create_backup(retention_days: int = DEFAULT_RETENTION_DAYS) -> dict:
    """
    Cria backup do empenhos.db com validação e rotação.
    Retorna dict com informações do backup.
    """
    result = {
        "success": False,
        "backup_file": None,
        "size_bytes": 0,
        "sha256": None,
        "integrity_ok": False,
        "integrity_msg": "",
        "deleted_old": [],
        "errors": [],
    }

    # 1. Verificar se o banco original existe
    if not DB_PATH.exists():
        msg = f"Banco original não encontrado: {DB_PATH}"
        logger.error(msg)
        result["errors"].append(msg)
        return result

    # 2. Verificar integridade do banco original antes do backup
    original_ok, original_msg = verify_db_integrity(DB_PATH)
    if not original_ok:
        msg = f"Banco original com problemas: {original_msg}"
        logger.warning(msg)
        # Continua mesmo assim, mas registra o aviso

    # 3. Criar cópia do banco
    backup_filename = _backup_filename()
    backup_file = _backup_path(backup_filename)

    try:
        logger.info(f"Iniciando backup: {backup_filename}")
        logger.info(f"Origem: {DB_PATH}")
        logger.info(f"Destino: {backup_file}")

        # Usar shutil.copy2 para preservar metadados
        shutil.copy2(DB_PATH, backup_file)

        # 4. Verificar integridade do backup
        backup_ok, backup_msg = verify_db_integrity(backup_file)
        result["integrity_ok"] = backup_ok
        result["integrity_msg"] = backup_msg

        if not backup_ok:
            msg = f"Backup corrompido: {backup_msg}"
            logger.error(msg)
            result["errors"].append(msg)
            # Remover backup corrompido
            try:
                backup_file.unlink()
            except Exception:
                pass
            return result

        # 5. Calcular tamanho e hash
        size_bytes = backup_file.stat().st_size
        result["size_bytes"] = size_bytes
        result["sha256"] = calculate_sha256(backup_file)
        result["backup_file"] = str(backup_file)
        result["success"] = True

        size_mb = size_bytes / (1024 * 1024)
        logger.info(f"Backup criado com sucesso: {backup_filename} ({size_mb:.2f} MB)")
        logger.info(f"Integridade: {backup_msg}")
        logger.info(f"SHA256: {result['sha256'][:16]}...")

        # 6. Salvar hash em arquivo separado
        save_hash_file(backup_file, result["sha256"])

        # 7. Rotação — remover backups antigos
        if retention_days > 0:
            deleted = rotate_backups(retention_days)
            result["deleted_old"] = deleted
            if deleted:
                logger.info(f"Rotação: {len(deleted)} backup(s) antigo(s) removido(s)")

        return result

    except Exception as e:
        msg = f"Erro ao criar backup: {e}"
        logger.error(msg)
        result["errors"].append(msg)

        # Limpar arquivo parcial se existir
        try:
            if backup_file.exists():
                backup_file.unlink()
        except Exception:
            pass

        return result


# ── Rotação de backups ──────────────────────────────────────
def rotate_backups(retention_days: int) -> list[str]:
    """
    Remove backups mais antigos que retention_days.
    Retorna lista de arquivos removidos.
    """
    import glob

    deleted = []
    cutoff = datetime.now().timestamp() - (retention_days * 86400)

    # Padrão: empenhos_backup_YYYYMMDD_HHMMSS.db
    pattern = str(BACKUP_DIR / "empenhos_backup_*.db")
    backup_files = glob.glob(pattern)

    for filepath in backup_files:
        try:
            file_mtime = os.path.getmtime(filepath)
            if file_mtime < cutoff:
                os.remove(filepath)
                deleted.append(os.path.basename(filepath))
                logger.debug(f"Removido backup antigo: {os.path.basename(filepath)}")
        except Exception as e:
            logger.warning(f"Falha ao remover {filepath}: {e}")

    # Também remover arquivos de hash antigos (.sha256)
    pattern_sha = str(BACKUP_DIR / "empenhos_backup_*.sha256")
    for filepath in glob.glob(pattern_sha):
        try:
            file_mtime = os.path.getmtime(filepath)
            if file_mtime < cutoff:
                os.remove(filepath)
                deleted.append(os.path.basename(filepath))
        except Exception:
            pass

    return deleted


# ── Salvar hash do backup ───────────────────────────────────
def save_hash_file(backup_file: Path, sha256: str):
    """Salva hash SHA256 em arquivo .sha256 separado."""
    hash_file = backup_file.with_suffix(".db.sha256")
    with open(hash_file, "w", encoding="utf-8") as f:
        f.write(f"{sha256}  {backup_file.name}\n")


# ── Verificar último backup ─────────────────────────────────
def verify_latest_backup() -> dict:
    """Verifica integridade do backup mais recente."""
    import glob

    result = {
        "found": False,
        "file": None,
        "integrity_ok": False,
        "integrity_msg": "",
        "sha256_match": None,
    }

    pattern = str(BACKUP_DIR / "empenhos_backup_*.db")
    backup_files = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)

    if not backup_files:
        result["integrity_msg"] = "Nenhum backup encontrado"
        return result

    latest = Path(backup_files[0])
    result["found"] = True
    result["file"] = str(latest)

    # Verificar integridade
    ok, msg = verify_db_integrity(latest)
    result["integrity_ok"] = ok
    result["integrity_msg"] = msg

    # Verificar hash se existir arquivo .sha256
    hash_file = latest.with_suffix(".db.sha256")
    if hash_file.exists():
        try:
            with open(hash_file, "r", encoding="utf-8") as f:
                expected_hash = f.read().split()[0]
            actual_hash = calculate_sha256(latest)
            result["sha256_match"] = expected_hash == actual_hash
        except Exception as e:
            result["sha256_match"] = False
            logger.warning(f"Erro ao verificar hash: {e}")

    return result


# ── Listar backups disponíveis ──────────────────────────────
def list_backups() -> list[dict]:
    """Lista todos os backups disponíveis com informações."""
    import glob

    backups = []
    pattern = str(BACKUP_DIR / "empenhos_backup_*.db")
    backup_files = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)

    for filepath in backup_files:
        path = Path(filepath)
        stat = path.stat()
        size_mb = stat.st_size / (1024 * 1024)
        modified = datetime.fromtimestamp(stat.st_mtime)

        backups.append({
            "file": path.name,
            "path": str(path),
            "size_mb": round(size_mb, 2),
            "created": modified.strftime("%d/%m/%Y %H:%M:%S"),
            "days_ago": (datetime.now() - modified).days,
        })

    return backups


# ── Main ────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Backup automatizado do empenhos.db")
    parser.add_argument(
        "--rotate", type=int, default=DEFAULT_RETENTION_DAYS,
        help=f"Manter backups dos últimos N dias (padrão: {DEFAULT_RETENTION_DAYS}, 0=infinity)"
    )
    parser.add_argument(
        "--verify", action="store_true",
        help="Verificar integridade do último backup"
    )
    parser.add_argument(
        "--list", action="store_true",
        help="Listar backups disponíveis"
    )
    args = parser.parse_args()

    print("=" * 60)
    print(f"  Backup Automatizado — empenhos.db")
    print(f"  Data: {_human_timestamp()}")
    print("=" * 60)

    if args.verify:
        # Modo verificação
        result = verify_latest_backup()
        if result["found"]:
            print(f"\nArquivo: {result['file']}")
            print(f"Integridade: {'OK' if result['integrity_ok'] else 'FALHOU'}")
            print(f"Detalhes: {result['integrity_msg']}")
            if result["sha256_match"] is not None:
                print(f"Hash válido: {'SIM' if result['sha256_match'] else 'NÃO'}")
        else:
            print(f"\n{result['integrity_msg']}")
        return 0 if result.get("integrity_ok", False) else 1

    if args.list:
        # Modo listagem
        backups = list_backups()
        if not backups:
            print("\nNenhum backup encontrado.")
        else:
            print(f"\nBackups disponíveis ({len(backups)}):")
            print(f"{'Arquivo':<45} {'Tamanho':>8} {'Data':>20} {'Idade':>8}")
            print("-" * 85)
            for b in backups:
                print(f"{b['file']:<45} {b['size_mb']:>6.2f} MB  {b['created']:>20}  {b['days_ago']:>3}d")
        return 0

    # Modo backup normal
    result = create_backup(retention_days=args.rotate)

    if result["success"]:
        print(f"\nBackup criado com sucesso!")
        print(f"  Arquivo: {result['backup_file']}")
        print(f"  Tamanho: {result['size_bytes'] / (1024 * 1024):.2f} MB")
        print(f"  Integridade: {result['integrity_msg']}")
        print(f"  SHA256: {result['sha256'][:32]}...")
        if result["deleted_old"]:
            print(f"  Rotação: {len(result['deleted_old'])} backup(s) antigo(s) removido(s)")
    else:
        print(f"\nFALHA ao criar backup:")
        for error in result["errors"]:
            print(f"  ✗ {error}")

    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
