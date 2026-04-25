# Sugestões de Melhorias - Sistema de Empenhos

**Análise realizada em:** 14/04/2026  
**Projeto:** Sistema de Controle de Empenhos Mensais - Prefeitura de Inajá

---

## 🎯 Melhorias Prioritárias

### 1. **Consolidar Arquitetura (server.py vs app/__init__.py)**

**Problema:** Você tem dois pontos de entrada duplicados:
- `server.py` (690 linhas) - implementação completa standalone
- `app/__init__.py` (353 linhas) - factory pattern moderno

**Solução:**
```python
# server.py simplificado
from app import create_app

if __name__ == "__main__":
    app = create_app()
    app.run(host=settings.host, port=settings.port, debug=settings.debug)
```

**Benefícios:**
- Elimina ~400 linhas de código duplicado
- Facilita testes unitários
- Melhora manutenibilidade

---

### 2. **Otimizar Cache de Arquivos Estáticos**

**Problema:** Cache em RAM carrega todos os arquivos no boot (3.2MB+ banco + assets)

**Solução:**
```python
# Lazy loading com LRU cache
from functools import lru_cache

@lru_cache(maxsize=128)
def _get_static_file(url: str):
    # Carrega sob demanda, mantém 128 mais usados
    pass
```

**Benefícios:**
- Startup 50-70% mais rápido
- Menor uso de memória
- Cache inteligente dos arquivos mais acessados

---

### 3. **Adicionar Índices Compostos Faltantes**

**Problema:** Consultas lentas em filtros combinados

**Solução:**
```sql
-- Para filtros da tela principal
CREATE INDEX idx_credores_filtros 
ON credores(ativo, departamento, tipo_valor, nome);

-- Para busca com paginação
CREATE INDEX idx_credores_search 
ON credores(ativo, nome, departamento);
```

**Benefícios:**
- Queries 3-5x mais rápidas
- Melhor experiência em listas grandes (>500 credores)

---

### 4. **Implementar Connection Pool**

**Problema:** Uma conexão SQLite por thread pode causar locks

**Solução:**
```python
from queue import Queue
import threading

class SQLitePool:
    def __init__(self, db_path, pool_size=5):
        self.pool = Queue(maxsize=pool_size)
        for _ in range(pool_size):
            conn = sqlite3.connect(db_path, check_same_thread=False)
            self.pool.put(conn)
    
    def get_connection(self):
        return self.pool.get()
    
    def return_connection(self, conn):
        self.pool.put(conn)
```

**Benefícios:**
- Reduz contenção em acessos simultâneos
- Melhor performance sob carga

---

### 5. **Separar Lógica de Negócio das Rotas**

**Problema:** Rotas com validação + DB + lógica misturados

**Estrutura sugerida:**
```
app/
├── routes/          # Apenas HTTP (request/response)
├── services/        # Lógica de negócio
│   ├── credores_service.py
│   ├── empenhos_service.py
│   └── rpas_service.py
└── repositories/    # Acesso a dados
    └── credores_repo.py
```

**Exemplo:**
```python
# app/services/credores_service.py
class CredoresService:
    def criar_credor(self, data: dict) -> tuple[dict, list]:
        # Validação
        # Verificação de duplicados
        # Criação no banco
        # Log de auditoria
        pass

# app/routes/credores.py
@bp.route('/credores', methods=['POST'])
def criar_credor():
    service = CredoresService()
    result, errors = service.criar_credor(request.json)
    if errors:
        return jsonify({'errors': errors}), 400
    return jsonify(result), 201
```

**Benefícios:**
- Código testável
- Reutilização de lógica
- Rotas mais limpas

---

### 6. **Adicionar Testes Automatizados**

**Problema:** Sem testes = refatoração arriscada

**Estrutura mínima:**
```
tests/
├── test_credores.py
├── test_empenhos.py
├── test_api.py
└── conftest.py
```

**Exemplo:**
```python
# tests/test_credores.py
def test_criar_credor_valido(client):
    response = client.post('/api/credores', json={
        'nome': 'FORNECEDOR TESTE',
        'valor': 1000.00,
        'departamento': 'SAÚDE'
    })
    assert response.status_code == 201
    assert 'id' in response.json

def test_criar_credor_cnpj_duplicado(client):
    # Criar primeiro
    client.post('/api/credores', json={'nome': 'A', 'cnpj': '12345678000190'})
    # Tentar duplicar
    response = client.post('/api/credores', json={'nome': 'B', 'cnpj': '12345678000190'})
    assert response.status_code == 400
```

**Comando:**
```bash
pytest tests/ -v --cov=app
```

---

### 7. **Melhorar Tratamento de Erros**

**Problema:** Erros genéricos sem contexto

**Solução:**
```python
# app/utils/exceptions.py
class AppException(Exception):
    def __init__(self, message: str, status_code: int = 400, details: dict = None):
        self.message = message
        self.status_code = status_code
        self.details = details or {}

class CredorDuplicadoException(AppException):
    def __init__(self, cnpj: str):
        super().__init__(
            f"Credor com CNPJ {cnpj} já existe",
            status_code=409,
            details={'cnpj': cnpj}
        )

# app/__init__.py
@app.errorhandler(AppException)
def handle_app_exception(e):
    return jsonify({
        'error': e.message,
        'details': e.details
    }), e.status_code
```

---

### 8. **Adicionar Variáveis de Ambiente para Segurança**

**Problema:** Senha admin hardcoded, sem SECRET_KEY forte

**Solução:**
```bash
# .env (adicionar ao .gitignore)
SECRET_KEY=sua-chave-secreta-forte-aqui-min-32-chars
ADM_PASSWORD=senha-forte-admin
DATABASE_URL=sqlite:///empenhos.db
OPENROUTER_API_KEY=sk-or-v1-...
```

