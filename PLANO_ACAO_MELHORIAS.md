# Plano de Ação - Melhorias Prioritárias

**Data:** 14/04/2026  
**Objetivo:** Implementar melhorias de alto impacto com baixo risco

---

## 🎯 Quick Wins (Implementar Hoje)

### 1. Adicionar .gitignore Completo
**Tempo:** 5 minutos  
**Impacto:** Alto (segurança)  
**Risco:** Nenhum

```bash
# Criar arquivo
cat > .gitignore << 'EOF'
__pycache__/
*.py[cod]
*.db
*.db-shm
*.db-wal
logs/
*.log
backups/
.env
.env.local
.vscode/
.idea/
documentos_centro/
DADOS/
EOF

git add .gitignore
git commit -m "chore: adiciona .gitignore completo"
```

---

### 2. Criar Arquivo .env para Configurações Sensíveis
**Tempo:** 10 minutos  
**Impacto:** Alto (segurança)  
**Risco:** Baixo

```bash
# Criar .env
cat > .env << 'EOF'
# Servidor
APP_HOST=0.0.0.0
APP_PORT=5000
APP_DEBUG=false
APP_RELOADER=false

# Segurança
SECRET_KEY=gerar-chave-forte-aqui-min-32-caracteres
ADM_PASSWORD=sua-senha-admin-forte

# OpenRouter (se usar)
OPENROUTER_API_KEY=
OPENROUTER_DEFAULT_MODEL=openai/gpt-4o-mini
OPENROUTER_CHAT_MODEL=meta-llama/llama-3.3-70b-instruct:free
EOF

# Adicionar .env.example para documentação
cp .env .env.example
# Limpar valores sensíveis do .env.example
```

---

### 3. Adicionar Endpoint de Health Check
**Tempo:** 10 minutos  
**Impacto:** Médio (monitoramento)  
**Risco:** Nenhum

Adicionar em `app/__init__.py` ou criar `app/routes/health.py`:

```python
from flask import Blueprint, jsonify
from datetime import datetime
import sqlite3

bp = Blueprint('health', __name__)

@bp.route('/health')
def health_check():
    """Endpoint para verificar saúde do sistema."""
    try:
        from app.utils.db import get_db
        conn = get_db()
        conn.execute("SELECT 1").fetchone()
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'database': 'connected',
            'version': '1.0.0'
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'timestamp': datetime.now().isoformat(),
            'error': str(e)
        }), 503

@bp.route('/health/ready')
def readiness_check():
    """Verifica se o sistema está pronto para receber requisições."""
    try:
        from app.utils.db import get_db
        conn = get_db()
        
        # Verifica se tabelas principais existem
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        
        required_tables = {'credores', 'empenhos', 'logs'}
        existing_tables = {row[0] for row in tables}
        
        if required_tables.issubset(existing_tables):
            return jsonify({'status': 'ready'}), 200
        else:
            missing = required_tables - existing_tables
            return jsonify({
                'status': 'not_ready',
                'missing_tables': list(missing)
            }), 503
    except Exception as e:
        return jsonify({'status': 'not_ready', 'error': str(e)}), 503
```

Registrar blueprint em `app/__init__.py`:
```python
from app.routes.health import bp as health_bp
app.register_blueprint(health_bp)
```

---

### 4. Adicionar Índices Compostos Críticos
**Tempo:** 15 minutos  
**Impacto:** Alto (performance)  
**Risco:** Baixo

Criar script `add_critical_indexes.py`:

