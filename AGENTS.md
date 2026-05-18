# AGENTS.md — CEREBRO_PREFEITURA_INAJA

## Entry Point

- **Main server**: `python server.py` (or double-click `iniciar.bat`)
- **Do NOT use** `app/__init__.py` — it's a stale/abandoned factory. The real app is created in `server.py:create_app()`

## Architecture

- **Flask + SQLite** monolith with modular blueprints
- **`server.py`** — app factory, DB init, static file cache in RAM, middleware, blueprint registration
- **`routes/`** — all API blueprints:
  - `credores.py` — CRUD credores (fornecedores)
  - `empenhos.py` — empenhos mensais
  - `kanban.py` — tarefas/kanban com anexos
  - `documentos.py` — centro de documentos + blueprint `bp_autentique`
  - `all_routes.py` — prazos, protocolos, RPAs, PDF, despesas, CNPJ, IA chat proxy, config, logs, auth, extratos, empenho_assistente, classificador
- **`services/`** — business logic: `openrouter_service.py`, `ai_tasks.py`, `tavily_service.py`, `empenhos_service.py`, `extratos_service.py`
- **`renomer/`** — file organizer with AI
- **`app/`** — **STALE/UNUSED** — do not modify, this is a leftover from a refactoring attempt

## Database

- Single SQLite file: `empenhos.db` (gitignored)
- Schema created/migrated at startup in `server.py:init_db()` and `migrate_db()`
- Connection is thread-local, shared via `app._get_db` → `g._get_db`
- All blueprints access DB via: `from flask import g; conn = g._get_db()`
- PRAGMAs: `journal_mode=DELETE`, `synchronous=NORMAL`, `foreign_keys=ON`

## Key Conventions

- **Config**: `config.py` uses a frozen dataclass `Settings`, reads from env vars (`APP_HOST`, `APP_PORT`, `ADM_PASSWORD`, `OPENROUTER_*`)
- **Static files**: preloaded into RAM cache at boot with gzip+brotli compression. Debug mode checks mtime on each request.
- **AI/LLM**: OpenRouter proxy. API key and model stored in `configuracoes` DB table (keys: `api_openrouter_key`, `api_openrouter_modelo`, `api_opencode_go_key`). Also fallback to env vars `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`.
- **Auth**: simple SHA-256 hash of `ADM_PASSWORD`, verified via `/api/auth/adm`. No sessions/tokens — client-side state only.
- **Rate limiting**: `/api/auth/adm` uses `rate_limited()` from `routes/helpers.py`
- **CNPJ lookup**: tries `open.cnpja.com` first, falls back to `receitaws.com`

## Commands

```bash
# Start server
python server.py

# Install deps
pip install -r requirements.txt

# Run tests (basic structure checks only)
python -m pytest tests/
```

## Security Issues

- No CSRF protection
- Admin auth is client-side only (SHA-256 hash, no session)
- `.env` is NOT in `.gitignore` — add it

## Quirks

- `iniciar.ps1` auto-kills processes on port 5000 before starting
- `routes/all_routes.py` is very large (~1500+ lines) — contains many unrelated blueprints in one file
- `data.js` seeds the database with initial `CREDORES_FIXOS` if the `credores` table is empty
- `renomer/` directory is a standalone file organizer tool, not part of the web app
- `app/` directory is abandoned — the project uses `server.py` directly, not the `app/` factory