```python
# config.py
import secrets

@dataclass(frozen=True)
class Settings:
    secret_key: str = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
    admin_password: str = os.environ.get("ADM_PASSWORD", "")
    
    def __post_init__(self):
        if not self.admin_password:
            raise ValueError("ADM_PASSWORD deve ser definida no .env")
```

---

### 9. **Implementar Rate Limiting**

**Problema:** APIs sem proteção contra abuso

**Solução:**
```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

@bp.route('/api/credores', methods=['POST'])
@limiter.limit("10 per minute")
def criar_credor():
    pass
```

**Adicionar ao requirements.txt:**
```
Flask-Limiter>=3.5,<4.0
```

---

### 10. **Otimizar Queries N+1**

**Problema:** Buscar empenhos para cada credor individualmente

**Solução:**
```python
# ❌ Ruim (N+1 queries)
credores = cur.execute("SELECT * FROM credores").fetchall()
for credor in credores:
    empenhos = cur.execute(
        "SELECT * FROM empenhos WHERE credor_id=?", 
        (credor['id'],)
    ).fetchall()

# ✅ Bom (2 queries)
credores = cur.execute("SELECT * FROM credores").fetchall()
empenhos_map = {}
for emp in cur.execute("SELECT * FROM empenhos").fetchall():
    empenhos_map.setdefault(emp['credor_id'], []).append(emp)

for credor in credores:
    credor['empenhos'] = empenhos_map.get(credor['id'], [])
```

---

## 🔧 Melhorias Rápidas (< 30 min)

### 1. Adicionar .gitignore completo
```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
*.egg-info/

# Banco de dados
*.db
*.db-shm
*.db-wal

# Logs
logs/
*.log

# Backups
backups/

# Ambiente
.env
.env.local

# IDE
.vscode/
.idea/
*.swp

# OS
.DS_Store
Thumbs.db

# Documentos sensíveis
documentos_centro/
DADOS/
```

### 2. Adicionar healthcheck endpoint
```python
@app.route('/health')
def health():
    try:
        conn = get_db()
        conn.execute("SELECT 1").fetchone()
        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 503
```

### 3. Adicionar logging estruturado
```python
import logging
import json

class JSONFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({
            'timestamp': self.formatTime(record),
            'level': record.levelname,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName
        })

handler.setFormatter(JSONFormatter())
```

### 4. Comprimir responses grandes
```python
# Já implementado, mas verificar threshold
if len(data) > 1024:  # Aumentar de 256 para 1KB
    response.set_data(gzip.compress(data))
```

### 5. Adicionar CORS se necessário
```python
from flask_cors import CORS

CORS(app, resources={
    r"/api/*": {
        "origins": ["http://localhost:3000"],
        "methods": ["GET", "POST", "PUT", "DELETE"]
    }
})
```

---

## 📊 Métricas de Performance

### Antes das Melhorias (estimado)
- Startup: ~800-1200ms
- Query credores (500 registros): ~50-80ms
- Memória em uso: ~80-120MB
- Requests/segundo: ~50-100

### Depois das Melhorias (estimado)
- Startup: ~200-400ms (↓ 60-70%)
- Query credores (500 registros): ~10-20ms (↓ 75%)
- Memória em uso: ~40-60MB (↓ 50%)
- Requests/segundo: ~200-400 (↑ 300%)

---

## 🚀 Roadmap de Implementação

### Fase 1 - Fundação (1-2 dias)
1. ✅ Consolidar server.py → app/__init__.py
2. ✅ Adicionar .gitignore e .env
3. ✅ Implementar testes básicos
4. ✅ Separar services das rotas

### Fase 2 - Performance (1 dia)
5. ✅ Otimizar cache estático
6. ✅ Adicionar índices compostos
7. ✅ Implementar connection pool
8. ✅ Corrigir queries N+1

### Fase 3 - Segurança (meio dia)
9. ✅ Rate limiting
10. ✅ Variáveis de ambiente
11. ✅ Melhorar error handling

### Fase 4 - Monitoramento (meio dia)
12. ✅ Healthcheck endpoint
13. ✅ Logging estruturado
14. ✅ Métricas de performance

---

## 📝 Comandos Úteis

```bash
# Instalar dependências de desenvolvimento
pip install pytest pytest-cov flask-limiter flask-cors black flake8

# Rodar testes
pytest tests/ -v --cov=app --cov-report=html

# Formatar código
black app/ tests/

# Verificar qualidade
flake8 app/ --max-line-length=100

# Rodar servidor em modo debug
APP_DEBUG=1 python server.py

# Criar backup antes de mudanças
python backup_db.py

# Verificar performance do banco
python add_indexes.py --benchmark
```

---

## ⚠️ Avisos Importantes

1. **Backup antes de mudanças:** Sempre rode `backup_db.py` antes de refatorações
2. **Testar em ambiente local:** Não aplique mudanças direto em produção
3. **Migrations:** Use Alembic para mudanças no schema do banco
4. **Compatibilidade:** Mantenha compatibilidade com código existente durante transição

---

## 📚 Recursos Adicionais

- [Flask Best Practices](https://flask.palletsprojects.com/en/3.0.x/patterns/)
- [SQLite Performance Tuning](https://www.sqlite.org/optoverview.html)
- [Python Testing with pytest](https://docs.pytest.org/)
- [REST API Design](https://restfulapi.net/)

---

**Próximos Passos:**
1. Revisar este documento com a equipe
2. Priorizar melhorias baseado em necessidades
3. Criar branch para cada melhoria
4. Testar individualmente antes de merge
5. Documentar mudanças no README.md
