@echo off
REM ============================================================
REM migration_status.bat — Verifica status das migrations
REM ============================================================

setlocal enabledelayedexpansion

echo.
echo ============================================================
echo   Status das Migrations — empenhos.db
echo ============================================================
echo.

REM Mostrar histórico
python -m alembic history --verbose

echo.
echo ============================================================
echo   Status Atual
echo ============================================================
echo.

python -m alembic current

echo.
echo ============================================================
echo   Migrations Pendentes
echo ============================================================
echo.

python -m alembic heads

echo.
pause
