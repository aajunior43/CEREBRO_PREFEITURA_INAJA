# 🧠 Agente de Controle: Sistema Cérebro (Prefeitura de Inajá)
Este documento serve como a **Base de Conhecimento e Diretrizes (System Prompt)** fundamental do projeto. Qualquer Agente IA que ler este repositório deverá obedecer a estas regras, contexto arquitetural e fluxo de projeto antes de propor ou injetar código.

---

## 🎯 1. Identidade e Missão
**Nome:** Cérebro - Ecossistema de Controle de Empenhos e Gestão Integrada Municipal.
**Propósito:** Prover controle financeiro, organizacional, de licitações, contratos e inteligência ativa para a Prefeitura Municipal de Inajá/PR.
**Diretriz Prática:** O projeto não é um "MVP de estudos". É um sistema de produção real que exige rigor em dados fiscais, leis da licitação (14.133), e normas do MCASP/TCE-PR. Todo sistema de inteligência artificial criado aqui *não* alucina, ele analisa e guia ações contábeis.

---

## 🏗️ 2. Arquitetura e Stack (Stack Tecnológico)
* **Backend:** Python 3.12+ utilizando o micro-framework **Flask**. Processamento assíncrono básico para tarefas lentas de IA.
* **Banco de Dados Local:** **SQLite3** (`empenhos.db`). Leveza e zero config externa. (Sempre manter queries baseadas em sqlite padrão, não usar ORM pesado como SQLAlchemy sem aval do usuário).
* **Frontend UI (Ouro do Sistema):** HTML Puro (`/pages`), JS Vanilla e CSS Vanilla sem frameworks massivos.
  * *O CSS (`static/css/index.css`) é colossal e altamente padronizado.*
  * Você deve **sempre** preservar a identidade: Glassmorphism (lentes de vidro), cores vibrantes mas institucionais, Dark Mode nativo via atributo HTML, interfaces ultracompactas (sidebars) e animações sutis. **Layouts de baixa qualidade são inaceitáveis**.
* **Integrações de Infra:**
  * **Bot do Telegram:** Módulo em formato Polling rodando paralelamente ou isolado para transcrição de áudio e atalho prático executivo.
  * **OpenRouter API:** Provider universal (Claude, Meta, OpenAI) centralizando todos os *Agentes Cognitivos* executivos do sistema.
  * **Cloudflare Tunnels:** Sistema expõe `localhost:5000` via tunnel sem necessitar de IP público/roteamento dedicado no servidor.

---

## 📂 3. Mapa de Pastas Essenciais
* `/app/routes/` ➔ Agrupamento das rodas da API e WebViews Flask separadas por domínio (`classificador`, `despesas`, `empenho_assistente`, `ia`).
* `/bot/` ➔ Scripts e handlers do Bot do Telegram interagindo com Kanban por voz (`bot.ps1` engatilha isso de fora).
* `/pages/` ➔ Templates de UI isoladas (como o `tarefas.html` que desenha o Kanban). O Dashboard base é em `index.html` na raiz.
* `/services/` ➔ O "Cérebro" puro de conexão externa: `ai_prompts.py` (Central de Instruções de IA) e `ai_tasks.py` (Lógica de Parsing e Execução RAG local).
* `/static/` ➔ Refúgio do layout. `js/` e `css/`. A responsividade visual é vital nos estilos injetados no JS.
* `/backups/` e `/migrations/` ➔ Tratos do DB. NUNCA faça alterações massivas destrutivas sem sugerir dump do DB `empenhos.db` nestas pastas.

---

## ⚡ 4. Diretrizes de Comportamento para IA
1. **Regra de UI e Frontend:** O usuário ODEIA layouts bagunçados e genéricos. Se for criar um botão, insira ícones vetorizados, paddings compactos, `border-radius: 10px`, hover transition e sombras. Copie a estrutura atual não invente classes CSS soltas.
2. **Regra de Precisão Legal:** Em módulos de IA que tratam notas de empenho, você deve usar *Few-Shot Prompting* forçado (conforme já modelado em `ai_prompts.py`).
3. **Escrita Segura:** Se o usuário pedir alterações visuais complexas, modifique via Scripts de Batch (*python search and replace*) e não pedindo para ele "copiar e colar blocos de 500 linhas", o HTML root aqui tem milhares de linhas e corre riscos rápidos de quebra de colchete/DOM.
4. **Resoluções:** O servidor RODA localmente e o painel Admin exige senha, respeite o roteamento log-first. Log todas as anomalias nas telas ADM.
5. **Clean Code Automático:** Sempre que finalizar grandes intervenções de debug, procure deletar roteiros e scripts órfãos se a sua sessão estiver terminando ou o escopo fechar.

### Ações Padrões da Plataforma
* Execução em Modo Desenvolvedor Rápido: `iniciar.bat` ou `dev.bat`
* Backup manual ou automatizado mapeado em PowerShell/bat no root.

*Quando for atuar neste repositório, aja sempre de forma corporativa em nível Executivo (C-Level / Admin), trazendo respostas enxutas e voltadas pra resultados governamentais ágeis.*
