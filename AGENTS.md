# AGENTS.md — CEREBRO_PREFEITURA_INAJA

> Documento de referência para IAs e devs. **Mantenha atualizado** sempre que
> mexer em entry points, blueprints, schema do banco, auth ou segurança.

---

## 1. Visão geral

Monólito **Flask + SQLite** para gestão da Prefeitura de Inajá (PR): credores,
empenhos, mural, kanban, documentos com assinatura digital (Autentique), IA via
OpenRouter, classificador de despesa, gerador de PDF LaTeX, calendário, prazos,
protocolos, RPAs, despesas e CNPJ.

- **Stack:** Flask 3 + SQLite (WAL) + gevent/waitress + OpenRouter + Autentique
- **Sem build step** — frontend é HTML/CSS/JS puro servido como arquivos estáticos
- **Tamanho:** ~7k LoC Python (rotas) + 1.4k LoC (services) + 30k LoC HTML +
  11k LoC CSS + 7k LoC JS
- **DB único:** `empenhos.db` (~12 MB em uso típico)

---

## 2. Entry Point

```bash
python server.py              # produção
python server.py --reload     # dev (APP_RELOADER=1 também ativa)
```

Alternativas:
- `iniciar.bat` (Windows, duplo-clique)
- `iniciar.ps1` (Windows, mata processos na porta 5000 + opcionalmente abre
  túnel Cloudflare público — **cuidado**, expõe a app na internet)
- `dev.ps1` / `dev.bat` (dev com reload)

**Servidor de produção:** `gevent` se disponível (suporte a SSE no mural),
fallback para `waitress` (24 threads).

---

## 3. Estrutura de diretórios

```
.
├── server.py              # 1.409 linhas: factory + DB + cache estático + middleware
├── config.py              # Settings (dataclass frozen) + load .env
├── data.js                # Seeds iniciais (CREDORES_FIXOS) — usado se `credores` vazio
├── index.html             # 2.714 linhas: shell da SPA
├── login.html
├── pages/                 # 27 páginas HTML (carregadas via <iframe> ou fetch)
├── static/
│   ├── css/index.css      # 230 KB — TODO do CSS do app em um único arquivo
│   ├── js/app.js          # 87 KB / 2.266 linhas — lógica principal
│   ├── js/shared-header.js
│   ├── js/despesa/        # bem organizado (csv, historico, logic, main, state, ui, utils)
│   └── dados/             # ⚠ contém Relação de Despesas.csv — não commitar
├── routes/                # 24 arquivos .py, ~7.180 LoC
│   ├── _shared.py         # get_db, require_login, audit, openrouter helpers
│   ├── helpers.py         # rate_limited, cnpj, filtros, payloads
│   ├── all_routes.py      # ⚠ shim de re-export (29 linhas) — pode ser removido
│   └── <um .py por blueprint>
├── services/              # 6 arquivos, ~1.430 LoC
│   ├── openrouter_service.py  # cliente OpenRouter com TTLCache + retry
│   ├── ai_tasks.py            # fachada de tarefas IA (AITaskFacade)
│   ├── ai_prompts.py          # templates de prompt
│   ├── tavily_service.py
│   ├── empenhos_service.py
│   └── extratos_service.py
├── renomer/               # ferramenta standalone de renomeação de arquivos (NÃO é web)
├── tests/                 # apenas test_app_structure.py (sanity check)
├── scripts/               # utilitários de dev (benchmark, extract, render_board…)
├── documents_centro/      # arquivos enviados pelos usuários
├── logs/server.log        # RotatingFileHandler 2 MB × 3 backups
└── backup_db.py           # backup automático via git plumbing (branch `backups`)
```

**Diretórios de caches de IDE/agent (já no `.gitignore` mas presentes):**
`.kilo/`, `.qwen/`, `.claude/`, `.commandcode/`, `.vscode/`, `.pytest_cache/`,
`.backup_worktree/`.

---

## 4. `server.py` — o que cada coisa faz

`server.py:create_app()` (linha 124) é uma "fat factory" — faz tudo. Ao mexer,
considere quebrar em módulos:

