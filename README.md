# Sistema de Controle de Empenhos Mensais
**Prefeitura Municipal de Inajá**

Sistema web local para gestão de credores fixos, empenhos mensais, RPAs e extratos bancários.

---

## Como iniciar

**Duplo clique em `iniciar.bat`**

Ou pelo terminal:
```bash
python -m pip install -r requirements.txt
python server.py
```

Acesse em: `http://localhost:5000`

> Requer Python 3.8+ e as dependências listadas em `requirements.txt`.

## Configuração

O servidor aceita configuração por variáveis de ambiente:

- `APP_HOST` — host do servidor (`0.0.0.0` por padrão)
- `APP_PORT` — porta HTTP (`5000` por padrão)
- `APP_DEBUG` — ativa debug (`true`, `1`, `yes`, `on`)
- `ADM_PASSWORD` — senha da área administrativa
- `OPENROUTER_DEFAULT_MODEL` — modelo padrão do organizador de extratos
- `OPENROUTER_CHAT_MODEL` — modelo padrão do proxy `/api/ia/chat`
- `OPENROUTER_REFERER` — cabeçalho `HTTP-Referer` enviado ao OpenRouter
- `OPENROUTER_TITLE` — cabeçalho `X-Title` enviado ao OpenRouter

---

## Estrutura do projeto

```
CREDORES_FIXOS_MENSAIR/
├── server.py
├── config.py
├── iniciar.bat
├── requirements.txt
├── exportar_dados.py
├── data.js
├── empenhos.db
├── index.html
├── pages/
│   ├── auditor.html
│   ├── calendario.html
│   ├── cnpj.html
│   ├── despesa-prefeitura.html
│   ├── despesa-relatorios.html
│   ├── extratos.html
│   ├── fornecimento.html
│   ├── gerador-empenho.html
│   ├── manual.html
│   ├── pdf.html
│   ├── renomear.html
│   ├── rpa.html
│   ├── tarefas.html
│   ├── tarifas-bancarias.html
│   └── visualizador.html
│
├── static/
│   ├── css/
│   ├── js/
│   │   ├── app.js
│   │   ├── shared-header.js
│   │   └── despesa/
│   └── img/
│
└── renomer/
    ├── organizador_local_avancado.py
    ├── organizador_ia.py
    ├── file_processor.py
    └── prompts.py
```

---

