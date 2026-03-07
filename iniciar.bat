@echo off
title Sistema de Empenhos - Prefeitura Municipal de Inaja
color 0B

cd /d "%~dp0"

echo.
echo  ============================================================
echo   Sistema de Controle de Empenhos Mensais
echo   Prefeitura Municipal de Inaja
echo  ============================================================
echo.

:: Verifica Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  ERRO: Python nao encontrado!
    echo  Instale em: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

:: Instala dependencias se necessario
python -c "import flask, PyPDF2, openpyxl" >nul 2>&1
if errorlevel 1 (
    echo  Instalando dependencias do projeto, aguarde...
    python -m pip install -r requirements.txt --quiet
    echo  Dependencias instaladas com sucesso!
    echo.
)

:: Libera a porta 5000 se ja estiver em uso
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":5000 "') do (
    taskkill /F /PID %%a >nul 2>&1
)

echo  Iniciando servidor...
echo.
echo  >> Acesse Local: http://localhost:5000
for /f "tokens=*" %%i in ('powershell -NoProfile -Command "(Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notmatch 'Loopback|VirtualBox|VMware' }).IPAddress[0]"') do set LOCAL_IP=%%i
echo  >> Acesse Rede:  http://%LOCAL_IP%:5000
echo.
echo  >> Para ENCERRAR: feche esta janela
echo.
echo  ============================================================
echo.

:: Abre o navegador apos 2 segundos
start "" /B cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:5000"

:: Inicia o servidor (mantem a janela aberta)
python -u server.py

echo.
echo  Servidor encerrado.
pause