```python
"""
Adiciona índices compostos críticos para melhorar performance.
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "empenhos.db"

CRITICAL_INDEXES = [
    # Filtros da tela principal (mais usado)
    """CREATE INDEX IF NOT EXISTS idx_credores_filtros_principais 
       ON credores(ativo, departamento, tipo_valor, nome)""",
    
    # Busca com paginação
    """CREATE INDEX IF NOT EXISTS idx_credores_busca_paginada 
       ON credores(ativo, nome, departamento, id)""",
    
    # Histórico de empenhos por credor
    """CREATE INDEX IF NOT EXISTS idx_empenhos_historico_credor 
       ON empenhos(credor_id, ano DESC, mes DESC, empenhado)""",
    
    # Logs recentes
    """CREATE INDEX IF NOT EXISTS idx_logs_recentes 
       ON logs(data DESC, acao, credor_id)""",
    
    # RPAs por período
    """CREATE INDEX IF NOT EXISTS idx_rpas_periodo_completo 
       ON rpas(periodo_referencia DESC, cpf_prestador, criado_em DESC)""",
]

def add_indexes():
    print("Conectando ao banco de dados...")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    print(f"\nAdicionando {len(CRITICAL_INDEXES)} índices críticos...\n")
    
    for i, sql in enumerate(CRITICAL_INDEXES, 1):
        index_name = sql.split("IF NOT EXISTS ")[1].split()[0]
        try:
            cur.execute(sql)
            print(f"✓ [{i}/{len(CRITICAL_INDEXES)}] {index_name}")
        except Exception as e:
            print(f"✗ [{i}/{len(CRITICAL_INDEXES)}] {index_name}: {e}")
    
    conn.commit()
    
    # Verificar índices criados
    print("\n" + "="*60)
    print("Índices no banco:")
    print("="*60)
    
    indexes = cur.execute(
        "SELECT name, tbl_name FROM sqlite_master WHERE type='index' ORDER BY tbl_name, name"
    ).fetchall()
    
    current_table = None
    for idx_name, tbl_name in indexes:
        if tbl_name != current_table:
            print(f"\n{tbl_name}:")
            current_table = tbl_name
        print(f"  - {idx_name}")
    
    conn.close()
    print("\n✓ Índices adicionados com sucesso!")

if __name__ == "__main__":
    add_indexes()
```

Executar:
```bash
python add_critical_indexes.py
```

---

## 📈 Melhorias de Médio Prazo (Esta Semana)

### 5. Consolidar Arquitetura (server.py → app/)
**Tempo:** 2-3 horas  
**Impacto:** Alto (manutenibilidade)  
**Risco:** Médio

**Passos:**

1. Backup completo:
```bash
python backup_db.py
git add -A
git commit -m "backup: antes de consolidar arquitetura"
```

2. Mover lógica de `server.py` para `app/__init__.py`:
   - Cache de arquivos estáticos
   - Middlewares
   - Error handlers
   - Inicialização do banco

3. Simplificar `server.py`:
```python
"""
server.py — Ponto de entrada do servidor
"""
from app import create_app
from config import settings

if __name__ == "__main__":
    app = create_app()
    
    print(f"Servidor iniciando em http://{settings.host}:{settings.port}")
    print(f"Modo debug: {'ligado' if settings.debug else 'desligado'}")
    
    app.run(
        host=settings.host,
        port=settings.port,
        debug=settings.debug,
        use_reloader=settings.reloader,
        threaded=True,
    )
```

4. Testar:
```bash
python server.py
# Verificar se todas as rotas funcionam
# Testar páginas principais
```

---

### 6. Implementar Testes Básicos
**Tempo:** 3-4 horas  
**Impacto:** Alto (qualidade)  
**Risco:** Nenhum

**Estrutura:**
```
tests/
├── conftest.py          # Fixtures compartilhadas
├── test_credores.py     # Testes de credores
├── test_empenhos.py     # Testes de empenhos
├── test_api.py          # Testes de API
└── test_db.py           # Testes de banco
```

**Instalar dependências:**
```bash
pip install pytest pytest-cov pytest-flask
```

