# 📋 Plano de Refatoração do Servidor

## 🎯 Problema Atual

O arquivo `server.py` possui **4161 linhas** com:
- **93 rotas** misturadas com lógica de negócio
- Helpers e utilitários espalhados
- Dificuldade de manutenção e testes
- Acoplamento alto entre camadas

---

## ✅ Solução Implementada

Foi criada uma **arquitetura modular** seguindo o padrão Application Factory do Flask:

```
app/
├── __init__.py           # Factory do Flask
├── routes/               # Blueprints de rotas
│   ├── auth.py           # Autenticação
│   ├── config.py         # Configurações
│   ├── credores.py       # Gestão de credores
│   ├── empenhos.py       # Gestão de empenhos
│   ├── rpas.py           # Recibos RPA
│   ├── kanban.py         # Tarefas Kanban
│   ├── documentos.py     # Centro de documentos
│   ├── autentique.py     # Integração Autentique
│   ├── prazos.py         # Gestão de prazos
│   ├── protocolo.py      # Protocolo
│   ├── extratos.py       # Processamento de extratos
│   ├── ia.py             # IA/OpenRouter
│   ├── cnpj.py           # Consulta CNPJ
│   └── pdf.py            # Manipulação de PDF
├── utils/
│   ├── __init__.py
│   ├── helpers.py        # Funções auxiliares
│   └── db.py             # Banco de dados
└── models/
    └── __init__.py       # Modelos de dados
```

---

## 📊 Comparação

| Aspecto | Antes | Depois |
|---------|-------|--------|
| **Linhas no server.py** | 4161 | ~100 |
| **Organização** | Único arquivo | 15 módulos |
| **Testabilidade** | Baixa | Alta |
| **Manutenibilidade** | Difícil | Fácil |
| **Acoplamento** | Alto | Baixo |

---

## 🚀 Como Usar a Nova Versão

### Opção 1: Manter server.py atual (recomendado para produção)

O servidor atual continua funcionando normalmente. A refatoração é **compatível** e pode ser migrada gradualmente.

### Opção 2: Migrar para nova estrutura

1. **Renomeie o server.py atual:**
   ```bash
   ren server.py server_monolitico.py
   ren server_novo.py server.py
   ```

2. **Teste o servidor:**
   ```bash
   python server.py
   ```

3. **Acesse:** http://localhost:5000

---

## 📝 Próximos Passos

### Fase 1 - Infraestrutura (✅ Concluída)
- [x] Criar estrutura de pastas `app/`
- [x] Criar factory do Flask
- [x] Mover helpers para `app/utils/`
- [x] Criar blueprints básicos

### Fase 2 - Migração de Rotas (🔄 Em Progresso)
- [x] Rotas de autenticação e config
- [x] Rotas de credores e empenhos
- [x] Rotas de RPA e Kanban
- [x] Rotas de documentos e Autentique
- [x] Rotas de prazos e protocolo
- [x] Rotas de extratos, IA, CNPJ, PDF

### Fase 3 - Finalização (⏳ Pendente)
- [ ] Migrar rotas restantes do server.py original
- [ ] Atualizar imports nos serviços existentes
- [ ] Criar testes unitários
- [ ] Documentar cada blueprint
- [ ] Validar todas as funcionalidades

---

## 🔧 Benefícios da Refatoração

### 1. **Manutenibilidade**
- Cada módulo tem responsabilidade única
- Fácil localizar e modificar código
- Menor risco de efeitos colaterais

### 2. **Testabilidade**
- Blueprints podem ser testados isoladamente
- Mock de dependências simplificado
- Cobertura de testes mais fácil

### 3. **Escalabilidade**
- Novas rotas em arquivos separados
- Serviços podem ser extraídos gradualmente
- Possibilidade de microserviços futuros

### 4. **Colaboração**
- Múltiplos desenvolvedores sem conflitos
- Code review focado por módulo
- Onboarding de novos devs acelerado

---

## 📚 Estrutura de Cada Blueprint

Cada arquivo de rota segue este padrão:

```python
"""
app/routes/nome_modulo.py — Descrição do módulo
"""

from flask import Blueprint, request, jsonify
from app.utils.db import get_db
from app.utils.helpers import row_to_dict

bp = Blueprint('nome', __name__)


@bp.route('/endpoint', methods=['GET'])
def funcao():
    """Docstring da função."""
    try:
        conn = get_db()
        # Lógica aqui
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

---

## 🔍 Mapeamento de Rotas

| Rota Original | Novo Blueprint | Status |
|--------------|----------------|--------|
| `/api/credores` | `app/routes/credores.py` | ✅ Migrado |
| `/api/empenhos/*` | `app/routes/empenhos.py` | ✅ Migrado |
| `/api/rpas` | `app/routes/rpas.py` | ✅ Migrado |
| `/api/kanban/*` | `app/routes/kanban.py` | ✅ Migrado |
| `/api/documentos/*` | `app/routes/documentos.py` | ✅ Migrado |
| `/api/autentique/*` | `app/routes/autentique.py` | ✅ Migrado |
| `/api/prazos/*` | `app/routes/prazos.py` | ✅ Migrado |
| `/api/protocolo/*` | `app/routes/protocolo.py` | ✅ Migrado |
| `/api/extratos/*` | `app/routes/extratos.py` | ✅ Migrado |
| `/api/ia/*` | `app/routes/ia.py` | ✅ Migrado |
| `/api/cnpj/*` | `app/routes/cnpj.py` | ✅ Migrado |
| `/api/pdf/*` | `app/routes/pdf.py` | ✅ Migrado |
| `/api/auth/*` | `app/routes/auth.py` | ✅ Migrado |
| `/api/config` | `app/routes/config.py` | ✅ Migrado |

---

## ⚠️ Atenção

### Compatibilidade
- Os serviços existentes em `/services/` continuam funcionando
- A nova estrutura é **adicional**, não substituta
- Migração pode ser gradual

### Banco de Dados
- Estrutura do banco não muda
- Mesmas tabelas e índices
- Funções de DB em `app/utils/db.py`

### Configuração
- `config.py` permanece inalterado
- Variáveis de ambiente iguais
- `.env` compatível

---

## 📞 Dúvidas

Consulte a documentação do Flask sobre:
- [Application Factory](https://flask.palletsprojects.com/en/patterns/appfactories/)
- [Blueprints](https://flask.palletsprojects.com/en/blueprints/)
- [Large Applications as a Package](https://flask.palletsprojects.com/en/patterns/packages/)

---

**Data**: 31 de Março de 2026
**Autor**: Refatoração Assistida por IA
**Status**: Estrutura criada, migração em andamento
