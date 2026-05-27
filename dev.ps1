# =============================================================================
# dev.ps1 - Ambiente de Desenvolvimento
# Ativa DEBUG e delega ao iniciar.ps1
# =============================================================================

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$host.UI.RawUI.WindowTitle = "Prefeitura de Inaja - Servidor (DEV)"
Set-Location $PSScriptRoot

$env:APP_DEBUG = "1"
$env:APP_RELOADER = "1"

Write-Host ""
Write-Host "  MODO DESENVOLVIMENTO" -Fore DarkCyan
Write-Host "  DEBUG ativado, reloader automatico ligado." -Fore DarkCyan
Write-Host ""

& "$PSScriptRoot\iniciar.ps1" -Tunnel