**Criar conftest.py:**
```python
import pytest
import tempfile
import os
from app import create_app
from app.utils.db import get_db

@pytest.fixture
def app():
    """Cria app de teste com banco temporário."""
    db_fd, db_path = tempfile.mkstemp()
    
    app = create_app({
        'TESTING': True,
        'DATABASE': db_path,
    })
    
    with app.app_context():
        # Inicializar banco de teste
        conn = get_db()
        cur = conn.cursor()
        
        # Criar tabelas
        cur.execute("""
            CREATE TABLE credores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                valor REAL DEFAULT 0,
                departamento TEXT,
                ativo INTEGER DEFAULT 1
            )
        """)
        conn.commit()
    
    yield app
    
    os.close(db_fd)
    os.unlink(db_path)

@pytest.fixture
def client(app):
    """Cliente de teste."""
    return app.test_client()

@pytest.fixture
def runner(app):
    """Runner CLI de teste."""
    return app.test_cli_runner()
```

**Criar test_credores.py:**
```python
def test_listar_credores_vazio(client):
    """Deve retornar lista vazia quando não há credores."""
    response = client.get('/api/credores')
    assert response.status_code == 200
    data = response.get_json()
    assert 'credores' in data
    assert len(data['credores']) == 0

def test_criar_credor_valido(client):
    """Deve criar credor com dados válidos."""
    response = client.post('/api/credores', json={
        'nome': 'FORNECEDOR TESTE',
        'valor': 1000.00,
        'departamento': 'SAÚDE'
    })
    assert response.status_code == 201
    data = response.get_json()
    assert 'id' in data
    assert data['nome'] == 'FORNECEDOR TESTE'

def test_criar_credor_sem_nome(client):
    """Deve rejeitar credor sem nome."""
    response = client.post('/api/credores', json={
        'valor': 1000.00
    })
    assert response.status_code == 400
    data = response.get_json()
    assert 'error' in data or 'errors' in data
```

**Rodar testes:**
```bash
pytest tests/ -v
pytest tests/ -v --cov=app --cov-report=html
```

---

### 7. Separar Lógica de Negócio (Services)
**Tempo:** 4-6 horas  
**Impacto:** Alto (manutenibilidade)  
**Risco:** Médio

**Estrutura:**
```
app/
├── services/
│   ├── __init__.py
│   ├── credores_service.py
│   ├── empenhos_service.py
│   └── base_service.py
└── repositories/
    ├── __init__.py
    └── credores_repository.py
```

**Exemplo base_service.py:**
```python
from typing import Optional
from app.utils.db import get_db

class BaseService:
    """Classe base para services."""
    
    def __init__(self):
        self.db = get_db()
    
    def log_action(self, action: str, details: str = "", credor_id: Optional[int] = None):
        """Registra ação no log."""
        self.db.execute(
            "INSERT INTO logs (acao, detalhes, credor_id) VALUES (?, ?, ?)",
            (action, details, credor_id)
        )
        self.db.commit()
```

