# 📋 Checklist de Melhorias - Sistema de Empenhos

**Data de Criação:** 14/04/2026  
**Última Atualização:** 14/04/2026 13:37

---

## 🎯 Quick Wins (Hoje - 30 minutos)

### Instalação Automática
- [ ] Executar `instalar_melhorias.bat` (Windows) ou `./instalar_melhorias.sh` (Linux/Mac)

### OU Instalação Manual

#### 1. Backup de Segurança
- [ ] Executar `python backup_db.py`
- [ ] Verificar backup em `backups/`

#### 2. Índices Críticos
- [ ] Executar `python add_critical_indexes.py`
- [ ] Verificar saída: 8/8 índices adicionados
- [ ] Executar `python add_critical_indexes.py --benchmark`
- [ ] Anotar tempos de query (antes/depois)

#### 3. Configuração Segura
- [ ] Copiar `.env.example` para `.env`
- [ ] Editar `.env`:
  - [ ] Gerar SECRET_KEY forte (32+ caracteres)
  - [ ] Definir ADM_PASSWORD forte
  - [ ] Configurar OPENROUTER_API_KEY (se usar IA)
  - [ ] Ajustar APP_DEBUG=false para produção

#### 4. Health Check
- [ ] Abrir `app/__init__.py`
- [ ] Adicionar após outros imports:
  ```python
  from app.routes.health import bp as health_bp
  ```
- [ ] Adicionar após outros register_blueprint:
  ```python
  app.register_blueprint(health_bp)
  ```
- [ ] Salvar arquivo

#### 5. Validação
- [ ] Reiniciar servidor: `python server.py`
- [ ] Acessar http://localhost:5000/health
- [ ] Verificar resposta JSON com status "healthy"
- [ ] Acessar http://localhost:5000/health/metrics
- [ ] Testar funcionalidades principais do sistema

---

## 📊 Métricas de Sucesso

### Performance (anotar antes/depois)

**Antes:**
- Startup: _____ ms
- Query credores: _____ ms
- Query empenhos: _____ ms
- Memória: _____ MB

**Depois:**
- Startup: _____ ms (esperado: -60%)
- Query credores: _____ ms (esperado: -70%)
- Query empenhos: _____ ms (esperado: -70%)
- Memória: _____ MB (esperado: -50%)

### Funcionalidades
- [ ] Listar credores funciona
- [ ] Filtrar por departamento funciona
- [ ] Buscar por nome funciona
- [ ] Criar novo credor funciona
- [ ] Empenhar/desempenhar funciona
- [ ] Histórico de empenhos funciona
- [ ] Logs aparecem corretamente

---

## 📅 Esta Semana (8 horas)

### Consolidar Arquitetura
- [ ] Ler seção "Consolidar Arquitetura" em PLANO_ACAO_MELHORIAS.md
- [ ] Fazer backup completo: `git add -A && git commit -m "backup: antes de consolidar"`
- [ ] Mover lógica de `server.py` para `app/__init__.py`
- [ ] Simplificar `server.py` (apenas ponto de entrada)
- [ ] Testar todas as rotas
- [ ] Commit: `git commit -m "refactor: consolida arquitetura em app/"`

### Implementar Testes Básicos
- [ ] Instalar pytest: `pip install pytest pytest-cov pytest-flask`
- [ ] Criar estrutura `tests/`
- [ ] Copiar exemplos de `PLANO_ACAO_MELHORIAS.md`
- [ ] Criar `tests/conftest.py`
- [ ] Criar `tests/test_credores.py`
- [ ] Executar: `pytest tests/ -v`
- [ ] Verificar cobertura: `pytest tests/ --cov=app --cov-report=html`
- [ ] Commit: `git commit -m "test: adiciona testes basicos"`

### Separar Services
- [ ] Criar `app/services/base_service.py`
- [ ] Criar `app/services/credores_service.py`
- [ ] Mover validações de `app/routes/credores.py` para service
- [ ] Atualizar rotas para usar service
- [ ] Testar funcionalidades
- [ ] Commit: `git commit -m "refactor: separa services das rotas"`

### Adicionar Rate Limiting
- [ ] Instalar: `pip install Flask-Limiter`
- [ ] Adicionar ao `requirements.txt`
- [ ] Configurar em `app/__init__.py`
- [ ] Aplicar limites em rotas críticas
- [ ] Testar com múltiplas requisições
- [ ] Commit: `git commit -m "feat: adiciona rate limiting"`

---

## 🚀 Próximas 2 Semanas (16 horas)

### Otimizar Cache de Arquivos
- [ ] Implementar lazy loading com LRU cache
- [ ] Testar startup time
- [ ] Medir uso de memória
- [ ] Commit: `git commit -m "perf: otimiza cache de arquivos estaticos"`

### Connection Pool
- [ ] Implementar SQLitePool
- [ ] Configurar pool_size via .env
- [ ] Testar sob carga
- [ ] Commit: `git commit -m "perf: adiciona connection pool"`

### Logging Estruturado
- [ ] Implementar JSONFormatter
- [ ] Configurar níveis de log
- [ ] Adicionar contexto às mensagens
- [ ] Commit: `git commit -m "feat: adiciona logging estruturado"`

### Métricas de Performance
- [ ] Adicionar endpoint /health/performance
- [ ] Coletar métricas de requests
- [ ] Dashboard simples de métricas
- [ ] Commit: `git commit -m "feat: adiciona metricas de performance"`

---

## 📝 Notas e Observações

### Problemas Encontrados
```
Data: ___/___/___
Problema: _________________________________
Solução: __________________________________
```

### Melhorias Adicionais Identificadas
```
1. _______________________________________
2. _______________________________________
3. _______________________________________
```

### Dúvidas para Resolver
```
1. _______________________________________
2. _______________________________________
3. _______________________________________
```

---

## ✅ Status Geral

- [ ] Quick Wins implementados
- [ ] Melhorias da semana implementadas
- [ ] Melhorias de 2 semanas implementadas
- [ ] Documentação atualizada
- [ ] Testes passando
- [ ] Performance melhorada
- [ ] Sistema em produção

---

## 🎓 Recursos

### Documentação
- MELHORIAS_SUGERIDAS.md - Guia completo
- PLANO_ACAO_MELHORIAS.md - Plano detalhado
- RESUMO_EXECUTIVO.md - Visão geral

### Scripts
- `instalar_melhorias.bat` - Instalação automática (Windows)
- `instalar_melhorias.sh` - Instalação automática (Linux/Mac)
- `add_critical_indexes.py` - Gerenciamento de índices
- `backup_db.py` - Backup do banco

### Comandos Úteis
```bash
# Verificar índices
python add_critical_indexes.py --verify

# Benchmark
python add_critical_indexes.py --benchmark

# Health check
curl http://localhost:5000/health

# Métricas
curl http://localhost:5000/health/metrics

# Testes
pytest tests/ -v --cov=app

# Backup
python backup_db.py
```

---

**Última Revisão:** ___/___/___  
**Responsável:** _________________  
**Status:** [ ] Em Andamento [ ] Concluído
