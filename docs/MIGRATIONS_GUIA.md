# Guia Completo de Migrations — empenhos.db

## Visão Geral

O sistema utiliza **Alembic** para gerenciar migrations de banco de dados, permitindo:
- ✅ Versionamento do esquema
- ✅ Evolução controlada e reversível
- ✅ Constraints de integridade (NOT NULL, UNIQUE, CHECK)
- ✅ Foreign keys com CASCADE DELETE
- ✅ Rollback seguro

---

## Instalação

```bash
pip install -r requirements.txt
```

Dependências adicionadas:
- `alembic>=1.13,<2.0`
- `SQLAlchemy>=2.0,<3.0`

---

## Comandos Rápidos (Windows)

| Ação | Comando |
|------|---------|
| Ver status | `migration_status.bat` |
| Executar migrations | `migration_rodar.bat` |
| Criar migration | `migration_criar.bat "descricao"` |
| Reverter migration | `migration_reverter.bat` |

---

## Comandos Alembic (CLI)

```bash
# Ver status atual
python -m alembic current

# Ver histórico
python -m alembic history --verbose

# Executar upgrade
python -m alembic upgrade head

# Reverter último
python -m alembic downgrade -1

# Criar nova migration
python -m alembic revision -m "descricao"

# Ver migrations pendentes
python -m alembic heads
```

---

## Estrutura de Arquivos

```
CREDORES_FIXOS_MENSAIR/
├── alembic.ini                    # Configuração do Alembic
├── migrations/
│   ├── env.py                     # Ambiente do Alembic
│   ├── EXEMPLO_TEMPLATE.py        # Template de exemplo
│   └── versions/
│       └── 7efb54210000_initial_complete_schema_with_constraints.py
├── migration_rodar.bat
├── migration_criar.bat
├── migration_reverter.bat
├── migration_status.bat
└── apply_constraints.py
```

---

## Migration Inicial

### 7efb54210000 — initial_complete_schema_with_constraints

**Data:** 2026-04-11  
**Tipo:** Completa (cria todas as tabelas)

**Conteúdo:**
- 23 tabelas criadas
- 59 índices otimizados
- 30+ constraints (CHECK, UNIQUE, NOT NULL)
- 7 foreign keys com CASCADE DELETE

---

## Constraints de Integridade

### Tabela: credores

| Constraint | Tipo | Condição | Descrição |
|-----------|------|----------|-----------|
| `ck_credores_valor_positivo` | CHECK | `valor >= 0` | Valor deve ser positivo |
| `ck_credores_ativo_boolean` | CHECK | `ativo IN (0, 1)` | Ativo é booleano |
| `ck_credores_tipo_valor_valido` | CHECK | `tipo_valor IN (...)` | Tipo deve ser válido |
| `uq_credores_cnpj` | UNIQUE | `cnpj` | CNPJ único |

### Tabela: empenhos

| Constraint | Tipo | Condição | Descrição |
|-----------|------|----------|-----------|
| `ck_empenhos_ano_valido` | CHECK | `ano >= 2000 AND ano <= 2100` | Ano válido |
| `ck_empenhos_mes_valido` | CHECK | `mes >= 1 AND mes <= 12` | Mês válido |
| `ck_empenhos_empenhado_boolean` | CHECK | `empenhado IN (0, 1)` | Empenhado é booleano |
| `uq_empenhos_credor_ano_mes` | UNIQUE | `credor_id, ano, mes` | Um empenho por mês |

### Tabela: logs

| Constraint | Tipo | Condição | Descrição |
|-----------|------|----------|-----------|
| `ck_logs_acao_valida` | CHECK | `acao IN (...)` | Ação deve ser válida |

### Tabela: rpas

| Constraint | Tipo | Condição | Descrição |
|-----------|------|----------|-----------|
| `ck_rpas_valor_bruto_positivo` | CHECK | `valor_bruto >= 0` | Valor bruto positivo |
| `ck_rpas_valor_liquido_positivo` | CHECK | `valor_liquido >= 0` | Valor líquido positivo |
| `uq_rpas_numero` | UNIQUE | `numero_rpa` | Número RPA único |

### Tabela: kanban_tasks

| Constraint | Tipo | Condição | Descrição |
|-----------|------|----------|-----------|
| `ck_kanban_status_valido` | CHECK | `status IN (...)` | Status válido |
| `ck_kanban_priority_valida` | CHECK | `priority IN (...)` | Prioridade válida |

### Tabela: protocolos

| Constraint | Tipo | Condição | Descrição |
|-----------|------|----------|-----------|
| `uq_protocolos_numero` | UNIQUE | `numero` | Número único |
| `ck_protocolos_direcao_valida` | CHECK | `direcao IN (...)` | Direção válida |
| `ck_protocolos_status_valido` | CHECK | `status IN (...)` | Status válido |

---

## Foreign Keys

### CASCADE DELETE

| Tabela | Coluna FK | Referência | On Delete |
|--------|-----------|-----------|-----------|
| `empenhos` | credor_id | credores(id) | CASCADE |
| `kanban_attachments` | task_id | kanban_tasks(id) | CASCADE |
| `protocolo_anexos` | protocolo_id | protocolos(id) | CASCADE |
| `despesas_linhas` | importacao_id | despesas_importacoes(id) | CASCADE |
| `empenhos_linhas` | importacao_id | empenhos_importacoes(id) | CASCADE |
| `autentique_envios` | documento_centro_id | documentos_centro(id) | CASCADE |

### SET NULL

