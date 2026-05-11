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
