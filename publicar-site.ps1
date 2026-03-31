# =============================================================================
# CREDORES_FIXOS_MENSAIR - Sistema de Controle de Empenhos Mensais
# Prefeitura Municipal de Inajá
# publicar-site.ps1 - Publicacao via Cloudflare Tunnel
# =============================================================================

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Set-Location $PSScriptRoot

$host.UI.RawUI.WindowTitle = "CREDORES_FIXOS_MENSAIR - Cloudflare Tunnel"

function Write-Header {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "   CREDORES_FIXOS_MENSAIR - Sistema de Empenhos Mensais" -ForegroundColor Cyan
    Write-Host "   Prefeitura Municipal de Inajá" -ForegroundColor Cyan
    Write-Host "   Publicando site via Cloudflare Tunnel..." -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host ""
}

function Write-Step {
    param([string]$Message)
    Write-Host "[>>] $Message" -ForegroundColor Yellow
}

function Write-OK {
    param([string]$Message)
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-Fail {
    param([string]$Message)
    Write-Host "[ERRO] $Message" -ForegroundColor Red
}

# ---------------------------------------------------------------------------
# 1. Verificar cloudflared.exe
# ---------------------------------------------------------------------------
function Get-CloudflaredPath {
    Write-Step "Procurando cloudflared.exe..."

    # Primeiro: ao lado do script
    $localPath = Join-Path $PSScriptRoot "cloudflared.exe"
    if (Test-Path $localPath) {
        Write-OK "cloudflared.exe encontrado em: $localPath"
        return $localPath
    }

    # Segundo: no PATH do sistema
    $inPath = Get-Command "cloudflared" -ErrorAction SilentlyContinue
    if ($inPath) {
        Write-OK "cloudflared encontrado no PATH: $($inPath.Source)"
        return $inPath.Source
    }

    Write-Fail "cloudflared.exe nao encontrado."
    Write-Host ""
    Write-Host "  Baixe em: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/" -ForegroundColor DarkCyan
    Write-Host "  Coloque o cloudflared.exe na mesma pasta deste script:" -ForegroundColor DarkCyan
    Write-Host "  $PSScriptRoot" -ForegroundColor DarkCyan
    Write-Host ""
    return $null
}

# ---------------------------------------------------------------------------
# 2. Iniciar tunnel e capturar URL
# ---------------------------------------------------------------------------
function Start-CloudflareTunnel {
    param([string]$CloudflaredPath)

    Write-Step "Iniciando Cloudflare Tunnel para http://localhost:5000 ..."
    Write-Host "  Aguardando URL publica (pode levar alguns segundos)..." -ForegroundColor DarkGray
    Write-Host ""

    $publicUrl = $null

    # Usar job para capturar saida linha a linha
    $scriptBlock = {
        param($exe)
        & $exe tunnel --url http://localhost:5000 2>&1
    }

    $job = Start-Job -ScriptBlock $scriptBlock -ArgumentList $CloudflaredPath

    $timeout = 60   # segundos maximos esperando URL
    $elapsed = 0
    $checkInterval = 1

    while ($elapsed -lt $timeout) {
        Start-Sleep -Seconds $checkInterval
        $elapsed += $checkInterval

        $output = Receive-Job -Job $job -Keep 2>&1
        foreach ($line in ($output -split "`n")) {
            if ($line -match "(https://[a-zA-Z0-9\-]+\.trycloudflare\.com)") {
                $publicUrl = $Matches[1].Trim()
                break
            }
        }

        if ($publicUrl) { break }

        # Verificar se o job terminou inesperadamente
        if ($job.State -eq "Failed" -or $job.State -eq "Completed") {
            Write-Fail "Cloudflared encerrou antes de fornecer uma URL."
            $errOutput = Receive-Job -Job $job 2>&1
            Write-Host $errOutput -ForegroundColor DarkRed
            Remove-Job -Job $job -Force
            return $null
        }

        Write-Host "  ... aguardando ($elapsed s)" -ForegroundColor DarkGray
    }

    if (-not $publicUrl) {
        Write-Fail "Tempo esgotado aguardando URL do tunnel."
        Stop-Job -Job $job
        Remove-Job -Job $job -Force
        return $null
    }

    return @{ Url = $publicUrl; Job = $job }
}

# ---------------------------------------------------------------------------
# 3. Exibir URL e copiar para clipboard
# ---------------------------------------------------------------------------
function Show-TunnelUrl {
    param([string]$Url)

    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "   SITE PUBLICO DISPONIVEL!" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "   URL publica:" -ForegroundColor White
    Write-Host "   $Url" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host ""

    try {
        Set-Clipboard -Value $Url
        Write-OK "URL copiada para a area de transferencia (Ctrl+V para colar)."
    } catch {
        Write-Host "[AVISO] Nao foi possivel copiar para o clipboard: $_" -ForegroundColor DarkYellow
    }

    Write-Host ""
    Write-Host "  O tunnel permanecera ativo ate voce pressionar qualquer tecla." -ForegroundColor DarkGray
    Write-Host "  Mantenha esta janela aberta." -ForegroundColor DarkGray
    Write-Host ""
}

# ---------------------------------------------------------------------------
# 4. Aguardar tecla e encerrar
# ---------------------------------------------------------------------------
function Wait-AndCleanup {
    param($Job)

    Write-Host "  Pressione qualquer tecla para encerrar o tunnel..." -ForegroundColor DarkGray

    # Loop: checar se job ainda esta rodando e aguardar tecla
    while ($true) {
        if ([Console]::KeyAvailable) {
            $null = [Console]::ReadKey($true)
            break
        }
        if ($Job.State -ne "Running") {
            Write-Host ""
            Write-Fail "O tunnel encerrou inesperadamente."
            break
        }
        Start-Sleep -Milliseconds 500
    }

    Write-Host ""
    Write-Step "Encerrando Cloudflare Tunnel..."

    try {
        Stop-Job -Job $Job -ErrorAction SilentlyContinue
        Remove-Job -Job $Job -Force -ErrorAction SilentlyContinue
    } catch {}

    # Garantir que nao restou processo cloudflared
    $procs = Get-Process -Name "cloudflared" -ErrorAction SilentlyContinue
    foreach ($p in $procs) {
        try { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue } catch {}
    }

    Write-OK "Tunnel encerrado."
}

# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
try {
    Write-Header

    # Criar atalho na area de trabalho na primeira execucao
    $desktop = [System.Environment]::GetFolderPath('Desktop')
    $lnkPath = Join-Path $desktop 'CREDORES - Publicar Site.lnk'
    if (-not (Test-Path $lnkPath)) {
        try {
            $wsh = New-Object -ComObject WScript.Shell
            $lnk = $wsh.CreateShortcut($lnkPath)
            $lnk.TargetPath       = 'powershell.exe'
            $lnk.Arguments        = "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
            $lnk.WorkingDirectory = $PSScriptRoot
            $lnk.Description      = 'CREDORES - Publicar Site via Cloudflare Tunnel'
            $lnk.IconLocation     = 'powershell.exe,0'
            $lnk.Save()
            Write-OK "Atalho 'CREDORES - Publicar Site.lnk' criado na area de trabalho."
        } catch {}
    }

    $cfPath = Get-CloudflaredPath
    if (-not $cfPath) {
        Read-Host "Pressione Enter para sair"
        exit 1
    }

    $result = Start-CloudflareTunnel -CloudflaredPath $cfPath
    if (-not $result) {
        Read-Host "Pressione Enter para sair"
        exit 1
    }

    Show-TunnelUrl -Url $result.Url

    Wait-AndCleanup -Job $result.Job

} catch {
    Write-Fail "Erro inesperado: $_"
} finally {
    Write-Host ""
    Write-Host "Publicacao encerrada." -ForegroundColor DarkGray
    Read-Host "Pressione Enter para sair"
}
