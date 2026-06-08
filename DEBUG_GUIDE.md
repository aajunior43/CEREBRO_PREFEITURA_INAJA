# Guia de Diagnóstico e Depuração (Debug Guide)

Este guia documenta o sistema de monitoramento, logs e diagnóstico do Cérebro Prefeitura de Inajá. Ele é voltado para desenvolvedores e administradores de TI responsáveis por diagnosticar e mitigar problemas de infraestrutura e comportamento em produção.

---

## 📂 Arquivos Chave de Diagnóstico

### 1. Arquivo de Logs (`logs/server.log`)
Todos os logs do servidor Flask, incluindo inicialização, auditorias de acesso seguras, requisições lentas e erros de sistema (com tracebacks completos) são registrados em:
* **Caminho:** `logs/server.log`
* **Rotação:** O arquivo de log rotaciona automaticamente ao atingir 2 MB, mantendo até 3 backups (`server.log.1`, `server.log.2`, etc.).
* **Nível Ativo:** `INFO` (captura inicialização, logouts, logins, auditorias de segurança e erros).

### 2. Banco de Dados SQLite (`empenhos.db`)
O arquivo do banco de dados SQLite principal:
* **Caminho:** `empenhos.db` (gerido em WAL mode para concorrência segura).
* **Backups:** Automatizados via script `backup_db.py`.

---

## 🪵 Estrutura e Formato dos Logs

Cada linha do arquivo `logs/server.log` segue a estrutura padronizada abaixo:
```text
2026-06-03 21:30:15,123 [INFO] (server:1310) Todos os 22 blueprints registrados com sucesso.
```

Campos:
1. `Timestamp` (`YYYY-MM-DD HH:MM:SS,fff`): Data e hora exatas do evento.
2. `LogLevel` (`[INFO]`, `[WARNING]`, `[ERROR]`, `[CRITICAL]`): Severidade da ocorrência.
3. `Source` (`(module_name:line_number)`): Módulo/arquivo python e a linha exata onde o log foi disparado (essencial para debug rápido).
4. `Message`: Mensagem descritiva detalhada.

---

## 🛠️ Endpoints de Monitoramento (Health Checks)

### 1. Monitoramento Público (`/api/health`)
Endpoint leve e público para serviços de monitoramento de uptime (como UptimeRobot, Zabbix ou Prometheus). **Não exige credenciais de autenticação**.
* **URL:** `GET /api/health`
* **Resposta típica (JSON):**
  ```json
  {
    "status": "ok",
    "db": true,
    "uptime_s": 3600,
    "error_count": 0,
    "slow_requests": 2,
    "cache_files": 45,
    "cache_gzip": 45
  }
  ```
* Se o banco falhar ou o sistema registrar mais de 10 erros críticos em RAM, o `status` passa para `"degraded"`.

### 2. Resumo Técnico e Operacional (`/api/admin/summary`)
Exposto diretamente na Área Administrativa do painel web. **Exige autenticação como administrador (`admin`/`adm`)**.
* **URL:** `GET /api/admin/summary`
* Fornece o estado atual completo da aplicação, incluindo:
  - Resumos operacionais (total de credores ativos, RPAs, tarefas kanban, importações CSV e logs).
  - Status e contagem de chaves de APIs integradas (OpenRouter, CNPJá, Autentique, Tavily).
  - Métricas de cache de arquivos estáticos em RAM.
  - Informações de ambiente técnico (IP de escuta, porta, modo debug, caminhos absolutos do DB e logs).
  - Últimas 8 entradas da tabela de auditoria operacional (`logs`).

---

## 🚨 Resolução de Problemas Comuns (Troubleshooting)

### 1. `Database is locked` (Banco de Dados Bloqueado)
**Sintoma:** Erro de escrita/leitura ocorrendo de forma intermitente com mensagem do SQLite.
* **Causa:** SQLite em concorrência pesada. Embora o WAL mode e timeouts elevados (10 segundos) estejam habilitados, conexões que abrem transações longas ou falham em fechar a conexão de thread-local podem segurar o lock.
* **Mitigação:**
  1. Verifique se há algum processo pendente de backup (`backup_db.py`) segurando lock na tabela.
  2. Garanta que todas as conexões abertas manualmente executem `conn.close()` no encerramento (o Flask já faz isso nativamente no middleware `teardown_appcontext`).

### 2. `Timeout` na compilação de LaTeX (PDFs de RPAs/Empenhos)
**Sintoma:** O arquivo de log registra `TimeoutExpired` do comando `pdflatex.EXE` após 45 segundos.
* **Causa:** O compilador MiKTeX ou TexLive entrou em loop infinito devido a um caractere ou template LaTeX quebrado, ou está tentando baixar pacotes em tempo real sem internet.
* **Mitigação:**
  1. Instale todos os pacotes LaTeX necessários em modo offline no servidor de antemão.
  2. Verifique se o caminho da pasta temporária do sistema possui permissões de escrita/leitura.

### 3. Erros `429` ou Limites de Requisições na IA (OpenRouter)
**Sintoma:** Falha na IA ao processar extratos ou classificações de despesa; warnings `ia.fallback` no log do servidor.
* **Causa:** Limite de cota de requisições por minuto/dia atingido na API de IA gratuita.
* **Mitigação:**
  - O sistema possui retentativas nativas com backoff exponencial e fallback automático para modelos reservas (definidos em `services/openrouter_service.py`).
  - Caso os erros persistam, o administrador deve cadastrar uma chave API paga ou trocar para o provedor OpenCode Go nas configurações administrativas.

### 4. Requisições Lentas (`Slow request`)
**Sintoma:** Logs do tipo `Slow request 144634.9ms POST /api/empenho-assistente [200]` no nível de `WARNING`.
* **Causa:** Rotas de IA, consultas em lote ou compilação de PDFs demoradas. O limite para disparo do alerta é de 250ms.
* **Mitigação:**
  - Requisições que batem na IA (como leitura de extratos ou classificação) são inerentemente lentas e esperadas.
  - Para rotas normais de banco de dados, verifique a criação de índices executando `ensure_db_indexes(cur)` no script de migração do banco.

---

## 🧪 Executando Testes de Validação

Para certificar-se de que a estrutura e conexões do servidor estão íntegras após qualquer manutenção:
```bash
# Executa a suíte de testes de sanidade estrutural e de endpoints
python tests/test_app_structure.py
```
Se tudo estiver correto, a saída finalizará com a mensagem `TODOS OS TESTES PASSARAM!`.
