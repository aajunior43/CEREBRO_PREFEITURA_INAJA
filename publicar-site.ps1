# =============================================================================
# publicar-site.ps1 - Publicacao via Cloudflare Tunnel
# Prefeitura Municipal de Inaja
# =============================================================================

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$host.UI.RawUI.WindowTitle = "Prefeitura de Inaja - Cloudflare Tunnel"
Set-Location $PSScriptRoot

function Write-Step  { Write-Host "[>>] $args" -Fore Yellow }
function Write-OK    { Write-Host "[OK] $args" -Fore Green }
function Write-Fail  { Write-Host "[ERRO] $args" -Fore Red }
function Write-Info  { Write-Host "[INFO] $args" -Fore DarkCyan }

# ── 1. Garantir Flask rodando (job em segundo plano) ─────────────────────────
$global:FlaskProc = $null
function Ensure-Flask {
    $conn = Get-NetTCPConnection -LocalPort 5000 -ErrorAction SilentlyContinue
    if ($conn -and $conn.State -eq "Listen") {
        Write-OK "Servidor Flask ja esta rodando na porta 5000."
        return $true
    }
    Write-Step "Flask nao esta rodando. Iniciando em segundo plano..."
    # Matar processos na porta primeiro
    Get-NetTCPConnection -LocalPort 5000 -ErrorAction SilentlyContinue | ForEach-Object {
        Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep 1
    # Procurar Python
    foreach ($cmd in @("python","python3")) {
        $ver = & $cmd --version 2>$null
        if ($ver -match "Python 3") { $py = $cmd; break }
    }
    if (-not $py) { Write-Fail "Python nao encontrado."; return $false }
    # Iniciar Flask como processo oculto
    $global:FlaskProc = Start-Process -FilePath $py -ArgumentList "server.py" -WorkingDirectory $PSScriptRoot -PassThru -WindowStyle Hidden
    Start-Sleep 3
    if (-not $global:FlaskProc.HasExited) { Write-OK "Flask iniciado (PID $($global:FlaskProc.Id))."; return $true }
    Write-Fail "Flask nao iniciou."; return $false
}

# ── 2. Verificar cloudflared.exe ────────────────────────────────────────────
function Find-Cloudflared {
    Write-Step "Procurando cloudflared.exe..."
    $paths = @(
        Join-Path $PSScriptRoot "cloudflared.exe"
        (Get-Command "cloudflared" -ErrorAction SilentlyContinue).Source
    )
    foreach ($p in $paths) { if ($p -and (Test-Path $p)) { Write-OK "Encontrado: $p"; return $p } }
    Write-Fail "cloudflared.exe nao encontrado."
    Write-Info "Baixe em: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/"
    Write-Info "Coloque o .exe na pasta: $PSScriptRoot"
    return $null
}

# ── 3. Iniciar tunnel com timeout ───────────────────────────────────────────
function Start-Tunnel {
    param($CloudflaredPath)
    Write-Step "Iniciando Cloudflare Tunnel..."
    Write-Host "  Aguardando URL publica..." -Fore DarkGray

    $url = $null
    $job = Start-Job -ScriptBlock { param($exe) & $exe tunnel --url http://127.0.0.1:5000 2>&1 } -ArgumentList $CloudflaredPath

    $elapsed = 0
    while ($elapsed -lt 60) {
        Start-Sleep 1; $elapsed++
        $lines = Receive-Job -Job $job -Keep 2>&1
        foreach ($line in $lines) {
            if ($line -match "(https://[a-zA-Z0-9\-]+\.trycloudflare\.com)") {
                $url = $Matches[1]; break
            }
        }
        if ($url) { break }
        if ($job.State -ne "Running") { break }
        if ($elapsed % 5 -eq 0) { Write-Host "  ... $elapsed s" -Fore DarkGray }
    }

    if (-not $url) {
        Write-Fail "Nao foi possivel obter URL do tunnel."
        Stop-Job $job -ErrorAction SilentlyContinue; Remove-Job $job -Force -ErrorAction SilentlyContinue
        return $null
    }
    return @{ Url = $url; Job = $job }
}

# ── 4. Exibir URL ───────────────────────────────────────────────────────────
function Show-URL {
    param($Url)
    Write-Host ""
    Write-Host "============================================================" -Fore Green
    Write-Host "   SITE PÚBLICO DISPONÍVEL!" -Fore Green
    Write-Host "============================================================" -Fore Green
    Write-Host ""
    Write-Host "   $Url" -Fore Cyan
    Write-Host ""
    Write-Host "   Local: http://localhost:5000" -Fore Green
    Write-Host "============================================================" -Fore Green
    Write-Host ""
    try { Set-Clipboard -Value $Url; Write-OK "URL copiada para area de transferencia." } catch {}
    Write-Host "  Pressione Ctrl+C para encerrar." -Fore DarkGray
    Write-Host ""
}

# ── MAIN ────────────────────────────────────────────────────────────────────
try {
    Write-Host ""
    Write-Host "============================================================" -Fore Cyan
    Write-Host "   PREFEITURA MUNICIPAL DE INAJÁ" -Fore Cyan
    Write-Host "   Publicacao via Cloudflare Tunnel" -Fore Cyan
    Write-Host "============================================================" -Fore Cyan
    Write-Host ""

    $cf = Find-Cloudflared
    if (-not $cf) { Read-Host "Enter para sair"; exit 1 }

    $result = Start-Tunnel $cf
    if (-not $result) { Read-Host "Enter para sair"; exit 1 }

    Show-URL $result.Url

    # Aguardar Ctrl+C ou job morrer
    while ($result.Job.State -eq "Running") {
        if ([Console]::KeyAvailable) { $null = [Console]::ReadKey($true); break }
        Start-Sleep 1
    }

} catch { Write-Fail "Erro: $_" }
finally {
    Write-Host ""; Write-Step "Encerrando..."
    Get-Process "cloudflared" -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.Id -Force }
    if ($global:FlaskProc -and !$global:FlaskProc.HasExited) {
        Stop-Process -Id $global:FlaskProc.Id -Force -ErrorAction SilentlyContinue
        Write-OK "Flask encerrado."
    }
    Write-OK "Tunnel encerrado."
    Write-Host ""; Read-Host "Enter para sair"
}
