# Sistema de Controle de Empenhos Mensais
**Prefeitura Municipal de Inajá**

Sistema web local para gestão de credores fixos, empenhos mensais, RPAs e extratos bancários.

---

## Como iniciar

**Duplo clique em `iniciar.bat`**

Ou pelo terminal:
```bash
python server.py
```

Acesse em: `http://localhost:5000`

> Requer Python 3.8+. O Flask é instalado automaticamente se não estiver presente.

---

## Estrutura do projeto

```
CREDORES_FIXOS_MENSAIR/
├── server.py               # Servidor Flask + API REST
├── iniciar.bat             # Atalho para iniciar no Windows
├── exportar_dados.py       # Importa credores de planilha Excel → data.js
├── data.js                 # Seed inicial de credores (gerado pelo Excel)
├── empenhos.db             # Banco SQLite (criado automaticamente)
│
├── static/
│   ├── css/index.css       # Estilos globais
│   ├── js/
│   │   ├── app.js          # Lógica JavaScript principal
│   │   └── brasao_b64.js   # Brasão em Base64
│   └── img/brasao.png      # Brasão da Prefeitura
│
├── index.html              # Tela principal — Credores Fixos
├── rpa.html                # Emissão de RPA
├── extratos.html           # Organizador de extratos bancários
├── auditor.html            # Auditoria e logs
├── calendario.html         # Visão por calendário
├── visualizador.html       # Visualizador de documentos
├── gerador-empenho.html    # Geração de empenhos
├── fornecimento.html       # Controle de fornecimento
├── tarefas.html            # Gestão de tarefas
├── tarifas-bancarias.html  # Tarifas bancárias
├── cnpj.html               # Consulta de CNPJs
├── pdf.html                # Ferramentas PDF
├── renomear.html           # Renomeador de extratos
│
└── renomer/                # Módulo Python para organizar extratos (IA + local)
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

- `flask` — servidor web
- `PyPDF2` — manipulação de PDFs
- `openpyxl` — leitura de Excel (opcional, para `exportar_dados.py`)
