# =============================================================================
# iniciar.ps1 - Servidor Web Flask
# Prefeitura Municipal de Inaja - Cérebro Municipal
# =============================================================================

param(
    [switch]$Tunnel
)

# Configurar console
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$host.UI.RawUI.WindowTitle = "CÉREBRO MUNICIPAL - Prefeitura de Inajá"
Set-Location $PSScriptRoot

# Cores e Formatação
function Write-Step {
    Write-Host "  ⚙️  [AGUARDANDO] " -NoNewline -ForegroundColor Yellow
    Write-Host $args -ForegroundColor White
}

function Write-OK {
    Write-Host "  ✅ [SUCESSO]    " -NoNewline -ForegroundColor Green
    Write-Host $args -ForegroundColor Gray
}

function Write-Fail {
    Write-Host "  ❌ [ERRO]       " -NoNewline -ForegroundColor Red
    Write-Host $args -ForegroundColor DarkRed
}

function Write-Info {
    Write-Host "  ℹ️  [INFO]       " -NoNewline -ForegroundColor Cyan
    Write-Host $args -ForegroundColor Gray
}

# ── 1. Checar Python ────────────────────────────────────────────────────────
function Find-Python {
    Write-Step "Verificando ambiente Python..."
    foreach ($cmd in @("python", "python3")) {
        try {
            $ver = & $cmd --version 2>&1
            if ($ver -match "Python (\d+)\.(\d+)") {
                if (([int]$Matches[1] -gt 3) -or ($Matches[1] -eq 3 -and [int]$Matches[2] -ge 8)) {
                    Write-OK "Python detectado: $ver"
                    return $cmd
                }
            }
        } catch {}
    }
    Write-Fail "Python 3.8 ou superior não encontrado no PATH."
    return $null
}

# ── 2. Instalar dependencias ────────────────────────────────────────────────
function Install-Deps {
    param($PythonCmd)
    Write-Step "Verificando integridade das dependências..."
    $missing = @()
    $packages = (Get-Content requirements.txt) | Where { $_ -match '\S' -and $_ -notmatch '^\s*#' }
    $modMap = @{ "Flask"="flask"; "tavily-python"="tavily"; "pillow"="PIL"; "beautifulsoup4"="bs4"; "pyyaml"="yaml"; "scikit-learn"="sklearn" }
    
    foreach ($pkg in $packages) {
        $mod = $pkg -split '[>=<!]' | Select -First 1
        if ($modMap.ContainsKey($mod)) { $mod = $modMap[$mod] }
        & $PythonCmd -c "import $mod" 2>$null
        if ($LASTEXITCODE -ne 0) {
            $missing += $pkg
            Write-Host "    [✖] Falta: $pkg" -ForegroundColor DarkYellow
        } else {
            Write-Host "    [✔] OK: $pkg" -ForegroundColor Green
        }
    }
    if ($missing.Count -eq 0) {
        Write-OK "Todas as dependências estão presentes."
        return $true
    }
    Write-Step "Instalando $($missing.Count) pacote(s) pendente(s)..."
    & $PythonCmd -m pip install @missing --quiet
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "Falha ao instalar pacotes via pip."
        return $false
    }
    Write-OK "Dependências instaladas com sucesso!"
    return $true
}

# ── 3. Liberar porta 5000 ───────────────────────────────────────────────────
function Clear-Port {
    Write-Step "Verificando disponibilidade da porta 5000..."
    $conns = Get-NetTCPConnection -LocalPort 5000 -ErrorAction SilentlyContinue
    if (-not $conns) {
        Write-OK "Porta 5000 está livre."
        return
    }
    foreach ($c in $conns) {
        $pid = $c.OwningProcess
        try {
            $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
            $procName = if ($proc) { $proc.ProcessName } else { "Desconhecido" }
            Write-Info "Finalizando processo em uso na porta 5000: $procName (PID: $pid)..."
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
        } catch {
            Write-Fail "Não foi possível encerrar PID $pid na porta 5000."
        }
    }
    Start-Sleep 1
    Write-OK "Porta 5000 liberada."
}

# ── 4. Exibir IPs de rede ───────────────────────────────────────────────────
function Show-URLs {
    Write-Host "  ┌──────────────────────────────────────────────────────────┐" -ForegroundColor Cyan
    Write-Host "  │                   ENDEREÇOS DE ACESSO                    │" -ForegroundColor Cyan
    Write-Host "  ├──────────────────────────────────────────────────────────┤" -ForegroundColor Cyan
    
    $localUrl = "http://127.0.0.1:5000"
    $lineLocal = "  │   Local:  $localUrl"
    $padLocal = 61 - $lineLocal.Length
    $lineLocal = $lineLocal + (" " * $padLocal) + "│"
    Write-Host $lineLocal -ForegroundColor Green

    $ips = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where { $_.IPAddress -notmatch '^127\.|^169\.254\.' -and $_.PrefixOrigin -ne 'WellKnown' }
    foreach ($ip in $ips) {
        $ipStr = "http://$($ip.IPAddress):5000"
        $line = "  │   Rede:   $ipStr"
        $pad = 61 - $line.Length
        if ($pad -gt 0) { $line = $line + (" " * $pad) + "│" }
        else { $line = $line + " │" }
        Write-Host $line -ForegroundColor Cyan
    }
    Write-Host "  └──────────────────────────────────────────────────────────┘" -ForegroundColor Cyan
}

