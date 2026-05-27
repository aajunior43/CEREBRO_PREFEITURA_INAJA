# =============================================================================
# iniciar.ps1 - Servidor Web Flask
# Prefeitura Municipal de Inaja
# =============================================================================

param(
    [switch]$Tunnel
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$host.UI.RawUI.WindowTitle = "Prefeitura de Inaja - Servidor Web"
Set-Location $PSScriptRoot

function Write-Step  { Write-Host "  => [AGUARDANDO] $args" -Fore Yellow }
function Write-OK    { Write-Host "  [OK] $args" -Fore Green }
function Write-Fail  { Write-Host "  [ERRO] $args" -Fore Red }
function Write-Info  { Write-Host "  [INFO] $args" -Fore Cyan }

# ── 1. Checar Python ────────────────────────────────────────────────────────
function Find-Python {
    Write-Step "Verificando Python..."
    foreach ($cmd in @("python", "python3")) {
        try {
            $ver = & $cmd --version 2>&1
            if ($ver -match "Python (\d+)\.(\d+)") {
                if (([int]$Matches[1] -gt 3) -or ($Matches[1] -eq 3 -and [int]$Matches[2] -ge 8)) {
                    Write-OK "Python $((& $cmd --version 2>&1))"
                    return $cmd
                }
            }
        } catch {}
    }
    Write-Fail "Python >= 3.8 nao encontrado."
    return $null
}

# ── 2. Instalar dependencias ────────────────────────────────────────────────
function Install-Deps {
    param($PythonCmd)
    Write-Step "Verificando dependencias..."
    $missing = @()
    $packages = (Get-Content requirements.txt) | Where { $_ -match '\S' -and $_ -notmatch '^\s*#' }
    $modMap = @{ "Flask"="flask"; "tavily-python"="tavily"; "pillow"="PIL"; "beautifulsoup4"="bs4"; "pyyaml"="yaml"; "scikit-learn"="sklearn" }
    foreach ($pkg in $packages) {
        $mod = $pkg -split '[>=<!]' | Select -First 1
        if ($modMap.ContainsKey($mod)) { $mod = $modMap[$mod] }
        & $PythonCmd -c "import $mod" 2>$null
        if ($LASTEXITCODE -ne 0) { $missing += $pkg; Write-Host "    [ ] $pkg" -Fore DarkYellow }
        else { Write-Host "    [v] $pkg" -Fore DarkGreen }
    }
    if ($missing.Count -eq 0) { Write-OK "Todas as dependencias instaladas."; return $true }
    Write-Step "Instalando $($missing.Count) pacote(s)..."
    & $PythonCmd -m pip install @missing --quiet
    if ($LASTEXITCODE -ne 0) { Write-Fail "Falha ao instalar."; return $false }
    Write-OK "Dependencias instaladas."
    return $true
}

# ── 3. Liberar porta 5000 ───────────────────────────────────────────────────
function Clear-Port {
    $conns = Get-NetTCPConnection -LocalPort 5000 -ErrorAction SilentlyContinue
    if (-not $conns) { Write-OK "Porta 5000 livre."; return }
    foreach ($c in $conns) {
        try { Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue } catch {}
    }
    Start-Sleep 1
    Write-OK "Porta 5000 liberada."
}

# ── 4. Exibir IPs de rede ───────────────────────────────────────────────────
function Show-URLs {
    Write-Host "  +----------------------------------------------------------+" -Fore DarkGreen
    Write-Host "  |                     ENDERECOS LOCAIS                     |" -Fore DarkGreen
    Write-Host "  +----------------------------------------------------------+" -Fore DarkGreen
    Write-Host "  |                                                          |" -Fore DarkGreen
    Write-Host "  |   Local:  http://127.0.0.1:5000                          |" -Fore Green
    
    $ips = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where { $_.IPAddress -notmatch '^127\.|^169\.254\.' -and $_.PrefixOrigin -ne 'WellKnown' }
    foreach ($ip in $ips) {
        $ipStr = "http://$($ip.IPAddress):5000"
        $line = "  |   Rede:   $ipStr"
        $pad = 61 - $line.Length
        if ($pad -gt 0) { $line = $line + (" " * $pad) + "|" }
        else { $line = $line + " |" }
        Write-Host $line -Fore Green
    }
    
    Write-Host "  |                                                          |" -Fore DarkGreen
    Write-Host "  +----------------------------------------------------------+" -Fore DarkGreen
}

# ── 5. Cloudflare Tunnel functions ──────────────────────────────────────────
function Find-Cloudflared {
    Write-Step "Procurando cloudflared.exe..."
    $paths = @(
        Join-Path $PSScriptRoot "cloudflared.exe"
        (Get-Command "cloudflared" -ErrorAction SilentlyContinue).Source
    )
    foreach ($p in $paths) { if ($p -and (Test-Path $p)) { Write-OK "Encontrado: $p"; return $p } }
    Write-Fail "cloudflared.exe nao encontrado."
    Write-Info "Coloque o .exe na pasta: $PSScriptRoot"
    return $null
}

function Start-Tunnel {
    param($CloudflaredPath)
    Write-Step "Iniciando Cloudflare Tunnel..."
    Write-Host "  Aguardando URL publica..." -Fore DarkGray

    $url = $null
    $job = Start-Job -ScriptBlock { param($exe) & $exe tunnel --url http://127.0.0.1:5000 2>&1 } -ArgumentList $CloudflaredPath

    $elapsed = 0
    while ($elapsed -lt 30) {
        Start-Sleep 1; $elapsed++
        $lines = Receive-Job -Job $job -Keep 2>&1
        foreach ($line in $lines) {
            if ($line -match "(https://[a-zA-Z0-9\-]+\.trycloudflare\.com)") {
                $url = $Matches[1]; break
            }
        }
        if ($url) { break }
        if ($job.State -ne "Running") { break }
    }

    if (-not $url) {
        Write-Fail "Nao foi possivel obter URL do tunnel."
        Stop-Job $job -ErrorAction SilentlyContinue; Remove-Job $job -Force -ErrorAction SilentlyContinue
        return $null
    }
    return @{ Url = $url; Job = $job }
}

# ── MAIN ────────────────────────────────────────────────────────────────────
try {
    Write-Host ""
    Write-Host "  +----------------------------------------------------------+" -Fore Cyan
    Write-Host "  |              PREFEITURA MUNICIPAL DE INAJA               |" -Fore Cyan
    Write-Host "  |             SISTEMA DE CONTROLE DE EMPENHOS              |" -Fore Cyan
    Write-Host "  +----------------------------------------------------------+" -Fore Cyan
    Write-Host ""
    Write-Host "   __  __ _    _ _____          _" -Fore Magenta
    Write-Host "  |  \/  | |  | |  __ \   /\   | |" -Fore Magenta
    Write-Host "  | \  / | |  | | |__) | /  \  | |" -Fore Magenta
    Write-Host "  | |\/| | |  | |  _  / / /\ \ | |" -Fore Magenta
    Write-Host "  | |  | | |__| | | \ \/ ____ \| |____" -Fore Magenta
    Write-Host "  |_|  |_|\____/|_|  \_\_/    \_\______|" -Fore Magenta
    Write-Host ""

    $py = Find-Python
    if (-not $py) { Read-Host "Enter para sair"; exit 1 }

    if (-not (Install-Deps $py)) { Read-Host "Enter para sair"; exit 1 }

    Clear-Port

    $tunnelJob = $null
    if ($Tunnel) {
        $cf = Find-Cloudflared
        if ($cf) {
            $result = Start-Tunnel $cf
            if ($result) {
                $tunnelJob = $result.Job
                Write-Host ""
                Write-Host "  +----------------------------------------------------------+" -Fore Green
                Write-Host "  |                SITE PUBLICO ATIVADO (DEV)                |" -Fore Green
                Write-Host "  +----------------------------------------------------------+" -Fore Green
                Write-Host "  |                                                          |" -Fore Green
                
                $urlStr = "  Url:    $($result.Url)"
                $line = "  | $urlStr"
                $pad = 61 - $line.Length
                if ($pad -gt 0) { $line = $line + (" " * $pad) + "|" }
                else { $line = $line + " |" }
                Write-Host $line -Fore Cyan
                
                Write-Host "  |                                                          |" -Fore Green
                Write-Host "  +----------------------------------------------------------+" -Fore Green
                Write-Host ""
                try { Set-Clipboard -Value $result.Url; Write-OK "URL copiada para a area de transferencia." } catch {}
                Write-Host ""
            }
        }
    }

    Write-Step "Iniciando servidor Flask..."
    Write-Host ""

    Show-URLs
    Write-Host ""
    Write-Host "  Pressione Ctrl+C para encerrar." -Fore DarkGray
    Write-Host ""

    & $py server.py
    Write-Host ""
    Write-Info "Servidor encerrado."

} catch { Write-Fail "Erro: $_" }
finally {
    if ($tunnelJob) {
        Write-Step "Encerrando Cloudflare Tunnel..."
        Stop-Job $tunnelJob -ErrorAction SilentlyContinue
        Remove-Job $tunnelJob -Force -ErrorAction SilentlyContinue
        Get-Process "cloudflared" -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }
        Write-OK "Tunnel encerrado."
    }
    Read-Host "Enter para sair"
}
