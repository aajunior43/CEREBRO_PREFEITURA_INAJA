@echo off
setlocal
cd /d "%~dp0"

if not exist "cloudflared.exe" (
  echo [ERRO] cloudflared.exe nao encontrado na pasta do projeto.
  echo Baixe o executavel novamente antes de publicar.
  pause
  exit /b 1
)

echo.
echo Iniciando Cloudflare Quick Tunnel para http://localhost:5000
echo O link publico aparecera abaixo.
echo Mantenha esta janela aberta para o site continuar acessivel fora da rede local.
echo.

cloudflared.exe tunnel --url http://localhost:5000

endlocal
