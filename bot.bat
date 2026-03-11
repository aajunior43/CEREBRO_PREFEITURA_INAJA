@echo off
chcp 65001 >nul
title Bot Telegram - Prefeitura de Inajá

echo =====================================================
echo   BOT TELEGRAM - Sistema da Prefeitura de Inajá
echo =====================================================
echo.

REM Verifica se .env existe
if not exist ".env" (
    echo [AVISO] Arquivo .env nao encontrado!
    echo Crie o arquivo .env com as seguintes variaveis:
    echo.
    echo   TELEGRAM_TOKEN=seu_token_aqui
    echo   TELEGRAM_CHAT_ID=seu_chat_id_aqui
    echo.
    echo Veja o arquivo .env.exemplo para referencia.
    echo.
    pause
    exit /b 1
)

REM Instala dependências se necessário
echo Verificando dependencias...
pip show requests >nul 2>&1
if errorlevel 1 (
    echo Instalando requests...
    pip install requests
)

echo.
echo [OK] Iniciando bot do Telegram...
echo [OK] Pressione Ctrl+C para parar o bot
echo.

python telegram_bot.py

echo.
echo Bot encerrado.
pause