## API REST

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/api/credores` | Lista credores ativos |
| POST | `/api/credores` | Cria credor |
| PUT | `/api/credores/<id>` | Atualiza credor |
| DELETE | `/api/credores/<id>` | Remove credor (soft delete) |
| GET | `/api/empenhos/<ano>/<mes>` | Empenhos de um mês |
| POST | `/api/empenhos` | Toggle empenho |
| GET | `/api/empenhos/historico/<id>` | Histórico de um credor |
| GET | `/api/logs` | Últimas 100 ações |
| GET | `/api/rpas` | Lista RPAs |
| POST | `/api/rpas` | Cria RPA |
| PUT | `/api/rpas/<id>` | Atualiza RPA |
| DELETE | `/api/rpas/<id>` | Remove RPA |
| POST | `/api/cnpj/buscar` | Consulta CNPJ |
| POST | `/api/extratos/preview` | Pré-visualiza organização de extratos |
| POST | `/api/extratos/organizar` | Organiza extratos |
| POST | `/api/pdf/mesclar` | Mescla PDFs |
| POST | `/api/pdf/dividir` | Divide PDF |
| POST | `/api/pdf/proteger` | Protege PDF com senha |

---

## Atualizar lista de credores via Excel

1. Coloque o arquivo Excel na pasta do projeto
2. Edite `exportar_dados.py` e ajuste o nome do arquivo em `EXCEL_FILE`
3. Execute: `python exportar_dados.py`
4. Reinicie o servidor (o banco será repopulado se estiver vazio)

---

## Dependências Python

- `Flask` — servidor web e API REST
- `PyPDF2` — manipulação de PDFs
- `pdfplumber` — extração de texto de PDF para o módulo `renomer`
- `openpyxl` — leitura de Excel para `exportar_dados.py`

---

## Backup Automatizado

O sistema inclui backup automatizado do banco de dados `empenhos.db` com rotação, verificação de integridade e agendamento diário via Task Scheduler do Windows.

### Scripts de Backup

| Arquivo | Descrição |
|---------|-----------|
| `backup_db.py` | Script Python principal de backup |
| `backup_db.ps1` | Script PowerShell alternativo |
| `backup_agendar.bat` | Agenda backup diário no Task Scheduler |
| `backup_cancelar.bat` | Remove backup agendado |
| `backup_restaurar.bat` | Restaura backup (lista disponíveis) |

### Agendar Backup Diário

**Executar como Administrador:**
```bat
backup_agendar.bat
```

Ou com horário personalizado:
```bat
backup_agendar.bat 03:30
```

**Padrão:**
- Horário: 02:00 AM
- Retenção: 30 dias
- Pasta: `backups/`

### Comandos Úteis

**Executar backup manualmente:**
```bat
python backup_db.py
```

**Verificar último backup:**
```bat
python backup_db.py --verify
```

**Listar backups disponíveis:**
```bat
python backup_db.py --list
```

**Restaurar backup:**
```bat
backup_restaurar.bat
```

**Cancelar agendamento:**
```bat
backup_cancelar.bat
```

### Estrutura de Backups

Os backups são salvos na pasta `backups/` com o formato:
```
backups/
├── empenhos_backup_20260411_020000.db
├── empenhos_backup_20260411_020000.db.sha256
├── empenhos_backup_20260410_020000.db
└── ...
```

Cada backup inclui:
- **Cópia íntegra** do banco de dados
- **Verificação de integridade** via PRAGMA integrity_check
- **Hash SHA256** para validação
- **Rotação automática** (remove backups antigos conforme retenção)

### Logs de Backup

Todos os backups são registrados em `logs/backup.log` com timestamps e status.

### Restauração via Task Scheduler

Para restaurar um backup específico:
```bat
backup_restaurar.bat empenhos_backup_20260411_020000.db
```

O sistema cria automaticamente um backup do banco atual antes de restaurar.

---

## Otimização de Índices do Banco

O sistema inclui 59 índices otimizados para consultas frequentes, incluindo:

### Índices por Tabela

| Tabela | Qtd | Índices Principais |
|--------|-----|-------------------|
| `credores` | 10 | `ativo, departamento`, `ativo, nome`, `cnpj`, `email` |
| `empenhos` | 7 | `ano, mes, empenhado, credor_id`, `credor_id, ano, mes, empenhado` |
| `logs` | 4 | `data, acao`, `credor_id, data` |
| `documentos_centro` | 6 | `categoria, criado_em`, `referencia, criado_em` |
| `rpas` | 5 | `periodo_referencia, cpf_prestador`, `criado_em` |
| `kanban_tasks` | 3 | `status, priority`, `categoria, data_vencimento` |
| `protocolos` | 2 | `status, data_protocolo`, `tipo, direcao` |
| `despesas_linhas` | 2 | `importacao_id`, `importacao_id, id` |

### Script de Gerenciamento

```bash
# Adicionar índices (se não existirem)
python add_indexes.py

# Verificar todos os índices
python add_indexes.py --verify

# Executar benchmark de consultas
python add_indexes.py --benchmark

# Remover índices adicionados por este script
python add_indexes.py --drop
```

### Performance de Consultas (Benchmark)

| Consulta | Tempo Médio |
|----------|-------------|
| Listar credores ativos por departamento | 0.20ms |
| Listar empenhos do mês | 0.07ms |
| Histórico de empenhos de credor | 0.08ms |
| Últimos logs | 0.25ms |
| Documentos por categoria | 0.07ms |
| Tarefas Kanban por status | 0.11ms |

---

## Toast Notifications

O sistema inclui notificações visuais (toast) para feedback de erros e operações:

### Interceptação Automática

Erros HTTP são interceptados **globalmente** e exibidos como toasts:

| Status | Título | Descrição |
|--------|--------|-----------|
| **400** | Requisição Inválida | Verifique os dados enviados |
| **401** | Não Autorizado | Sessão expirada ou credenciais inválidas |
| **403** | Acesso Negado | Sem permissão para este recurso |
| **429** | Muitas Requisições | Aguarde antes de tentar novamente |
| **500** | Erro do Servidor | Erro interno, tente novamente |
| **502** | Serviço Indisponível | Serviço externo indisponível |
| **503** | Serviço Indisponível | Sistema em manutenção |

### Uso em JavaScript

```javascript
// Toasts automáticos (já funcionam sem configuração)
fetch('/api/credores') // Erro 401 → toast automático

