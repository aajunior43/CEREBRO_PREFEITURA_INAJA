@echo off
title [DEV] Sistema de Empenhos
color 0E

cd /d "%~dp0"

echo.
echo  ============================================================
echo   MODO DESENVOLVIMENTO (AUTO-RELOAD ATIVADO)
echo  ============================================================
echo.

:: Libera a porta 5000 se ja estiver em uso
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":5000 "') do (
    taskkill /F /PID %%a >nul 2>&1
)

set APP_DEBUG=1

echo  Iniciando servidor em modo debug...
echo  Qualquer alteracao em arquivos .py vai reiniciar automaticamente.
echo.

python -u server.py

echo.
echo  Servidor encerrado.
pause
