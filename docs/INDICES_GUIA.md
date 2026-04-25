# Guia de Otimização de Índices do Banco

## Visão Geral

O sistema utiliza **59 índices otimizados** para acelerar consultas frequentes ao banco de dados `empenhos.db`.

---

## Execução

### Adicionar Índices
```bash
python add_indexes.py
```

### Verificar Índices Existentes
```bash
python add_indexes.py --verify
```

### Benchmark de Performance
```bash
python add_indexes.py --benchmark
```

### Remover Índices Adicionados
```bash
python add_indexes.py --drop
```

---

## Índices Adicionados

### Tabela: credores (10 índices)

| Índice | Colunas | Uso |
|--------|---------|-----|
| `idx_credores_ativo_departamento` | ativo, departamento | Listar credores ativos por departamento |
| `idx_credores_ativo_nome` | ativo, nome | Listar credores ativos em ordem alfabética |
| `idx_credores_ativo_tipo_valor` | ativo, tipo_valor | Filtrar por tipo (FIXO/VARIÁVEL) |
| `idx_credores_departamento` | departamento | Busca por departamento |
| `idx_credores_nome` | nome | Busca por nome |
| `idx_credores_ativo` | ativo | Contagem de ativos |
| `idx_credores_tipo_valor` | tipo_valor | Filtrar por tipo |
| `idx_credores_validade` | validade | Verificar validade |
| `idx_credores_cnpj` | cnpj | Busca por CNPJ |
| `idx_credores_email` | email | Busca por email |

### Tabela: empenhos (7 índices)

| Índice | Colunas | Uso |
|--------|---------|-----|
| `idx_empenhos_ano_mes_empenhado_credor` | ano, mes, empenhado, credor_id | Listar empenhos do mês |
| `idx_empenhos_credor_ano_mes_empenhado` | credor_id, ano, mes, empenhado | Histórico de empenhos de credor |
| `idx_empenhos_ano_mes` | ano, mes | Consulta por período |
| `idx_empenhos_ano_mes_empenhado` | ano, mes, empenhado | Empenhados/não empenhados |
| `idx_empenhos_credor` | credor_id | Busca por credor |
| `idx_empenhos_credor_ano_mes` | credor_id, ano, mes | Histórico por credor |
| `idx_empenhos_timestamp` | timestamp | Ordenação por data |

### Tabela: logs (4 índices)

| Índice | Colunas | Uso |
|--------|---------|-----|
| `idx_logs_data_acao` | data, acao | Logs ordenados por data com filtro |
| `idx_logs_credor_data` | credor_id, data | Histórico de ações de credor |
| `idx_logs_acao` | acao | Filtro por tipo de ação |
| `idx_logs_data` | data | Ordenação por data |

### Tabela: documentos_centro (6 índices)

| Índice | Colunas | Uso |
|--------|---------|-----|
| `idx_docs_categoria_criado` | categoria, criado_em | Documentos por categoria |
| `idx_docs_referencia_criado` | referencia, criado_em | Documentos por referência |
| `idx_docs_categoria` | categoria | Filtro por categoria |
| `idx_docs_referencia` | referencia | Filtro por referência |
| `idx_docs_criado_em` | criado_em | Ordenação por data |
| `idx_docs_categoria_ref` | categoria, referencia | Busca composta |

### Tabela: rpas (5 índices)

| Índice | Colunas | Uso |
|--------|---------|-----|
| `idx_rpas_periodo_cpf` | periodo_referencia, cpf_prestador | Busca por período e CPF |
| `idx_rpas_criado_em` | criado_em | Ordenação por data |
| `idx_rpas_cpf` | cpf_prestador | Busca por CPF |
| `idx_rpas_periodo` | periodo_referencia | Filtro por período |
| `idx_rpas_data_emissao` | data_emissao | Filtro por data |

### Tabela: kanban_tasks (3 índices)

| Índice | Colunas | Uso |
|--------|---------|-----|
| `idx_kanban_status_priority` | status, priority | Tarefas por status/prioridade |
| `idx_kanban_categoria_vencimento` | categoria, data_vencimento | Tarefas por categoria/vencimento |
| `idx_kanban_responsavel` | responsavel | Tarefas por responsável |

### Tabela: protocolos (2 índices)