// Toasts manuais
Toast.success('Salvo!', 'Dados atualizados.')
Toast.error('Erro', 'Falha ao processar.')
Toast.warning('Atenção', 'Sessão expirando.')
Toast.info('Info', 'Backup concluído.')
```

### Características

- ✅ **Design consistente** — Flat design com dark mode
- ✅ **Auto-dismiss** — Fecha após 5 segundos
- ✅ **Animações suaves** — Slide in/out com progress bar
- ✅ **Acessível** — ARIA labels e roles
- ✅ **Responsivo** — Adapta-se a mobile

### Documentação Completa

Consulte `TOAST_GUIA.md` para guia detalhado.

---

## Migrations de Banco de Dados

O sistema utiliza **Alembic** para versionamento e migração do esquema do banco de dados, permitindo evolução controlada e reversível.

### Comandos Principais

```bash
# Verificar status das migrations
migration_status.bat

# Executar migrations pendentes
migration_rodar.bat

# Criar nova migration
migration_criar.bat "adicionar_coluna_telefone"

# Reverter última migration
migration_reverter.bat
```

### Constraints de Integridade Adicionados

| Tabela | Constraint | Tipo | Descrição |
|--------|-----------|------|-----------|
| `credores` | `ck_credores_valor_positivo` | CHECK | Valor >= 0 |
| `credores` | `ck_credores_ativo_boolean` | CHECK | Ativo IN (0, 1) |
| `credores` | `uq_credores_cnpj` | UNIQUE | CNPJ único |
| `empenhos` | `ck_empenhos_ano_valido` | CHECK | Ano entre 2000-2100 |
| `empenhos` | `ck_empenhos_mes_valido` | CHECK | Mês entre 1-12 |
| `empenhos` | `uq_empenhos_credor_ano_mes` | UNIQUE | Um empenho por credor/mês |
| `logs` | `ck_logs_acao_valida` | CHECK | Ação deve ser válida |
| `rpas` | `ck_rpas_valor_bruto_positivo` | CHECK | Valor bruto >= 0 |
| `rpas` | `uq_rpas_numero` | UNIQUE | Número RPA único |
| `kanban_tasks` | `ck_kanban_status_valido` | CHECK | Status válido |
| `protocolos` | `uq_protocolos_numero` | UNIQUE | Número único |
| `fornecimento_solicitacoes` | `ck_fornecimento_valor_total_positivo` | CHECK | Valor total >= 0 |

### Verificar Constraints

```bash
# Verificar constraints existentes
python apply_constraints.py --verify

# Aplicar constraints ausentes (dry-run)
python apply_constraints.py --dry-run

# Aplicar constraints ausentes
python apply_constraints.py
```

### Foreign Keys com CASCADE

| Tabela | FK | Referência | On Delete |
|--------|----|-----------|-----------|
| `empenhos` | credor_id | credores(id) | CASCADE |
| `logs` | credor_id | credores(id) | SET NULL |
| `kanban_attachments` | task_id | kanban_tasks(id) | CASCADE |
| `protocolo_anexos` | protocolo_id | protocolos(id) | CASCADE |
| `despesas_linhas` | importacao_id | despesas_importacoes(id) | CASCADE |
| `empenhos_linhas` | importacao_id | empenhos_importacoes(id) | CASCADE |
| `autentique_envios` | documento_centro_id | documentos_centro(id) | CASCADE |

### Exemplo: Criar Nova Migration

```bash
# 1. Criar migration
migration_criar.bat "adicionar_coluna_telefone_credores"

# 2. Editar arquivo criado em migrations/versions/
# Adicionar no upgrade():
#   with op.batch_alter_table('credores') as batch_op:
#       batch_op.add_column(sa.Column('telefone', sa.Text(), nullable=True))

# 3. Executar migration
migration_rodar.bat

# 4. Verificar status
migration_status.bat
```

### Histórico de Migrations

```
7efb54210000 → initial_complete_schema_with_constraints (2026-04-11)
  - Criação de todas as 23 tabelas
  - Adição de 32 índices otimizados
  - Constraints NOT NULL, UNIQUE, CHECK
  - Foreign keys com CASCADE DELETE
```