**Exemplo credores_service.py:**
```python
from typing import Tuple, List, Dict, Optional
from app.services.base_service import BaseService
from app.utils.helpers import normalizar_cnpj, cnpj_valido

class CredoresService(BaseService):
    """Service para lógica de negócio de credores."""
    
    def criar_credor(self, data: dict) -> Tuple[Optional[Dict], List[str]]:
        """
        Cria um novo credor.
        
        Returns:
            (credor_criado, erros)
        """
        # Validar dados
        payload, errors = self._validar_payload(data)
        if errors:
            return None, errors
        
        # Verificar duplicidade
        duplicado, msg = self._verificar_duplicado(payload.get('cnpj'))
        if duplicado:
            return None, [msg]
        
        # Inserir no banco
        cur = self.db.execute(
            """INSERT INTO credores (nome, valor, departamento, cnpj, email)
               VALUES (?, ?, ?, ?, ?)""",
            (
                payload['nome'],
                payload.get('valor', 0),
                payload.get('departamento', ''),
                payload.get('cnpj', ''),
                payload.get('email', '')
            )
        )
        self.db.commit()
        
        credor_id = cur.lastrowid
        
        # Log
        self.log_action('CRIAR_CREDOR', f"Credor {payload['nome']}", credor_id)
        
        # Retornar credor criado
        credor = self.db.execute(
            "SELECT * FROM credores WHERE id=?", (credor_id,)
        ).fetchone()
        
        return dict(credor), []
    
    def _validar_payload(self, data: dict) -> Tuple[Dict, List[str]]:
        """Valida dados do credor."""
        errors = []
        payload = {}
        
        # Nome obrigatório
        nome = (data.get('nome') or '').strip().upper()
        if not nome:
            errors.append('Campo "nome" é obrigatório')
        elif len(nome) < 3:
            errors.append('Campo "nome" deve ter pelo menos 3 caracteres')
        else:
            payload['nome'] = nome
        
        # Valor
        try:
            valor = float(data.get('valor', 0))
            if valor < 0:
                raise ValueError
            payload['valor'] = valor
        except:
            errors.append('Campo "valor" inválido')
        
        # CNPJ
        cnpj = normalizar_cnpj(data.get('cnpj', ''))
        if cnpj and not cnpj_valido(cnpj):
            errors.append('CNPJ inválido')
        payload['cnpj'] = cnpj
        
        # Outros campos...
        payload['departamento'] = (data.get('departamento') or '').strip().upper()
        payload['email'] = (data.get('email') or '').strip().lower()
        
        return payload, errors
    
    def _verificar_duplicado(self, cnpj: str) -> Tuple[bool, str]:
        """Verifica se já existe credor com este CNPJ."""
        if not cnpj:
            return False, ''
        
        row = self.db.execute(
            "SELECT id, nome FROM credores WHERE ativo=1 AND cnpj=?",
            (cnpj,)
        ).fetchone()
        
        if row:
            return True, f'Já existe credor ativo com este CNPJ: {row["nome"]}'
        
        return False, ''
```

**Atualizar rota:**
```python
# app/routes/credores.py
from app.services.credores_service import CredoresService

@bp.route('/credores', methods=['POST'])
def criar_credor():
    service = CredoresService()
    credor, errors = service.criar_credor(request.json)
    
    if errors:
        return jsonify({'errors': errors}), 400
    
    return jsonify(credor), 201
```

---

## 🚀 Melhorias de Longo Prazo (Próximas 2 Semanas)

### 8. Implementar Rate Limiting
### 9. Otimizar Cache de Arquivos Estáticos
### 10. Adicionar Logging Estruturado
### 11. Implementar Connection Pool
### 12. Adicionar Métricas de Performance

---

## ✅ Checklist de Implementação

### Hoje (14/04/2026)
- [ ] Criar .gitignore
- [ ] Criar .env e .env.example
- [ ] Adicionar endpoint /health
- [ ] Executar add_critical_indexes.py
- [ ] Testar todas as funcionalidades principais

### Esta Semana
- [ ] Consolidar arquitetura (server.py → app/)
- [ ] Implementar testes básicos (pytest)
- [ ] Separar services das rotas
- [ ] Documentar mudanças no README

### Próximas 2 Semanas
- [ ] Rate limiting
- [ ] Otimizar cache
- [ ] Logging estruturado
- [ ] Connection pool
- [ ] Métricas

---

## 📊 Como Medir Sucesso

### Métricas Antes
```bash
# Tempo de startup
time python server.py &

# Tempo de query
curl -w "@curl-format.txt" http://localhost:5000/api/credores

# Uso de memória
ps aux | grep python
```

### Métricas Depois
- Startup < 500ms
- Query credores < 20ms
- Memória < 60MB
- Testes passando 100%

---

## 🆘 Rollback Plan

Se algo der errado:

```bash
# 1. Parar servidor
Ctrl+C

# 2. Restaurar backup
python backup_restaurar.bat

# 3. Voltar commit anterior
git reset --hard HEAD~1

# 4. Reiniciar
python server.py
```

---

## 📞 Suporte

- Documentação: `MELHORIAS_SUGERIDAS.md`
- Issues: Criar issue no repositório
- Logs: `logs/server.log`
