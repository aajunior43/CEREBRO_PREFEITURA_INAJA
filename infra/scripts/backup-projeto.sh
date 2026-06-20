#!/usr/bin/env bash
# backup-projeto.sh — Backup de um projeto para o GitHub
# Uso: backup-projeto.sh <nome-do-projeto>
# Lê as configurações de /docker/<projeto>/.backup.conf

set -euo pipefail

DOCKER_DIR="/docker"
NOME="${1:-}"
LOG_FILE="/var/log/backup-projetos.log"

_log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$NOME] $*" | tee -a "$LOG_FILE"; }
_err() { _log "ERRO: $*" >&2; exit 1; }

[[ -z "$NOME" ]] && _err "Informe o nome do projeto. Uso: $0 <projeto>"

PROJ_DIR="$DOCKER_DIR/$NOME"
CONF_FILE="$PROJ_DIR/.backup.conf"

[[ -d "$PROJ_DIR" ]]  || _err "Projeto '$NOME' não encontrado em $PROJ_DIR"
[[ -f "$CONF_FILE" ]] || _err "Arquivo .backup.conf não encontrado em $CONF_FILE"

source "$CONF_FILE"

GITHUB_TOKEN="${GITHUB_TOKEN:-}"
GITHUB_REPO="${GITHUB_REPO:-}"
BACKUP_BRANCH="${BACKUP_BRANCH:-backups}"
BACKUP_PATHS="${BACKUP_PATHS:-}"
# Caminhos dentro do container a extrair via docker cp (ex: "/app/empenhos.db /app/data/")
DOCKER_PATHS="${DOCKER_PATHS:-}"

[[ -z "$GITHUB_TOKEN" ]] && _err "GITHUB_TOKEN não definido em .backup.conf"
[[ -z "$GITHUB_REPO"  ]] && _err "GITHUB_REPO não definido em .backup.conf"

_log "Iniciando backup → github.com/$GITHUB_REPO (branch: $BACKUP_BRANCH)"

WORK_DIR=$(mktemp -d)
trap 'rm -rf "$WORK_DIR"' EXIT

REMOTE_URL="https://${GITHUB_TOKEN}@github.com/${GITHUB_REPO}.git"

cd "$WORK_DIR"

if git clone --depth=1 --branch "$BACKUP_BRANCH" "$REMOTE_URL" repo 2>/dev/null; then
    cd repo
else
    _log "Branch '$BACKUP_BRANCH' não existe — criando..."
    git clone --depth=1 "$REMOTE_URL" repo 2>/dev/null || {
        mkdir -p repo && cd repo
        git init && git remote add origin "$REMOTE_URL"
    }
    cd "$WORK_DIR/repo"
    git checkout --orphan "$BACKUP_BRANCH" 2>/dev/null || true
    git rm -rf . 2>/dev/null || true
fi

git config user.email "backup@vps.local"
git config user.name  "VPS Backup"

DATA_DIR="data/$(date '+%Y-%m-%d')"
mkdir -p "$DATA_DIR"

# ── Chaves do .env (sem valores) ──────────────────────────────
if [[ -f "$PROJ_DIR/.env" ]]; then
    grep -E "^[A-Z_]+=.*" "$PROJ_DIR/.env" | \
        sed 's/=.*/=<REDACTED>/' > "$DATA_DIR/env.keys.txt" 2>/dev/null || true
    _log "Listagem de chaves do .env salva"
fi

# ── Extrair arquivos de dentro do container via docker cp ─────
if [[ -n "$DOCKER_PATHS" ]]; then
    # Descobrir o container em execução do projeto
    CONTAINER=$(cd "$PROJ_DIR" && docker compose ps -q 2>/dev/null | head -1)
    if [[ -n "$CONTAINER" ]]; then
        EXTRACT_DIR="$WORK_DIR/extracted"
        mkdir -p "$EXTRACT_DIR"
        for cpath in $DOCKER_PATHS; do
            fname=$(basename "$cpath")
            if docker cp "${CONTAINER}:${cpath}" "$EXTRACT_DIR/$fname" 2>/dev/null; then
                cp "$EXTRACT_DIR/$fname" "$DATA_DIR/$fname"
                SIZE=$(du -sh "$EXTRACT_DIR/$fname" | cut -f1)
                _log "Container → $fname ($SIZE)"
            else
                _log "Aviso: não foi possível extrair $cpath do container"
            fi
        done
    else
        _log "Aviso: container do projeto não está rodando — pulando DOCKER_PATHS"
    fi
fi

# ── Copiar paths do host ───────────────────────────────────────
if [[ -n "$BACKUP_PATHS" ]]; then
    for path_pattern in $BACKUP_PATHS; do
        full_path="$PROJ_DIR/$path_pattern"
        for item in $full_path; do
            [[ -e "$item" ]] || continue
            rel=$(basename "$item")
            if [[ -d "$item" ]]; then
                cp -r "$item" "$DATA_DIR/$rel" 2>/dev/null || true
                _log "Diretório copiado: $rel"
            else
                cp "$item" "$DATA_DIR/$rel" 2>/dev/null || true
                _log "Arquivo copiado: $rel ($(du -sh "$item" | cut -f1))"
            fi
        done
    done
fi

# ── docker-compose.yml e status ───────────────────────────────
[[ -f "$PROJ_DIR/docker-compose.yml" ]] && \
    cp "$PROJ_DIR/docker-compose.yml" "$DATA_DIR/docker-compose.yml"

cd "$PROJ_DIR" && docker compose ps 2>/dev/null > "$WORK_DIR/repo/$DATA_DIR/container-status.txt" || true
cd "$WORK_DIR/repo"

# ── README ────────────────────────────────────────────────────
cat > README.md <<EOF
# Backup — $NOME

Backups automáticos do projeto **$NOME** enviados para o GitHub.

| Info | Valor |
|---|---|
| Projeto | $NOME |
| Branch | $BACKUP_BRANCH |
| Última execução | $(date '+%Y-%m-%d %H:%M:%S UTC') |

## Estrutura

\`\`\`
data/YYYY-MM-DD/
  *.db              — banco de dados extraído do container
  docker-compose.yml
  env.keys.txt      — variáveis de ambiente (sem valores)
  container-status.txt
\`\`\`

> Histórico dos últimos 30 dias mantido automaticamente.
EOF

# Remover backups com mais de 30 dias
find data/ -maxdepth 1 -type d -name "????-??-??" | sort | head -n -30 | xargs rm -rf 2>/dev/null || true

# ── Commit e push ─────────────────────────────────────────────
git add -A
if git diff --cached --quiet; then
    _log "Nenhuma alteração desde o último backup."
else
    git commit -m "backup: $NOME — $(date '+%Y-%m-%d %H:%M')"
    git push origin "$BACKUP_BRANCH" 2>/dev/null || \
    git push --set-upstream origin "$BACKUP_BRANCH"
    _log "✅ Backup enviado → github.com/$GITHUB_REPO@$BACKUP_BRANCH"
fi