# ── 5. Cloudflare Tunnel functions ──────────────────────────────────────────
function Find-Cloudflared {
    Write-Step "Procurando executável do cloudflared..."
    $paths = @(
        Join-Path $PSScriptRoot "cloudflared.exe"
        (Get-Command "cloudflared" -ErrorAction SilentlyContinue).Source
    )
    foreach ($p in $paths) {
        if ($p -and (Test-Path $p)) {
            Write-OK "Cloudflared encontrado em: $p"
            return $p
        }
    }
    Write-Fail "cloudflared.exe não encontrado."
    Write-Info "Coloque o cloudflared.exe na pasta raiz: $PSScriptRoot"
    return $null
}

function Start-Tunnel {
    param($CloudflaredPath)
    Write-Step "Iniciando túnel Cloudflare para acesso externo..."
    Write-Host "  Aguardando geração da URL pública..." -ForegroundColor DarkGray

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
        Write-Fail "Não foi possível obter a URL do túnel do Cloudflare."
        Stop-Job $job -ErrorAction SilentlyContinue; Remove-Job $job -Force -ErrorAction SilentlyContinue
        return $null
    }
    return @{ Url = $url; Job = $job }
}

# ── MAIN ────────────────────────────────────────────────────────────────────
try {
    Clear-Host
    Write-Host ""
    Write-Host "  ┌──────────────────────────────────────────────────────────┐" -ForegroundColor Green
    Write-Host "  │               PREFEITURA MUNICIPAL DE INAJÁ              │" -ForegroundColor Green
    Write-Host "  │        🧠 CÉREBRO MUNICIPAL - PAINEL DE CONTROLE 🧠      │" -ForegroundColor Green
    Write-Host "  └──────────────────────────────────────────────────────────┘" -ForegroundColor Green
    Write-Host ""
    
    # ASCII Art do CÉREBRO
    Write-Host "   ██████╗███████╗██████╗ ███████╗██████╗ ██████╗  ██████╗  " -ForegroundColor Cyan
    Write-Host "  ██╔════╝██╔════╝██╔══██╗██╔════╝██╔══██╗██╔══██╗██╔═══██╗ " -ForegroundColor Cyan
    Write-Host "  ██║     █████╗  ██████╔╝█████╗  ██████╔╝██████╔╝██║   ██║ " -ForegroundColor Green
    Write-Host "  ██║     ██╔══╝  ██╔══██╗██╔══╝  ██╔══██╗██╔══██╗██║   ██║ " -ForegroundColor Green
    Write-Host "  ╚██████╗███████╗██║  ██║███████╗██████╔╝██║  ██║╚██████╔╝ " -ForegroundColor Yellow
    Write-Host "   ╚═════╝╚══════╝╚═╝  ╚═╝╚══════╝╚═════╝ ╚═╝  ╚═╝ ╚═════╝  " -ForegroundColor Yellow
    Write-Host ""

    $py = Find-Python
    if (-not $py) { Read-Host "Pressione Enter para sair"; exit 1 }

    if (-not (Install-Deps $py)) { Read-Host "Pressione Enter para sair"; exit 1 }

    Clear-Port

    $tunnelJob = $null
    if ($Tunnel) {
        $cf = Find-Cloudflared
        if ($cf) {
            $result = Start-Tunnel $cf
            if ($result) {
                $tunnelJob = $result.Job
                Write-Host ""
                Write-Host "  ┌──────────────────────────────────────────────────────────┐" -ForegroundColor Magenta
                Write-Host "  │            🔗 TÚNEL PÚBLICO ATIVADO (EXTERNO)            │" -ForegroundColor Magenta
                Write-Host "  ├──────────────────────────────────────────────────────────┤" -ForegroundColor Magenta
                
                $urlStr = "Url:    $($result.Url)"
                $line = "  │   $urlStr"
                $pad = 61 - $line.Length
                if ($pad -gt 0) { $line = $line + (" " * $pad) + "│" }
                else { $line = $line + " │" }
                Write-Host $line -ForegroundColor Magenta
                
                Write-Host "  └──────────────────────────────────────────────────────────┘" -ForegroundColor Magenta
                Write-Host ""
                try { Set-Clipboard -Value $result.Url; Write-OK "URL copiada para a área de transferência!" } catch {}
                Write-Host ""
            }
        }
    }

    Write-Step "Iniciando servidor Flask de Produção/Dev..."
    Write-Host ""

    Show-URLs
    Write-Host ""
    Write-Host "  [!] Servidor ativo. Pressione Ctrl+C para encerrar com segurança." -ForegroundColor Yellow
    Write-Host ""

    & $py server.py
    Write-Host ""
    Write-Info "Servidor encerrado."

} catch {
    Write-Fail "Erro crítico na execução: $_"
} finally {
    if ($tunnelJob) {
        Write-Step "Finalizando túnel Cloudflare..."
        Stop-Job $tunnelJob -ErrorAction SilentlyContinue
        Remove-Job $tunnelJob -Force -ErrorAction SilentlyContinue
        Get-Process "cloudflared" -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }
        Write-OK "Túnel encerrado."
    }
    Read-Host "Pressione Enter para fechar esta janela"
}