| Linhas | Responsabilidade | Extrair para |
|--------|------------------|--------------|
| 1-50   | imports + gevent monkey-patch | (manter) |
| 52-121 | helpers de cor/log no terminal | (manter, é cosmético) |
| 123-153| config Flask (secret, cookies, logging) | `app/config.py` |
| 155-186| `get_db()` thread-local + teardown | `db/connection.py` |
| 188-254| `ensure_db_indexes()` (~55 índices) | `db/indexes.py` |
| 256-474| `migrate_db()` (rename→recreate→copy) | `db/migrate.py` |
| 476-635| `init_db()` (schema, FTS5, triggers, seed) | `db/schema.py` |
| 637-742| `before_request`/`after_request` (auth, gzip, timing) | `middleware.py` |
| 744-868| cache estático em RAM (gzip+brotli+etag) | `cache.py` |
| 870-952| rotas estáticas (`/`, `/static/<path>`, catch-all) | `routes/static.py` |
| 954-1258| error handlers (incl. 500 page gigante inline) | `errors.py` |
| 1261-1318| registro de **22 blueprints** + init auth | (manter) |
| 1324-1409| `__main__` (gevent/waitress + banner) | `cli.py` |

---

## 5. Blueprints registrados (`server.py:1262-1308`)

22 blueprints — `import` no topo de `server.py` + `register_blueprint` no final
de `create_app`.

| Prefixo lógico | Módulo | Tamanho | O que faz |
|----------------|--------|---------|-----------|
| `bp_credores` | `routes/credores.py` | 14 KB | CRUD de credores (fornecedores) |
| `bp_mural` | `routes/mural.py` | 19 KB | Recados do mural com **SSE streaming** |
| `bp_calendario` | `routes/calendario.py` | 7 KB | Calendário de pagamentos/compromissos |
| `bp_empenhos` | `routes/empenhos.py` | 3 KB | Empenhos mensais (CRUD enxuto) |
| `bp_kanban` | `routes/kanban.py` | 30 KB | Tarefas kanban + anexos |
| `bp_documentos` | `routes/documentos.py` | 62 KB | Centro de documentos |
| `bp_autentique` | `routes/documentos.py` | (mesmo) | Integração Autentique (whatsapp signature) |
| `bp_prazos` | `routes/prazos.py` | 6 KB | Prazos/alertas |
| `bp_protocolos` | `routes/protocolos.py` | 10 KB | Protocolos (entrada/saída) |
| `bp_rpas` | `routes/rpas.py` | 6 KB | RPA (Recibo Pagamento Autônomo) |
| `bp_fornecimento` | `routes/fornecimento.py` | 14 KB | Solicitação de fornecimento |
| `bp_pdf` | `routes/pdf.py` | 3 KB | Geração PDF (PyPDF2/pdfplumber) |
| `bp_despesas` | `routes/despesas.py` | 21 KB | Importação/análise de despesas |
| `bp_cnpj` | `routes/cnpj.py` | 8 KB | Consulta CNPJ (open.cnpja → receitaws) |
| `bp_ia` | `routes/ia.py` | 1 KB | Proxy chat IA |
| `bp_config` | `routes/config.py` | 7 KB | Configurações runtime (DB) |
| `bp_logs` | `routes/logs.py` | 4 KB | Logs de auditoria |
| `bp_auth` | `routes/auth.py` | 16 KB | **Auth multi-usuário** (login/sessão/CRUD) |
| `bp_extratos` | `routes/extratos.py` | 3 KB | Extratos bancários |
| `bp_empenho_assistente` | `routes/empenho_assistente.py` | 8 KB | Assistente IA de empenhos |
| `bp_classificador` | `routes/classificador.py` | 6 KB | Classificador de despesa por IA |
| `bp_latex_pdf` | `routes/latex_pdf.py` | 14 KB | Geração PDF via LaTeX |

**Nota:** `routes/documentos.py` é enorme (62 KB / ~1.490 linhas) e mistura
dois blueprints. **Refatorar:** extrair `bp_autentique` para `routes/autentique.py`
+ `services/autentique_service.py`.

---

## 6. Helpers compartilhados

| Função | Onde | Para quê |
|--------|------|----------|
| `get_db()` | `routes/_shared.py:9` | `g._get_db()` — conexão SQLite thread-local |
| `require_login` | `routes/_shared.py:14` | decorator que exige `session["usuario_id"]` |
| `registrar_auditoria()` | `routes/_shared.py:29` | insere em `audit_trail` (INSERT genérico) |
| `row_to_dict()` | `routes/_shared.py:51` | `dict(row)` (sqlite3.Row) |
| `_get_openrouter_config()` | `routes/_shared.py:55` | lê chaves de `configuracoes` + env |
| `_build_ai_service()` / `_build_ai_facade()` | `routes/_shared.py:87,103` | constrói cliente/fachada IA |
| `rate_limited(key, max_hits, window)` | `routes/helpers.py` | rate limit em memória por chave |
| `normalizar_cnpj` / `cnpj_valido` | `routes/helpers.py` | utilitários de CNPJ |
| `montar_filtros_credores()` | `routes/helpers.py` | constrói `WHERE` com FTS5 MATCH |

