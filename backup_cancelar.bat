@echo off
REM ============================================================
REM backup_cancelar.bat — Remove backup agendado do Task Scheduler
REM ============================================================
REM Uso:
REM   backup_cancelar.bat
REM ============================================================

setlocal enabledelayedexpansion

set TASK_NAME=BackupEmpenhosDB

REM ── Verificar se está rodando como Administrador ─────────
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo ERRO: Este script deve ser executado como Administrador.
    echo Clique direito ^>"Executar como administrador^"
    echo.
    pause
    exit /b 1
)

REM ── Verificar se tarefa existe ───────────────────────────
schtasks /Query /TN "%TASK_NAME%" >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo ATENÇÃO: A tarefa '%TASK_NAME%' não existe.
    echo Nenhum backup agendado para cancelar.
    echo.
    pause
    exit /b 0
)

REM ── Mostrar informações da tarefa ────────────────────────
echo.
echo ============================================================
echo   Backup Agendado — Informações
echo ============================================================
echo.
schtasks /Query /TN "%TASK_NAME%" /V /FO LIST | findstr /C:"TaskName" /C:"Status" /C:"Next Run Time" /C:"Last Run Time" /C:"Task To Run"
echo.

REM ── Confirmar cancelamento ───────────────────────────────
choice /C SN /M "Deseja cancelar o backup agendado"
if errorlevel 2 (
    echo.
    echo Operação cancelada. O backup continuará sendo executado.
    pause
    exit /b 0
)

REM ── Remover tarefa ───────────────────────────────────────
echo.
echo Removendo tarefa '%TASK_NAME%'...
schtasks /Delete /TN "%TASK_NAME%" /F

if %errorlevel% equ 0 (
    echo.
    echo ============================================================
    echo   Backup agendado CANCELADO com sucesso!
    echo ============================================================
    echo.
    echo A tarefa '%TASK_NAME%' foi removida do Task Scheduler.
    echo.
    echo Os backups existentes na pasta 'backups/' NÃO foram removidos.
    echo Para removê-los manualmente, delete a pasta:
    echo   %~dp0backups\
    echo.
    pause
) else (
    echo.
    echo ERRO: Falha ao remover a tarefa!
    echo Verifique o Task Scheduler manualmente:
    echo   taskschd.msc
    echo.
    pause
    exit /b 1
)
