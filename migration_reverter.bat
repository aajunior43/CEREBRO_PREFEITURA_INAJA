@echo off
REM ============================================================
REM migration_reverter.bat — Reverte última migration
REM ============================================================

setlocal enabledelayedexpansion

echo.
echo ============================================================
echo   Reverter Última Migration — empenhos.db
echo ============================================================
echo.

choice /C SN /M "Deseja reverter a última migration"
if errorlevel 2 (
    echo Operação cancelada.
    pause
    exit /b 0
)

echo.
echo Revertendo migration...
python -m alembic downgrade -1

if %errorlevel% equ 0 (
    echo.
    echo ============================================================
    echo   Migration revertida com SUCESSO!
    echo ============================================================
    echo.
) else (
    echo.
    echo ERRO: Falha ao reverter migration!
    echo.
)

pause