| Tabela | Coluna FK | Referência | On Delete |
|--------|-----------|-----------|-----------|
| `logs` | credor_id | credores(id) | SET NULL |

---

## Como Criar Nova Migration

### Exemplo 1: Adicionar Coluna

```bash
# 1. Criar migration
migration_criar.bat "adicionar_coluna_telefone"

# 2. Editar arquivo em migrations/versions/
```

**Conteúdo do upgrade():**
```python
def upgrade():
    with op.batch_alter_table('credores') as batch_op:
        batch_op.add_column(sa.Column('telefone', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('ativo', sa.Integer(), server_default='1', nullable=False))
        batch_op.create_check_constraint(
            'ck_credores_ativo_boolean',
            'credores',
            'ativo IN (0, 1)'
        )

def downgrade():
    with op.batch_alter_table('credores') as batch_op:
        batch_op.drop_column('telefone')
        batch_op.drop_column('ativo')
```

```bash
# 3. Executar migration
migration_rodar.bat
```

### Exemplo 2: Adicionar Índice

```python
def upgrade():
    op.create_index('idx_credores_telefone', 'credores', ['telefone'])

def downgrade():
    op.drop_index('idx_credores_telefone')
```

### Exemplo 3: Adicionar Constraint UNIQUE

```python
def upgrade():
    with op.batch_alter_table('credores') as batch_op:
        batch_op.create_unique_constraint('uq_credores_email', 'credores', ['email'])

def downgrade():
    with op.batch_alter_table('credores') as batch_op:
        batch_op.drop_constraint('uq_credores_email', type_='unique')
```

### Exemplo 4: Adicionar Foreign Key

```python
def upgrade():
    with op.batch_alter_table('logs') as batch_op:
        batch_op.create_foreign_key(
            'fk_logs_credor',
            'credores',
            ['credor_id'],
            ['id'],
            ondelete='SET NULL'
        )

def downgrade():
    with op.batch_alter_table('logs') as batch_op:
        batch_op.drop_constraint('fk_logs_credor', type_='foreignkey')
```

### Exemplo 5: Criar Tabela Completa

```python
def upgrade():
    op.create_table(
        'nova_tabela',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('nome', sa.Text(), nullable=False),
        sa.Column('valor', sa.Float(), server_default='0', nullable=False),
        sa.Column('ativo', sa.Integer(), server_default='1', nullable=False),
        sa.CheckConstraint('valor >= 0', name='ck_nova_tabela_valor_positivo'),
        sa.CheckConstraint('ativo IN (0, 1)', name='ck_nova_tabela_ativo_boolean'),
        sa.UniqueConstraint('nome', name='uq_nova_tabela_nome'),
    )
    op.create_index('idx_nova_tabela_nome', 'nova_tabela', ['nome'])

def downgrade():
    op.drop_index('idx_nova_tabela_nome')
    op.drop_table('nova_tabela')
```

---

## Verificar Constraints

```bash
# Verificar constraints existentes
python apply_constraints.py --verify

# Aplicar constraints ausentes (dry-run)
python apply_constraints.py --dry-run

# Aplicar constraints ausentes
python apply_constraints.py
```

---

## Boas Práticas

### ✅ Sempre Faça

1. **Backup antes de migrations**
   ```bash
   python backup_db.py
   ```

2. **Teste em banco de desenvolvimento**
   - Nunca rode migrations em produção sem testar

3. **Implemente downgrade()**
   - Toda migration deve ser reversível

4. **Use batch_alter_table para SQLite**
   ```python
   with op.batch_alter_table('tabela') as batch_op:
       batch_op.add_column(...)
   ```

5. **Versione migrations no Git**
   - Arquivos em `migrations/versions/` devem ser commitados

### ⚠️ Evite

1. **Migrations destrutivas**
   - Evite `DROP TABLE` em produção

2. **Alterar tipo de coluna**
   - SQLite requer recreação da tabela

3. **Migrations irreversíveis**
   - Sempre implemente downgrade()

4. **Dados inválidos**
   - Valide dados antes de adicionar constraints

---

## Resolução de Problemas

### Migration Falha ao Executar

```bash
# Ver status
migration_status.bat

# Ver logs
type migrations\README

# Reverter
migration_reverter.bat

# Corrigir e re-executar
migration_rodar.bat
```

### Constraint Já Existe

```bash
# Verificar
python apply_constraints.py --verify

# Se já existe, migration vai ignorar (IF NOT EXISTS)
```

### Foreign Key Violation

```bash
# Verificar violações
python -c "import sqlite3; conn = sqlite3.connect('empenhos.db'); conn.execute('PRAGMA foreign_key_check'); print(conn.execute('PRAGMA foreign_key_check').fetchall())"
```

### Recriar Banco do Zero

```bash
# Deletar banco antigo
del empenhos.db

# Executar migrations
migration_rodar.bat

# Aplicar constraints
python apply_constraints.py
```

---

## Histórico de Migrations

### 7efb54210000 — initial_complete_schema_with_constraints

**Data:** 2026-04-11  
**Tipo:** Completa  
**Status:** ✅ Executada

**Alterações:**
- Criação de 23 tabelas
- 59 índices otimizados
- 30+ constraints (CHECK, UNIQUE, NOT NULL)
- 7 foreign keys com CASCADE DELETE

**Próxima Migration:** _(a ser criada)_

---

## Referências

- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [SQLite ALTER TABLE](https://www.sqlite.org/lang_altertable.html)
- [SQLAlchemy Core](https://docs.sqlalchemy.org/en/20/core/)
