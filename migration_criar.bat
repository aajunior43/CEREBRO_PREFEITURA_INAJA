@echo off
REM ============================================================
REM migration_criar.bat — Cria nova migration
REM ============================================================
REM Uso: migration_criar.bat "descricao_da_migration"
REM ============================================================

setlocal enabledelayedexpansion

set DESC=%1

if "%DESC%"=="" (
    echo.
    echo Uso: migration_criar.bat "descricao_da_migration"
    echo Exemplo: migration_criar.bat "adicionar_coluna_telefone"
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   Criar Nova Migration: %DESC%
echo ============================================================
echo.

REM Criar migration
python -m alembic revision -m "%DESC%"

if %errorlevel% equ 0 (
    echo.
    echo ============================================================
    echo   Migration criada com SUCESSO!
    echo ============================================================
    echo.
    echo Edite o arquivo criado em migrations/versions/
    echo e execute: migration_rodar.bat
    echo.
) else (
    echo.
    echo ERRO: Falha ao criar migration!
    echo.
)

pause
