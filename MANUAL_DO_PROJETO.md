# Manual Completo do Projeto - Sistema de Controle de Empenhos Mensais
Prefeitura Municipal de Inajá

Este manual fornece uma visão detalhada de todos os aspectos do projeto, desde a arquitetura até o uso diário do sistema.

## 📋 Sumário

1. [Visão Geral do Projeto](#-visão-geral-do-projeto)
2. [Arquitetura do Sistema](#-arquitetura-do-sistema)
3. [Instalação e Configuração](#-instalação-e-configuração)
4. [Estrutura de Pastas](#-estrutura-de-pastas)
5. [Módulos do Sistema](#-módulos-do-sistema)
6. [API REST](#-api-rest)
7. [Banco de Dados](#-banco-de-dados)
8. [Configurações e Variáveis de Ambiente](#-configurações-e-variáveis-de-ambiente)
9. [Tecnologias Utilizadas](#-tecnologias-utilizadas)
10. [Manutenção e Troubleshooting](#-manutenção-e-troubleshooting)

---

## 🎯 Visão Geral do Projeto

O Sistema de Controle de Empenhos Mensais é uma aplicação web local desenvolvida para a Prefeitura Municipal de Inajá, destinada à gestão de:

- Credores fixos e seus empenhos mensais
- Recibos de Pagamento Autônomo (RPA)
- Processamento inteligente de documentos com IA
- Controle financeiro e orçamentário
- Gestão de tarefas e calendário institucional
- Análise de extratos bancários e tarifas
- Consulta de dados cadastrais de empresas (CNPJ)

O sistema é construído com Python/Flask no backend e HTML/CSS/JavaScript no frontend, utilizando SQLite como banco de dados local.

---

## 🏗️ Arquitetura do Sistema

### Arquitetura em Camadas

```
┌─────────────────┐
│   Frontend      │ ← HTML/CSS/JS (pasta /pages, /static)
├─────────────────┤
│   Backend API   │ ← Flask (server.py + services/)
├─────────────────┤
│   Banco de Dados│ ← SQLite (empenhos.db)
├─────────────────┤
│   Serviços IA   │ ← OpenRouter API (opcional)
└─────────────────┘
```

### Componentes Principais

1. **Servidor Flask** (`server.py`): 
   - Servidor web que expõe a API REST e serve os arquivos estáticos
   - Contém rotas para autenticação, logging e middleware

2. **Serviços** (`/services/`):
   - `empenhos_service.py`: Lógica de negócio para credores e empenhos
   - `extratos_service.py`: Processamento de extratos bancários
   - `openrouter_service.py`: Integração com API de IA OpenRouter
   - `config.py`: Gerenciamento de configurações

3. **Frontend**:
   - Páginas HTML em `/pages/` para cada módulo
   - Arquivos estáticos em `/static/` (CSS, JS, imagens)
   - JavaScript otimizado com cache, tratamento de erros e logging

4. **Banco de Dados**:
   - SQLite (`empenhos.db`) com tabelas para credores, empenhos, RPAs, logs, etc.

5. **Integrações Externas** (opcionais):
   - OpenRouter API para funcionalidades de IA
   - CNPJá/ReceitaWS para consulta de empresas
   - APIs bancárias para extratos (via upload de arquivos)

---

## 🔧 Instalação e Configuração

### Pré-requisitos

- Python 3.8 ou superior
- pip (gerenciador de pacotes Python)
- Acesso à internet para download das dependências (ou arquivo requirements.txt disponível)

### Passo a Passo para Instalação

1. **Clone ou copie o projeto** para o diretório desejado

2. **Instale as dependências**:
   ```bash
   python -m pip install -r requirements.txt
   ```

3. **Configure as variáveis de ambiente** (opcional, pode usar os padrões):
   ```bash
   set APP_HOST=0.0.0.0
   set APP_PORT=5000
   set APP_DEBUG=true
   set ADM_PASSWORD=sua_senha_aqui
   set OPENROUTER_DEFAULT_MODEL=openai/gpt-4o-mini
   set OPENROUTER_CHAT_MODEL=meta-llama/llama-3.3-70b-instruct:free
   set OPENROUTER_REFERER=https://localhost
   set OPENROUTER_TITLE=CEREBRO_PREFEITURA
   ```

4. **Inicialize o banco de dados**:
   O banco será criado automaticamente na primeira execução do servidor.
   Para atualizar credores via Excel, veja a seção [Atualização de Credores](#atualização-de-credores-via-excel).

5. **Inicie o servidor**:
   - Opção 1: Duplo clique em `iniciar.bat`
   - Opção 2: Via terminal:
     ```bash
     python server.py
     ```

6. **Acesse o sistema**:
   Abra o navegador e vá para: `http://localhost:5000`

---

## 📁 Estrutura de Pastas

```
CREDORES_FIXOS_MENSAIR/
├── server.py                 # Servidor Flask principal
├── config.py                 # Configurações do sistema
├── iniciar.bat               # Script para iniciar o servidor (Windows)
├── requirements.txt          # Dependências Python
├── exportar_dados.py         # Script para atualizar credores via Excel
├── data.js                   # Dados estáticos usados no frontend
├── empenhos.db               # Banco de dados SQLite
├── index.html                # Página inicial do sistema
├── README.md                 # Visão geral básica
├── MANUAL_DO_PROJETO.md      # Este manual
├── GUIA_MODULOS.md           # Guia técnico de módulos de otimização
├── pages/                    # Páginas HTML dos módulos
│   ├── auditor.html
│   ├── calendario.html
│   ├── cnpj.html
│   ├── despesa-prefeitura.html
│   ├── despesa-relatorios.html
│   ├── extratos.html
│   ├── fornecimento.html
│   ├── gerador-empenho.html
│   ├── manual.html           # Manual existente (mantido para compatibilidade)
│   ├── pdf.html
│   ├── renomear.html
│   ├── rpa.html
│   ├── tarefas.html
│   ├── tarifas-bancarias.html
│   └── visualizador.html
├── static/                   # Arquivos estáticos
│   ├── css/
│   ├── js/
│   │   ├── app.js
│   │   ├── shared-header.js
│   │   └── despesa/
│   └── img/
├── services/                 # Lógica de negócio
│   ├── __init__.py
│   ├── empenhos_service.py
│   ├── extratos_service.py
│   └── openrouter_service.py
├── renomer/                  # Módulo de renomeação com IA
│   ├── organizador_local_avancado.py
│   ├── organizador_ia.py
│   ├── file_processor.py
│   └── prompts.py
├── documentos_centro/        # Pasta para documentos processados
├── logs/                     # Logs do servidor
└── __pycache__/              # Cache do Python
```

---

## 🧩 Módulos do Sistema

O sistema possui 15 módulos principais, cada um acessível pelo menu de navegação:

### 1. 💼 Credores Fixos
**Propósito**: Gerenciamento de credores que recebem empenhos mensais recorrentes
**Funcionalidades**:
- Cadastro, edição e exclusão de credores
- Organização por departamento (Administração, Saúde, Educação, Assistência Social)
- Controle mensal de empenhos (Pendente/Empenhado)
- Filtros por departamento e status
- Visualização histórica de empenhos
- Geração de relatórios em PDF

### 2. ✍️ Gerador de Empenho (IA)
**Propósito**: Criação automática de textos de empenho usando inteligência artificial
**Funcionalidades**:
- Entrada via upload de documento (PDF/imagem) ou digitação de texto
- Geração de texto formal em linguagem administrativa
- Contextualização com departamento, valor e fornecedor
- Edição e download do texto gerado
- Cache inteligente para reduzir custos de API

### 3. 🧾 RPA (Recibo de Pagamento Autônomo)
**Propósito**: Geração de recibos para prestadores autônomos
**Funcionalidades**:
- Cadastro de prestadores (nome, CPF, endereço, banco)
- Descrição do serviço prestado
- Cálculo automático de deduções (INSS, ISS)
- Geração de PDF pronto para assinatura
- Arquivamento e consulta de RPAs salvos
- Configuração de dados da prefeitura para preenchimento automático

### 4. 🔍 Auditor Fiscal com IA
**Propósito**: Análise automatizada de notas fiscais para detectar irregularidades
**Funcionalidades**:
- Upload de notas fiscais (PDF, JPG, PNG)
- Análise por IA para identificar:
  - Valores divergentes
  - Dados fiscais inválidos
  - Inconsistências nos serviços declarados
  - Sinais de adulteração
- Relatório com classificação (Aprovado/Suspeito/Reprovado)
- Download do relatório em PDF

### 5. 🏷️ Renomeador de Documentos com IA
**Propósito**: Renomeação em lote de documentos usando IA
**Funcionalidades**:
- Upload múltiplo de arquivos (PDF, imagens, Word)
- Análise de conteúdo para sugestão de nomes padronizados
- Edição dos nomes sugeridos antes da confirmação
- Download em lote dos arquivos renomeados
- Histórico de todas as renomeações realizadas

### 6. 🛒 Sistema de Aquisições
**Propósito**: Criação e gerenciamento de solicitações de aquisição
**Funcionalidades**:
- Formulário para solicitações individuais
- Importação em lote via arquivo de texto
- Adição múltipla de itens com descrição, quantidade e valor
- Pré-visualização em tempo real
- Exportação para PDF
- Template disponível para importação em lote

### 7. 📋 Tarefas · Kanban
**Propósito**: Gestão de tarefas com quadro visual
**Funcionalidades**:
- Quadro Kanban (A Fazer, Em Progresso, Concluído)
- Criação, edição e exclusão de tarefas
- Definição de prioridade (Baixa, Média, Alta)
- Atribuição de responsáveis
- Arraste-e-soltar para mudança de status
- Contadores automáticos por coluna

### 8. 📅 Calendário Municipal
**Propósito**: Agenda de pagamentos e eventos da prefeitura
**Funcionalidades**:
- Navegação mensal entre calendários
- Adição de eventos com título, hora e categoria
- Visualização colorida de eventos por dia
- Edição e exclusão de eventos
- Múltiplos eventos por dia

### 9. 🏢 Consulta CNPJ
**Propósito**: Busca de dados cadastrais de empresas
**Funcionalidades**:
- Consulta direta à Receita Federal (via CNPJá/ReceitaWS)
- Busca por CNPJ (com ou without formatação)
- Exibição de:
  - Razão social e nome fantasia
  - Endereço completo
  - Atividades econômicas (CNAE)
  - Sócios e administradores
  - Situação cadastral
  - Data de abertura
- Limite de 5 consultas gratuitas por minuto (aumentável com chave API)
- Impressão dos resultados

### 10. 🏦 Extratos Bancários (IA)
**Propósito**: Análise e organização de extratos bancários
**Funcionalidades**:
- Upload de extratos (PDF ou OFX)
- Processamento automático das transações
- Categorização inteligente com IA
- Filtros por período e categoria
- Visualização em tabela organizada
- Exportação para planilha
- Identificação de padrões de gastos e receitas

### 11. 👁️ Visualizador de Empenhos
**Propósito**: Relatório interativo de empenhos
**Funcionalidades**:
- Filtros por departamento, período e status
- Ordenação por clique nos cabeçalhos de coluna
- Exportação para Excel ou impressão
- Visualização de credor, valor, status e data
- Detalhamento de histórico por credor

### 12. 📄 PDF Tools
**Propósito**: Suite completa para manipulação de PDFs
**Funcionalidades**:
- Visualizador com zoom e navegação
- Ferramentas de anotação (texto, notas, desenho)
- Assinatura digital
- Mesclagem de múltiplos PDFs
- Divisão de PDF por intervalos de páginas
- Proteção com senha
- Todo processamento ocorre localmente no navegador

### 13. 💰 Analisador Financeiro (Tarifas Bancárias)
**Propósito**: Análise de tarifas e encargos bancários
**Funcionalidades**:
- Importação de extrato de tarifas fornecido pelo banco
- Categorização automática de tarifas
- Verificação de conformidade com limites do Banco Central
- Destaque visual para possíveis cobranças indevidas (vermelho)
- Geração de relatório para contestação
- Análise comparativa histórica

### 14. 📊 Despesa Pública
**Propósito**: Importação e análise de despesas do portal da transparência
**Funcionalidades**:
- **Visor de Despesas**: Consulta em tempo real do portal da transparência
  - Filtros por período e órgão/unidade orçamentária
  - Tabela detalhada de despesas
  - Gráficos de distribuição por categoria
- **Relatórios de Despesa**: Comparação entre períodos
  - Análise lado a lado de dois períodos
  - Variações percentuais destacadas
  - Exportação para PDF ou Excel

### 15. ⚙️ ADM — Área Administrativa
**Propósito**: Configuração de integrações e parâmetros do sistema
**Funcionalidades**:
- Configuração de chaves de API:
  - OpenRouter (para funcionalidades de IA)
  - CNPJá (para aumento de limite de consultas)
- Seleção de modelo de IA a ser utilizado
- Teste de conectividade com APIs
- Visualização de logs do sistema
- Gerenciamento de senha de acesso administrativo

---

## 🔌 API REST

O sistema expõe uma API REST completa para integração com outros sistemas ou desenvolvimento de clientes personalizados.

### Autenticação
Alguns endpoints podem requerer autenticação futura. Atualmente, o acesso é liberado para a rede local.

### Endpoints Principais

#### Credores
```
GET    /api/credores           # Lista credores ativos
POST   /api/credores           # Cria credor
PUT    /api/credores/<id>      # Atualiza credor
DELETE /api/credores/<id>      # Remove credor (soft delete)
```

#### Empenhos
```
GET    /api/empenhos/<ano>/<mes>  # Empenhos de um mês
POST   /api/empenhos               # Toggle empenho (empena/desempena)
GET    /api/empenhos/historico/<id> # Histórico de um credor
```

#### RPAs
```
GET    /api/rpas               # Lista RPAs
POST   /api/rpas               # Cria RPA
PUT    /api/rpas/<id>          # Atualiza RPA
DELETE /api/rpas/<id>          # Remove RPA
```

#### CNPJ
```
POST   /api/cnpj/buscar        # Consulta CNPJ
```

#### Extratos
```
POST   /api/extratos/preview   # Pré-visualiza organização de extratos
POST   /api/extratos/organizar # Organiza extratos
```

#### PDF
```
POST   /api/pdf/mesclar        # Mescla PDFs
POST   /api/pdf/dividir        # Divide PDF
POST   /api/pdf/proteger       # Protege PDF com senha
```

#### Logs
```
GET    /api/logs               # Últimas 100 ações
```

### Exemplos de Uso

#### Listar credores ativos:
```bash
curl http://localhost:5000/api/credores
```

#### Criar um novo credor:
```bash
curl -X POST http://localhost:5000/api/credores \
  -H "Content-Type: application/json" \
  -d '{"nome": "Empresa Exemplo", "departamento": "Saude", "valor": 1500.00, "objeto": "Prestacao de servicos"}'
```

#### Empenhar um credor para um mês específico:
```bash
curl -X POST http://localhost:5000/api/empenhos \
  -H "Content-Type: application/json" \
  -d '{"credor_id": 1, "ano": 2026, "mes": 3}'
```

---

## 🗃️ Banco de Dados

O sistema utiliza SQLite com o arquivo `empenhos.db` localizado na raiz do projeto.

### Tabelas Principais

#### credores
Armazena informações dos credores fixos:
- `id` (INTEGER PRIMARY KEY)
- `nome` (TEXT)
- `departamento` (TEXT)
- `valor` (REAL)
- `objeto` (TEXT)
- `ativo` (INTEGER, padrão 1)
- `timestamp` (TEXT)

#### empenhos
Registra os empenhos mensais dos credores:
- `id` (INTEGER PRIMARY KEY)
- `credor_id` (INTEGER, FK para credores.id)
- `ano` (INTEGER)
- `mes` (INTEGER)
- `empenhado` (INTEGER, 0 ou 1)
- `timestamp` (TEXT)

#### rpas
Armazena os Recibos de Pagamento Autônomo:
- `id` (INTEGER PRIMARY KEY)
- `prestador_nome` (TEXT)
- `prestador_cpf` (TEXT)
- `prestador_endereco` (TEXT)
- `prestador_banco` (TEXT)
- `prestador_agencia` (TEXT)
- `prestador_conta` (TEXT)
- `servico_descricao` (TEXT)
- `valor_bruto` (REAL)
- `periodo_referencia` (TEXT)
- `inss_desconto` (REAL)
- `iss_desconto` (REAL)
- `valor_liquido` (REAL)
- `numero_documento` (TEXT)
- `data_emissao` (TEXT)
- `timestamp` (TEXT)

#### logs
Registra todas as ações importantes no sistema:
- `id` (INTEGER PRIMARY KEY)
- `acao` (TEXT)
- `credor_id` (INTEGER, FK para credores.id)
- `credor_nome` (TEXT)
- `detalhes` (TEXT)
- `timestamp` (TEXT)

#### configuracoes
Armazena configurações do sistema:
- `id` (INTEGER PRIMARY KEY)
- `chave` (TEXT UNIQUE)
- `valor` (TEXT)
- `descricao` (TEXT)

### Inicialização do Banco

O banco de dados é criado automaticamente na primeira execução do servidor através do script `server.py`. As tabelas são criadas com estruturas padrão e, se o banco estiver vazio, é populado com dados iniciais de credores (se disponível).

---

## ⚙️ Configurações e Variáveis de Ambiente

O sistema aceita configuração por variáveis de ambiente ou através do arquivo `.env`.

### Variáveis de Ambiente Disponíveis

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `APP_HOST` | Host do servidor | `0.0.0.0` |
| `APP_PORT` | Porta HTTP | `5000` |
| `APP_DEBUG` | Ativa debug mode | `false` |
| `ADM_PASSWORD` | Senha da área administrativa | `1999` |
| `OPENROUTER_DEFAULT_MODEL` | Modelo padrão do organizador de extratos | `openai/gpt-4o-mini` |
| `OPENROUTER_CHAT_MODEL` | Modelo padrão do proxy `/api/ia/chat` | `meta-llama/llama-3.3-70b-instruct:free` |
| `OPENROUTER_REFERER` | Cabeçalho `HTTP-Referer` enviado ao OpenRouter | `https://localhost` |
| `OPENROUTER_TITLE` | Cabeçalho `X-Title` enviado ao OpenRouter | `CEREBRO_PREFEITURA` |

### Arquivo .env

Crie um arquivo `.env` na raiz do projeto com o formato:
```
APP_HOST=0.0.0.0
APP_PORT=5000
APP_DEBUG=true
ADM_PASSWORD=sua_senha
OPENROUTER_DEFAULT_MODEL=openai/gpt-4o-mini
OPENROUTER_CHAT_MODEL=meta-llama/llama-3.3-70b-instruct:free
OPENROUTER_REFERER=https://localhost
OPENROUTER_TITLE=CEREBRO_PREFEITURA
```

### Configurações via Área Administrativa

Algumas configurações podem ser feitas através da interface web na área ADM:
- Chave da API OpenRouter
- Chave da API CNPJá
- Seleção do modelo de IA
- Visualização e limpeza de logs

---

## 💻 Tecnologias Utilizadas

### Backend
- **Python 3.8+**: Linguagem de programação principal
- **Flask 3.0+**: Framework web para criação do servidor e API REST
- **SQLite**: Banco de dados embutido para armazenamento local
- **PyPDF2**: Manipulação de PDFs (mescla, divisão, proteção)
- **pdfplumber**: Extração de texto de PDF para processamento com IA
- **openpyxl**: Leitura e escrita de arquivos Excel
- **requests**: Cliente HTTP para integração com APIs externas

### Frontend
- **HTML5**: Estrutura das páginas
- **CSS3**: Estilização e responsividade
- **JavaScript ES6+**: Lógica de cliente e interatividade
- **Font Awesome**: Ícones utilizados na interface
- **Google Fonts**: Tipografias personalizadas

### Integrações Externas (Opcionais)
- **OpenRouter API**: Acesso a diversos modelos de linguagem para funcionalidades de IA
- **CNPJá/ReceitaWS**: Consulta de dados cadastrais de empresas
- **APIs Bancárias**: Para processamento de extratos (via upload de arquivos)

### Ferramentas de Desenvolvimento
- **Git**: Controle de versão
- **PIP**: Gerenciador de pacotes Python
- **Navegadores modernos**: Chrome, Firefox, Edge, Safari para acesso ao sistema

---

## 📖 Como Usar o Sistema

### Acesso Inicial
Após iniciar o servidor com `python server.py` ou duplo clique em `iniciar.bat`:
1. Abra o navegador
2. Acesse `http://localhost:5000`
3. O sistema abrirá na tela inicial com o menu de navegação superior

### Navegação
- O menu fixo no topo permite acesso rápido a todos os módulos
- O ícone de três pontos (⋯) no canto direito fornece acesso aos logs do sistema
- O tema (claro/escuro) pode ser alternado nas preferências do navegador ou através do localStorage

### Fluxo de Trabalho Típico

#### Para Gerenciamento de Credores:
1. Acesse o módulo "Credores Fixos"
2. Cadastre novos credores com "Novo Credor"
3. Organize por departamento usando os filtros
4. Marque empenhos mensais conforme ocorrem
5. Visualize histórico usando as setas de navegação temporal
6. Gere relatórios com "Imprimir Lote"

#### Para Processamento de Documentos com IA:
1. Certifique-se de ter configurado uma chave API da OpenRouter na ADM
2. Acesse o módulo desejado (Gerador de Empenho, Auditor Fiscal, etc.)
3. Faça upload do documento ou insira os dados necessários
4. Aguarde o processamento da IA
5. Revise, edite se necessário e exporte o resultado

#### Para Controle Financeiro:
1. Use "Extratos Bancários" para processar extratos mensais
2. Utilize "Despesa Pública" para acompanhar gastos conforme portal da transparência
3. Analise tarifas com o "Analisador Financeiro"
4. Planeje pagamentos no "Calendário Municipal"

---

## 🔄 Atualização de Credores via Excel

O sistema permite atualizar a lista de credores a partir de um arquivo Excel:

1. Prepare um arquivo Excel com as colunas:
   - `nome`: Nome do credor
   - `departamento`: Departamento (Administração, Saúde, Educação, Assistência Social)
   - `valor`: Valor mensal do empenho
   - `objeto`: Descrição do objeto do contrato

2. Salve o arquivo na pasta do projeto

3. Edite o arquivo `exportar_dados.py`:
   - Localize a linha `EXCEL_FILE = "seu_arquivo.xlsx"`
   - Substitua `seu_arquivo.xlsx` pelo nome do seu arquivo

4. Execute o script:
   ```bash
   python exportar_dados.py
   ```

5. Reinicie o servidor para que as alterações tenham efeito

> **Nota**: Se o banco de dados estiver vazio, ele será populado com os dados do Excel. Se já contiver dados, apenas novos credores serão adicionados (não sobrescreve existentes).

---

## 🐛 Manutenção e Troubleshooting

### Problemas Comuns

#### 1. Servidor não inicia
- **Verifique**: Se a porta 5000 está livre
- **Solucione**: 
  ```bash
  netstat -ano | findstr :5000
  ```
  Se estiver em uso, altere a porta em `config.py` ou `APP_PORT` nas variáveis de ambiente

#### 2. Erros de dependência
- **Verifique**: Se todas as dependências estão instaladas
- **Solucione**:
  ```bash
  python -m pip install -r requirements.txt --upgrade
  ```

#### 3. Falha na conexão com IA
- **Verifique**: Se a chave da API OpenRouter está configurada corretamente
- **Solucione**:
  1. Acesse ADM → OpenRouter (IA)
  2. Verifique se a chave está no formato `sk-or-v1-...`
  3. Clique em "Testar Chave"

#### 4. Banco de dados corrompido
- **Verifique**: Se o arquivo `empenhos.db` está acessível
- **Solucione**:
  1. Faça backup do arquivo atual
  2. Exclua ou renomeie `empenhos.db`
  3. Reinicie o servidor (criará um novo banco vazio)
  4. Restaure os credores via Excel se necessário

#### 5. Problemas de desempenho com IA
- **Verifique**: Se está usando modelos gratuitos ou pagos
- **Otimize**:
  1. Use modelos gratuitos sempre que possível (ex: `meta-llama/llama-3.2-3b-instruct:free`)
  2. Ative o cache nas opções de IA
  3. Limite o tamanho dos documentos enviados

### Logs do Sistema

O sistema mantém logs detalhados que podem ser acessados através:
1. Interface web: Clique no ícone de três pontos (⋯) → "Logs"
2. Arquivo físico: `logs/server.log`
3. Terminal: Observe a saída do servidor ao executar `python server.py`

Os logs registram:
- Acesso às páginas
- Chamadas à API
- Operações de banco de dados
- Integrações com APIs externas
- Erros e exceções
- Ações dos usuários (empenhos, RPAs, etc.)

### Backup e Recuperação

#### Backup Manual
1. Pare o servidor
2. Copie o arquivo `empenhos.db` para um local seguro
3. (Opcional) Copie também a pasta `documentos_centro/` se houver documentos importantes
4. Reinicie o servidor

#### Recuperação
1. Pare o servidor
2. Substitua o arquivo `empenhos.db` pelo backup
3. (Se aplicável) Restaure a pasta `documentos_centro/`
4. Reinicie o servidor

---

## 📞 Suporte e Contribuindo

Este sistema foi desenvolvido para a Prefeitura Municipal de Inajá. Para suporte técnico ou sugestões de melhorias:

### Contato
- Desenvolvedor: Aleksandro Alves
- Sistema: Sistema de Controle de Empenhos Mensais
- Versão: Consulte o arquivo `CHANGELOG_23FEV2026.md` para o histórico de atualizações

### Contribuindo
Se você deseja contribuir para o projeto:

1. **Fork** o repositório
2. Crie uma **branch** para sua feature: `git checkout -b feature/nova-funcionalidade`
3. Faça suas alterações
4. **Commit** suas mudanças: `git commit -m "Adiciona nova funcionalidade"`
5. **Push** para a branch: `git push origin feature/nova-funcionalidade`
6. Abra um **Pull Request**

### Diretrizes de Contribuição
- Mantenha o estilo de código existente
- Escreva comentários claros e em português
- Adiciona documentação para novas funcionalidades
- Teste suas alterações em ambiente local antes de submeter
- Respeite as licenças das dependências utilizadas

---

## 📜 Licença e Avisos

Este software é desenvolvido para uso exclusivo da Prefeitura Municipal de Inajá. 

### Avisos Importantes
1. **Funcionalidades de IA**: As funcionalidades baseadas em inteligência artificial são fornecidas como suporte à decisão e não substituem a análise humana qualificada.
2. **Dados Sensíveis**: O sistema armazena dados locaismente. É responsabilidade do usuário garantir a segurança do ambiente onde o sistema é executado.
3. **Integrações Externas**: O uso de APIs externas (OpenRouter, CNPJá) pode estar sujeito a termos de serviço e limitações de uso dos respectivos provedores.
4. **Responsabilidade Fiscal**: O usuário é responsável por garantir que todas as operações realizadas no sistema estejam em conformidade com a legislação aplicável.

### Atualizações
Consulte o arquivo `CHANGELOG_23FEV2026.md` para o histórico detalhado de atualizações, correções de bugs e novas funcionalidades adicionadas ao sistema.

---

*Manual gerado automaticamente em 17/03/2026*
*Para a versão mais recente, consulte o repositório do projeto*