**Anti-pattern:** muitos blueprints re-definem `get_db`/`row_to_dict` como
no-op passthroughs. Importe sempre de `routes/_shared`.

---

## 7. Database

- **Arquivo único:** `empenhos.db` (gitignored) — `BASE_DIR / "empenhos.db"`
- **Acesso:** `from flask import g; conn = g._get_db()`
  (thread-local inicializado em `server.py:160-173`)
- **PRAGMAs** (`server.py:165-171`):
  ```sql
  PRAGMA foreign_keys=ON
  PRAGMA journal_mode=WAL
  PRAGMA synchronous=NORMAL
  PRAGMA cache_size=-8000
  PRAGMA temp_store=MEMORY
  PRAGMA mmap_size=0
  PRAGMA auto_vacuum=INCREMENTAL
  ```
- **Schema:** `server.py:init_db()` cria ~22 tabelas + 2 FTS5 + 1 view
  (`v_classificador_despesa`) + triggers de sync FTS5
- **Migrações:** `server.py:migrate_db()` faz rename→recreate→copy→drop
  (destrutivo, mas wrapped em `try/except: pass`)
- **Versão de schema:** tabela `schema_version` existe (`version=2`) mas
  **não é consultada** — o sistema não tem migração incremental de verdade
- **~55 índices** criados em `ensure_db_indexes()` (`server.py:188-254`)
- **`VACUUM` roda em todo boot** (`server.py:609`) — desnecessário na inicialização
- **`audit_trail`** é populada por `routes/_shared.registrar_auditoria()` mas
  **não tem dashboard/UI** para leitura

### Tabelas principais (resumo)

`credores`, `logs`, `empenhos`, `rpas`, `kanban_tasks`, `kanban_attachments`,
`fornecimento_dados`, `fornecimento_solicitacoes`, `fornecimento_solicitacao_itens`,
`configuracoes`, `documentos_centro`, `autentique_envios`, `autentique_contatos`,
`empenho_assistente_historico`, `classificador_despesa_historico`, `prazos`,
`protocolos`, `protocolo_anexos`, `mural_recados`, `mural_anexos`,
`mural_anexo_contents`, `mural_comentarios`, `calendario_eventos`,
`calendario_overrides`, `calendario_regras`, `csv_importacoes`, `csv_linhas`,
`usuarios`, `audit_trail`.

---

## 8. Configuração

`config.py` (dataclass frozen `Settings`) lê do `.env` (com fallback manual
caso `python-dotenv` não esteja instalado).

| Env var | Default | Uso |
|---------|---------|-----|
| `APP_HOST` | `0.0.0.0` | bind do servidor |
| `APP_PORT` | `5000` | porta |
| `APP_DEBUG` | `false` | ativa `app.debug = True` (e reloader auto) |
| `APP_RELOADER` | `false` | reloader Werkzeug |
| `ADM_PASSWORD` | `""` | senha do `aleksandro` + parte do `secret_key` |
| `OPENROUTER_DEFAULT_MODEL` | `opencode-go/deepseek-v4-flash` | modelo padrão |
| `OPENROUTER_CHAT_MODEL` | mesmo | modelo do chat widget |
| `OPENROUTER_REFERER` | `https://localhost` | header `HTTP-Referer` |
| `OPENROUTER_TITLE` | `CEREBRO_PREFEITURA` | header `X-Title` |
| `OPENROUTER_TIMEOUT_SECONDS` | `60` | |
| `OPENROUTER_MAX_RETRIES` | `3` | |
| `OPENROUTER_BACKOFF_BASE` | `1.5` | |
| `OPENROUTER_CACHE_TTL_SECONDS` | `900` | cache em memória |

**Chaves de IA também são lidas do banco** (tabela `configuracoes`):
- `api_openrouter_key`
- `api_openrouter_modelo`
- `api_opencode_go_key` (usada quando o modelo começa com `opencode-go/`)

E como fallback do env: `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`,
`OPENCODE_GO_API_KEY`.

---

## 9. Auth & Segurança

### Como funciona

- **Multi-usuário** (NÃO é mais SHA-256 client-side). Tabela `usuarios` com
  níveis `adm` / `padrao` (`CHECK` no schema).
- Login: `POST /api/auth/login` com `{"login", "senha"}` → seta
  `session["usuario_id"]`, `session["usuario_login"]`, `session["usuario_nome"]`,
  `session["usuario_nivel"]` (cookie `inaja_sid`).
