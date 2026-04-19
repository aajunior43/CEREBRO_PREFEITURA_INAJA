@echo off
REM ============================================================
REM backup_restaurar.bat — Restaura backup do empenhos.db
REM ============================================================
REM Uso:
REM   backup_restaurar.bat              # Restaura backup mais recente
REM   backup_restaurar.bat nome_arquivo # Restaura backup específico
REM ============================================================

setlocal enabledelayedexpansion

set BACKUP_DIR=%~dp0backups
set DB_FILE=%~dp0empenhos.db
set DB_BACKUP_DIR=%~dp0backups

REM ── Verificações ──────────────────────────────────────────
if not exist "%DB_BACKUP_DIR%" (
    echo.
    echo ERRO: Pasta de backups não encontrada: %DB_BACKUP_DIR%
    echo.
    pause
    exit /b 1
)

REM Listar backups disponíveis
echo.
echo ============================================================
echo   Backups Disponíveis para Restauração
echo ============================================================
echo.

set COUNT=0
set LATEST=

for /f "delims=" %%F in ('dir /b /o-d "%DB_BACKUP_DIR%\empenhos_backup_*.db" 2^>nul') do (
    set /a COUNT+=1
    if !COUNT! equ 1 set LATEST=%%F
    for %%S in ("%%~zF") do set SIZE=%%~zS
    echo  !COUNT!. %%F  (!SIZE! bytes^)
)

if !COUNT! equ 0 (
    echo Nenhum backup encontrado em: %DB_BACKUP_DIR%
    echo.
    pause
    exit /b 1
)

echo.
echo Total: !COUNT! backup(s)
echo.

REM Determinar qual backup restaurar
set RESTORE_FILE=%1
if "%RESTORE_FILE%"=="" (
    echo Restaurar o backup mais recente: %LATEST%
    choice /C SN /M "Confirmar"
    if errorlevel 2 (
        echo Operação cancelada.
        pause
        exit /b 0
    )
    set RESTORE_FILE=%LATEST%
)

REM Verificar se arquivo existe
if not exist "%DB_BACKUP_DIR%\%RESTORE_FILE%" (
    echo.
    echo ERRO: Backup não encontrado: %RESTORE_FILE%
    echo.
    pause
    exit /b 1
)

REM ── Confirmar restauração ───────────────────────────────
echo.
echo ============================================================
echo   ATENÇÃO — Restauração de Backup
echo ============================================================
echo.
echo Backup: %RESTORE_FILE%
echo Destino: %DB_FILE%
echo.
echo Isso irá SUBSTITUIR o banco de dados atual pelo backup.
echo Todas as alterações feitas após este backup serão PERDIDAS.
echo.

choice /C SN /M "Confirmar restauração"
if errorlevel 2 (
    echo.
    echo Operação cancelada.
    pause
    exit /b 0
)

REM ── Criar backup do banco atual antes de restaurar ───────
if exist "%DB_FILE%" (
    echo.
    echo Criando backup do banco atual...
    set TIMESTAMP=%DATE:/=-%_%TIME::=-%
    set TIMESTAMP=%TIMESTAMP: =0%
    set BACKUP_BEFORE=%DB_BACKUP_DIR%\antes_restauracao_%TIMESTAMP%.db

    copy "%DB_FILE%" "%BACKUP_BEFORE%" >nul 2>&1
    if !errorlevel! equ 0 (
        echo Backup do banco atual criado: antes_restauracao_%TIMESTAMP%.db
    ) else (
        echo AVISO: Falha ao criar backup do banco atual.
        choice /C SN /M "Continuar mesmo assim"
        if errorlevel 2 (
            echo Operação cancelada.
            pause
            exit /b 0
        )
    )
)

REM ── Restaurar backup ─────────────────────────────────────
echo.
echo Restaurando backup...
copy "%DB_BACKUP_DIR%\%RESTORE_FILE%" "%DB_FILE%" >nul 2>&1

if !errorlevel! equ 0 (
    echo.
    echo ============================================================
    echo   Backup restaurado com SUCESSO!
    echo ============================================================
    echo.
    echo Arquivo: %RESTORE_FILE%
    echo Destino: %DB_FILE%
    echo.
    echo Reinicie o servidor Flask para usar o banco restaurado.
    echo.
) else (
    echo.
    echo ERRO: Falha ao restaurar backup!
    echo.
)

pause
