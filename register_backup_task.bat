@echo off
:: register_backup_task.bat
:: Registra a tarefa de backup automático no Windows Task Scheduler.
:: Execute UMA VEZ como Administrador.

set TASK_NAME=CerebroBackupDB
set SCRIPT_PATH=%~dp0backup_db.bat

echo Registrando tarefa "%TASK_NAME%" no Agendador de Tarefas...
echo Script: %SCRIPT_PATH%
echo Frequencia: a cada 30 minutos, indefinidamente

:: Remove tarefa anterior se existir
schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1

:: Cria a tarefa:
::   /SC MINUTE /MO 30  = a cada 30 minutos
::   /ST 00:00          = começa à meia-noite (próxima ocorrência)
::   /RI 30             = repete a cada 30 min
::   /DU 9999:59        = duração indefinida (~416 dias, máximo permitido)
::   /RU SYSTEM         = roda como SYSTEM (não precisa de login do usuário)
::   /F                 = força sobrescrever
schtasks /create ^
  /tn "%TASK_NAME%" ^
  /tr "\"%SCRIPT_PATH%\"" ^
  /sc MINUTE ^
  /mo 30 ^
  /st 00:00 ^
  /f

if %ERRORLEVEL% equ 0 (
    echo.
    echo Tarefa registrada com sucesso!
    echo.
    echo Para verificar: schtasks /query /tn "%TASK_NAME%"
    echo Para remover:   schtasks /delete /tn "%TASK_NAME%" /f
    echo Para rodar agora: schtasks /run /tn "%TASK_NAME%"
) else (
    echo.
    echo ERRO ao registrar a tarefa. Execute este arquivo como Administrador.
)

pause