- Cookie: `HttpOnly`, `SameSite=Lax`, **sem `Secure`** (vaza se tunelado HTTPS→HTTP).
- `require_login` decorator (`routes/_shared.py:14`) protege endpoints.
- Middleware global em `server.py:before_request` (whitelist-based) protege
  rotas `/api/*` não autenticadas.

### Hash de senha

`routes/auth.py:12-13`:
```python
def _hash(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()
```

**⚠ Sem salt, sem key-stretching.** Trocar por
`werkzeug.security.generate_password_hash` (scrypt/pbkdf2) ou `argon2-cffi`.

### Seed inicial (`routes/auth.py:76-113`)

`_seed_admin()` cria/atualiza 3 usuários:
- `aleksandro` (nível `adm`, senha = `ADM_PASSWORD` do env)
- `maicon` (nível `padrao`, senha = `Inaja@2025!` **hardcoded**)
- `luana` (nível `padrao`, senha = `Inaja@2025!` **hardcoded**)

### Secret key (`server.py:129-131`)

```python
_base = settings.admin_password or "inaja-prefeitura-secret-key-2024"
app.secret_key = _hl.sha256(f"inaja::sessao::{_base}".encode()).hexdigest()
```

**⚠ Fallback literal** se `ADM_PASSWORD` vazio — qualquer um pode forjar sessão.

### Rate limit

- `POST /api/auth/login` — 10 hits / 60s por IP (`routes/auth.py:152`)
- `POST /api/auth/adm` (legacy) — 5 hits / 60s
- **Não há rate limit** em endpoints de IA (`/api/ia/chat`,
  `/api/empenho-assistente/*`, `/api/classificador/*`, `/api/latex-pdf/*`) —
  usuários autenticados podem hammerar a OpenRouter.

---

## 10. OpenRouter / IA

- **Cliente:** `services/openrouter_service.py` (438 linhas) — com `TTLCache`
  in-memory, retry com backoff exponencial, fallback de modelo.
- **Fachada de tarefas:** `services/ai_tasks.py` (AITaskFacade)
- **Templates:** `services/ai_prompts.py`
- **Search opcional:** `services/tavily_service.py` (Tavily)
- **Resolução de config:** `_get_openrouter_config()` em `routes/_shared.py:55`
  (banco > env > default)

---

## 11. Frontend

- **27 páginas HTML** em `pages/` (carregadas como iframes ou fragmentos)
- **CSS monolítico:** `static/css/index.css` (230 KB) — quebra isso
- **JS principal:** `static/js/app.js` (87 KB / 2.266 linhas) — quebra isso
- **JS de módulo bem organizados:**
  - `static/js/despesa/{csv,historico,logic,main,state,ui,utils}.js`
  - `static/js/{ia-chat-widget,latex-pdf,assistente-empenho,error-handler,ai-cache,ocr-optimizer,usage-logger,document-autosave,adm-guard}.js`
- **CDN externa:** `index.html:28` carrega Phosphor Icons do `unpkg.com`,
  `server.py:1018` carrega Google Fonts. **Quebra offline.**
- **Dados sensíveis em `static/`:** `static/dados/Relação de Despesas.csv`
  (171 KB) — **mover para fora de `static/`**.

---

## 12. Backup

- `backup_db.py` (8.5 KB) — backup automático do `empenhos.db` via
  **git plumbing puro** (hash-object + mktree + commit-tree + update-ref)
  para a branch `backups` em worktree separado (`.backup_worktree/`).
- O running repo nunca é perturbado (a branch não é checked out).
- Agendamento: `register_backup_task.bat` (Windows Task Scheduler).

---

## 13. Comandos

```bash
# Instalar deps
pip install -r requirements.txt

# Rodar servidor (produção)
python server.py

# Rodar servidor (dev com reload)
APP_RELOADER=1 python server.py

# Backup manual
python backup_db.py

# Testes (sanity check estrutural)
python -m pytest tests/
```

---

## 14. Pendências / NÃO FAÇA (antes de refatorar)

> Estes são débitos técnicos conhecidos. **Agentes não devem piorar** a
> situação, e devem preferir atacar um item por vez com PRs pequenos.

### Crítico (segurança)
- [ ] Rotacionar `ADM_PASSWORD=aleksandro` e remover do `.env` trackeado
- [ ] Substituir SHA-256 por `werkzeug.security` (scrypt/pbkdf2) em `auth.py:13`
- [ ] Adicionar flag `SESSION_COOKIE_SECURE` quando `APP_HOST != 127.0.0.1`
- [ ] Implementar CSRF (Flask-WTF) ou `SameSite=Strict` para mutações
- [ ] Adicionar rate limit em `/api/ia/chat`, `/api/latex-pdf/*`,
      `/api/classificador/*`, `/api/extratos/*`
