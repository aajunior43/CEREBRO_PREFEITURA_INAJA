@echo off
REM ============================================================
REM migration_rodar.bat — Executa migrations pendentes
REM ============================================================

setlocal enabledelayedexpansion

echo.
echo ============================================================
echo   Executar Migrations — empenhos.db
echo ============================================================
echo.

REM Verificar se arquivo de migration existe
if not exist "%~dp0migrations\versions" (
    echo ERRO: Pasta de migrations não encontrada!
    echo Execute: migration_criar.bat
    pause
    exit /b 1
)

REM Executar upgrade
python -m alembic upgrade head

if %errorlevel% equ 0 (
    echo.
    echo ============================================================
    echo   Migrations executadas com SUCESSO!
    echo ============================================================
    echo.
) else (
    echo.
    echo ERRO: Falha ao executar migrations!
    echo.
)

pause