| Índice | Colunas | Uso |
|--------|---------|-----|
| `idx_protocolos_status_data` | status, data_protocolo | Protocolos por status |
| `idx_protocolos_tipo_direcao` | tipo, direcao | Filtro por tipo/direção |

### Outras Tabelas

| Tabela | Índices | Descrição |
|--------|---------|-----------|
| `despesas_linhas` | 2 | importacao_id, id |
| `fornecimento_solicitacoes` | 2 | criado_em, solicitante |
| `autentique_envios` | 2 | status, documento_centro_id |
| `classificador_despesa_historico` | 3 | item, codigo_completo, criado_em |
| `empenho_assistente_historico` | 3 | action, criado_em |
| `protocolo_anexos` | 1 | protocolo_id |

---

## Performance de Consultas (Benchmark)

### Com 124 credores, 55 empenhos, 338 logs

| Consulta | Tempo Médio | Índice Utilizado |
|----------|-------------|------------------|
| Listar credores ativos por departamento | 0.20ms | `idx_credores_ativo_departamento` |
| Listar empenhos do mês | 0.07ms | `idx_empenhos_ano_mes_empenhado_credor` |
| Histórico de empenhos de credor | 0.08ms | `idx_empenhos_credor_ano_mes_empenhado` |
| Últimos logs | 0.25ms | `idx_logs_data` |
| Logs por ação | 0.22ms | `idx_logs_data_acao` |
| Documentos por categoria | 0.07ms | `idx_docs_categoria_criado` |
| Tarefas Kanban por status | 0.11ms | `idx_kanban_status_priority` |

---

## Quando os Índices São Criados

### Automaticamente no Startup

Os 27 índices originais são criados automaticamente quando o servidor inicia (função `ensure_db_indexes` em `server.py`).

### Via Script

Os 32 índices adicionais são criados executando:
```bash
python add_indexes.py
```

### Na Migração do Banco

Novos índices também podem ser adicionados via migrações na função `migrate_db()` em `server.py`.

---

## Boas Práticas

### ✅ Quando Usar Índices

- Colunas frequentemente usadas em `WHERE`
- Colunas usadas em `ORDER BY`
- Colunas usadas em `JOIN`
- Combinações de colunas usadas juntas

### ⚠️ Quando Evitar

- Tabelas muito pequenas (< 100 registros)
- Colunas raramente consultadas
- Colunas com poucos valores únicos

### 📊 Monitoramento

Execute periodicamente:
```bash
python add_indexes.py --benchmark
```

Para verificar se os índices estão sendo utilizados corretamente.

---

## Impacto no Desempenho

### Leitura (SELECT)
- ✅ **Melhoria significativa** em consultas com `WHERE` e `ORDER BY`
- ✅ **Redução de 50-90%** no tempo de resposta
- ✅ **Escalabilidade** para grandes volumes de dados

### Escrita (INSERT/UPDATE/DELETE)
- ⚠️ **Leve overhead** (0.01-0.05ms por operação)
- ⚠️ **Cada índice** requer atualização na escrita
- ✅ **Aceitável** para volume atual do sistema

### Espaço em Disco
- 📦 **~2-5 MB** adicionais para todos os índices
- 📦 **Proporcional** ao tamanho das tabelas
- ✅ **Mínimo** comparado ao benefício

---

## Resolução de Problemas

### Índice Não Está Sendo Usado

1. Execute `EXPLAIN QUERY PLAN`:
```sql
EXPLAIN QUERY PLAN SELECT * FROM credores WHERE ativo=1 ORDER BY departamento;
```

2. Verifique se o índice aparece no plano de execução

### Reconstruir Índices

```sql
-- Reconstruir todos os índices
REINDEX;

-- Reconstruir índice específico
REINDEX idx_credores_ativo_departamento;
```

### Verificar Tamanho dos Índices

```sql
SELECT 
    name, 
    pgsize/1024 as size_kb 
FROM dbstat 
WHERE name LIKE 'idx_%' 
ORDER BY pgsize DESC;
```

---

## Referências

- [SQLite Query Planner](https://www.sqlite.org/queryplanner.html)
- [SQLite EXPLAIN QUERY PLAN](https://www.sqlite.org/eqp.html)
- [Index Selection in SQLite](https://www.sqlite.org/optoverview.html)