- [ ] Remover fallback literal de `secret_key` em `server.py:129-131`
- [ ] Trocar senhas seed `Inaja@2025!` (`auth.py:101,111`) por placeholders
      que forcem primeiro-login

### Importante (robustez)
- [ ] Mover `static/dados/Relação de Despesas.csv` para fora de `static/`
- [ ] Tirar `VACUUM` do boot (rodar em cron / sob demanda)
- [ ] Usar `schema_version` para migrações incrementais (hoje é só stamp v=2)
- [ ] Remover migrações destrutivas silenciosas (`try/except: pass` em
      `migrate_db()`) — pelo menos logar warning
- [ ] Adicionar dashboard/UI para `audit_trail` (dados acumulam sem leitura)

### Refatoração sugerida
- [ ] Quebrar `server.py` em `db/`, `cache.py`, `errors.py`, `middleware.py`
- [ ] Quebrar `routes/documentos.py` (62 KB): extrair `bp_autentique` para
      `routes/autentique.py` + `services/autentique_service.py`
- [ ] Consolidar `routes/_shared.py` + `routes/helpers.py` (sobrepõem)
- [ ] Remover shim `routes/all_routes.py` (29 linhas) e atualizar imports
- [ ] Remover `get_db`/`row_to_dict` re-definidos como no-op nos blueprints
- [ ] Quebrar `static/css/index.css` (230 KB) por módulo
- [ ] Quebrar `static/js/app.js` (2.266 linhas) por feature
- [ ] Criar testes para `services/openrouter_service.py` e `routes/auth.py`

### Limpeza de código morto
- [ ] Deletar `_apply_all.py`, `_apply_prompts.py` (scripts de migração pontual)
- [ ] Deletar `cloudflared.exe` (65.8 MB — baixar do site da Cloudflare)
- [ ] Deletar `audit_code.py` + `audit_results.txt` (substituir por `ruff`/`bandit`)
- [ ] Deletar `test_empenhos.db`, `server_test.log`
- [ ] Deletar `scratch/`, `pref_extracted/` (UI cyberpunk abandonada)
- [ ] Remover refs ao `app/` no `.gitignore` (linhas 43-45) — diretório não existe
- [ ] Adicionar `.pytest_cache/` ao `.gitignore`
- [ ] Atualizar `README.md` (cita nome antigo `CREDORES_FIXOS_MENSAIR`)
- [ ] Atualizar `MANUAL_DO_PROJETO.md` (740 linhas — descreve estrutura pré-blueprint)

---

## 15. Quirks

- `iniciar.ps1` mata processos na porta 5000 antes de subir (Windows).
- `iniciar.ps1` opcionalmente inicia `cloudflared tunnel --url http://127.0.0.1:5000`
  e copia a URL pública para o clipboard — **anônimo, sem auth, abre a IA
  para a internet**.
- `data.js` é parseado por regex (`_seed_from_data_js`) quando a tabela
  `credores` está vazia — não é import, é string parsing.
- Mural usa SSE (`routes/mural.py`) → exige `gevent` (fallback waitress
  não suporta streaming).
- `server.py:998-1000` mostra traceback no stdout em modo debug.
- `routes/_shared.py` tem prefixo `_` mas é importado por todos os blueprints —
  na verdade é "público" via shim. Considere renomear para `routes/common.py`.
- Backup automático cria commits no branch `backups` — aparece em
  `git branch -a` mas não atrapalha o checkout normal.
- `gevent.monkey.patch_all()` é aplicado mesmo se gevent não vai ser usado
  (decisão do `__main__` é tardia).
- `audit_trail` registra IP do request (`routes/_shared.registrar_auditoria`),
  mas body do request nunca é sanitizado antes de logar erros.

---

## 16. Onde olhar primeiro

| Quero… | Olhe em |
|--------|---------|
| Adicionar um endpoint | `routes/<modulo>.py` (copie padrão de `credores.py`) |
| Mexer no schema | `server.py:init_db()` + `migrate_db()` |
| Mudar config | `config.py` (env) ou tabela `configuracoes` (runtime) |
| Adicionar tarefa IA | `services/ai_prompts.py` (template) + `services/ai_tasks.py` (fachada) |
| Mexer no cache estático | `server.py:744-868` |
| Mexer no auth | `routes/auth.py` + `routes/_shared.py:require_login` |
| Ver o que está no DB | `sqlitebrowser empenhos.db` ou `python -c "import sqlite3; ..."` |
