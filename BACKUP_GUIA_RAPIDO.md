# Guia Rápido — Backup Automatizado

## Visão Geral
Sistema de backup automatizado do banco de dados `empenhos.db` com agendamento diário via Task Scheduler do Windows.

---

## Instalação (5 minutos)

### 1. Agendar Backup Diário
```bat
backup_agendar.bat
```
- Executa **todos os dias às 02:00 AM**
- Mantém backups dos **últimos 30 dias**
- Logs em `logs/backup.log`

### 2. Confirmar Agendamento
```bat
schtasks /Query /TN "BackupEmpenhosDB"
```

---

## Comandos Principais

| Ação | Comando |
|------|---------|
| **Executar backup agora** | `python backup_db.py` |
| **Verificar último backup** | `python backup_db.py --verify` |
| **Listar backups** | `python backup_db.py --list` |
| **Restaurar backup** | `backup_restaurar.bat` |
| **Cancelar agendamento** | `backup_cancelar.bat` |

---

## Como Funciona

### Backup Automático
1. **Cópia íntegra** do `empenhos.db`
2. **Verificação de integridade** via SQLite PRAGMA
3. **Hash SHA256** para validação
4. **Rotação automática** (remove backups > 30 dias)
5. **Log detalhado** em `logs/backup.log`

### Estrutura de Arquivos
```
backups/
├── empenhos_backup_20260411_020000.db          ← Backup
├── empenhos_backup_20260411_020000.db.sha256   ← Hash de validação
└── ...
```

### Restauração Segura
- Cria **backup automático** do banco atual antes de restaurar
- Lista todos os backups disponíveis
- Permite escolher backup específico

---

## Personalização

### Alterar Horário
```bat
backup_agendar.bat 03:30
```

### Alterar Retenção
Edite `backup_agendar.bat`:
```bat
set RETENTION_DAYS=60    ← Manter 60 dias
```

### Executar via PowerShell
```powershell
.\backup_db.ps1 -RetentionDays 60
.\backup_db.ps1 -Verify
.\backup_db.ps1 -List
```

---

## Troubleshooting

### Backup não executa
1. Verifique Task Scheduler: `taskschd.msc`
2. Procure tarefa `BackupEmpenhosDB`
3. Execute manualmente: `schtasks /Run /TN "BackupEmpenhosDB"`

### Verificar Logs
```bat
type logs\backup.log
```

### Espaço em Disco
- Cada backup tem ~3 MB
- 30 dias = ~90 MB total
- Ajuste retenção conforme necessário

---

## Boas Práticas

✅ **Manter retenção mínima de 30 dias**
✅ **Verificar backups semanalmente**
✅ **Testar restauração periodicamente**
✅ **Monitorar logs regularmente**
✅ **Executar como Administrador**

---

## Suporte

Para dúvidas ou problemas, consulte:
- `README.md` — Documentação completa
- `logs/backup.log` — Logs de execução
- Task Scheduler (`taskschd.msc`) — Gerenciamento de tarefas
