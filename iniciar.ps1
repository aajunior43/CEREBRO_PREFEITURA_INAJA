# =============================================================================
# iniciar.ps1 - Servidor Web Flask
# Prefeitura Municipal de Inaja
# =============================================================================

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$host.UI.RawUI.WindowTitle = "Prefeitura de Inaja - Servidor Web"
Set-Location $PSScriptRoot

function Write-Step  { Write-Host "[>>] $args" -Fore Yellow }
function Write-OK    { Write-Host "[OK] $args" -Fore Green }
function Write-Fail  { Write-Host "[ERRO] $args" -Fore Red }
function Write-Info  { Write-Host "[INFO] $args" -Fore DarkCyan }

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
    $modMap = @{ "pillow"="PIL"; "beautifulsoup4"="bs4"; "pyyaml"="yaml"; "scikit-learn"="sklearn" }
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
    Write-Host "    Local: http://localhost:5000" -Fore Green
    $ips = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where { $_.IPAddress -notmatch '^127\.|^169\.254\.' -and $_.PrefixOrigin -ne 'WellKnown' }
    foreach ($ip in $ips) { Write-Host "    Rede:  http://$($ip.IPAddress):5000" -Fore Green }
}

# ── MAIN ────────────────────────────────────────────────────────────────────
try {
    Write-Host ""
    Write-Host "============================================================" -Fore Cyan
    Write-Host "   PREFEITURA MUNICIPAL DE INAJÁ" -Fore Cyan
    Write-Host "   Sistema de Controle de Empenhos" -Fore Cyan
    Write-Host "============================================================" -Fore Cyan
    Write-Host ""

    $py = Find-Python
    if (-not $py) { Read-Host "Enter para sair"; exit 1 }

    if (-not (Install-Deps $py)) { Read-Host "Enter para sair"; exit 1 }

    Clear-Port

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
finally { Read-Host "Enter para sair" }
