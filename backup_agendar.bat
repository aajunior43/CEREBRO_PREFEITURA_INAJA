@echo off
REM ============================================================
REM backup_agendar.bat — Agenda backup diário no Task Scheduler
REM ============================================================
REM Uso:
REM   backup_agendar.bat              # Agenda com padrão 2:00 AM
REM   backup_agendar.bat 03:00       # Agenda com horário customizado
REM ============================================================

setlocal enabledelayedexpansion

REM ── Configuração ──────────────────────────────────────────
set TASK_NAME=BackupEmpenhosDB
set BACKUP_SCRIPT=%~dp0backup_db.ps1
set LOG_FILE=%~dp0logs\backup.log

REM Horário padrão: 02:00
set SCHEDULE_TIME=%1
if "%SCHEDULE_TIME%"=="" set SCHEDULE_TIME=02:00

REM Dias de retenção (0 = infinito)
set RETENTION_DAYS=30

REM ── Verificações ──────────────────────────────────────────
if not exist "%BACKUP_SCRIPT%" (
    echo.
    echo ERRO: Script de backup não encontrado: %BACKUP_SCRIPT%
    echo.
    pause
    exit /b 1
)

REM Verificar se está rodando como Administrador
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo ERRO: Este script deve ser executado como Administrador.
    echo Clique direito ^>"Executar como administrador^"
    echo.
    pause
    exit /b 1
)

REM ── Verificar se tarefa já existe ─────────────────────────
schtasks /Query /TN "%TASK_NAME%" >nul 2>&1
if %errorlevel% equ 0 (
    echo.
    echo ATENÇÃO: A tarefa '%TASK_NAME%' já existe!
    echo.
    choice /C SN /M "Deseja substituir a tarefa existente"
    if errorlevel 2 (
        echo Operação cancelada.
        pause
        exit /b 0
    )
    echo Removendo tarefa existente...
    schtasks /Delete /TN "%TASK_NAME%" /F >nul 2>&1
)

REM ── Criar tarefa agendada ─────────────────────────────────
echo.
echo ============================================================
echo   Agendando Backup Automático — empenhos.db
echo ============================================================
echo.
echo Nome da tarefa: %TASK_NAME%
echo Script: %BACKUP_SCRIPT%
echo Horário: %SCHEDULE_TIME%
echo Retenção: %RETENTION_DAYS% dias
echo.

REM Comando schtasks para criar a tarefa
REM /RU "" — Executar como usuário atual
REM /RL HIGHEST — Executar com privilégios mais altos
schtasks /Create ^
    /TN "%TASK_NAME%" ^
    /TR "powershell -ExecutionPolicy Bypass -File \"%BACKUP_SCRIPT%\" -RetentionDays %RETENTION_DAYS%" ^
    /SC DAILY ^
    /ST %SCHEDULE_TIME% ^
    /RU "%USERNAME%" ^
    /RL HIGHEST ^
    /F ^
    /DELAY 0001:00

if %errorlevel% equ 0 (
    echo.
    echo ============================================================
    echo   Backup agendado com sucesso!
    echo ============================================================
    echo.
    echo A tarefa '%TASK_NAME%' será executada:
    echo   • Todos os dias às %SCHEDULE_TIME%
    echo   • Retenção: %RETENTION_DAYS% dias
    echo   • Logs: %LOG_FILE%
    echo.
    echo Para ver a tarefa:
    echo   taskschd.msc
    echo.
    echo Para executar manualmente agora:
    echo   schtasks /Run /TN "%TASK_NAME%"
    echo.
    echo Para cancelar o agendamento:
    echo   backup_cancelar.bat
    echo.
    pause
) else (
    echo.
    echo ERRO: Falha ao agendar a tarefa!
    echo Verifique se o Task Scheduler está funcionando.
    echo.
    pause
    exit /b 1
)
