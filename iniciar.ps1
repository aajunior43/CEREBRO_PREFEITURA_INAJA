# =============================================================================
# CREDORES_FIXOS_MENSAIR - Sistema de Controle de Empenhos Mensais
# Prefeitura Municipal de Inajá
# iniciar.ps1 - Iniciador do Servidor Web Flask
# =============================================================================

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Set-Location $PSScriptRoot

$TITLE = "CREDORES_FIXOS_MENSAIR - Servidor Web"
$host.UI.RawUI.WindowTitle = $TITLE

function Write-Header {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "   CREDORES_FIXOS_MENSAIR - Sistema de Empenhos Mensais" -ForegroundColor Cyan
    Write-Host "   Prefeitura Municipal de Inajá" -ForegroundColor Cyan
    Write-Host "   Iniciando Servidor Web..." -ForegroundColor Cyan
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
# 1. Verificar Python e versao
# ---------------------------------------------------------------------------
function Test-Python {
    Write-Step "Verificando instalacao do Python..."

    $pythonCmd = $null
    foreach ($cmd in @("python", "python3")) {
        try {
            $ver = & $cmd --version 2>&1
            if ($ver -match "Python (\d+)\.(\d+)") {
                $major = [int]$Matches[1]
                $minor = [int]$Matches[2]
                if ($major -gt 3 -or ($major -eq 3 -and $minor -ge 8)) {
                    $pythonCmd = $cmd
                    Write-OK "Python encontrado: $ver (>= 3.8 - compativel)"
                    break
                } else {
                    Write-Fail "Python $ver encontrado, mas e necessario >= 3.8"
                    return $null
                }
            }
        } catch {
            # comando nao encontrado, tentar proximo
        }
    }

    if (-not $pythonCmd) {
        Write-Fail "Python nao encontrado. Instale em https://www.python.org/downloads/"
        return $null
    }

    return $pythonCmd
}

# ---------------------------------------------------------------------------
# 2. Verificar requirements.txt
# ---------------------------------------------------------------------------
function Test-Requirements {
    Write-Step "Verificando requirements.txt..."

    $reqPath = Join-Path $PSScriptRoot "requirements.txt"
    if (-not (Test-Path $reqPath)) {
        Write-Fail "Arquivo requirements.txt nao encontrado em: $reqPath"
        return $false
    }

    Write-OK "requirements.txt encontrado."
    return $true
}

# ---------------------------------------------------------------------------
# 3. Instalar dependencias ausentes
# ---------------------------------------------------------------------------
function Install-Dependencies {
    param([string]$PythonCmd)

    Write-Step "Verificando dependencias Python..."

    $reqPath = Join-Path $PSScriptRoot "requirements.txt"
    $packages = Get-Content $reqPath | Where-Object {
        $_ -notmatch '^\s*#' -and $_.Trim() -ne ""
    } | ForEach-Object {
        # extrair nome do pacote sem versao (ex: flask>=2.0 -> flask)
        ($_ -split '[>=<!]')[0].Trim().ToLower()
    }

    $missing = @()
    foreach ($pkg in $packages) {
        # mapear nomes de pacote para modulos importaveis
        $moduleMap = @{
            "pillow"              = "PIL"
            "beautifulsoup4"      = "bs4"
            "scikit-learn"        = "sklearn"
            "pyyaml"              = "yaml"
        }
        $importName = if ($moduleMap.ContainsKey($pkg)) { $moduleMap[$pkg] } else { $pkg }

        $check = & $PythonCmd -c "import $importName" 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Host "    [ ] $pkg - NAO instalado" -ForegroundColor DarkYellow
            $missing += $pkg
        } else {
            Write-Host "    [v] $pkg" -ForegroundColor DarkGreen
        }
    }

    if ($missing.Count -eq 0) {
        Write-OK "Todas as dependencias ja estao instaladas."
        return $true
    }

    Write-Step "Instalando $($missing.Count) pacote(s) ausente(s)..."
    try {
        & $PythonCmd -m pip install @($missing) --quiet
        if ($LASTEXITCODE -ne 0) {
            Write-Fail "Falha ao instalar dependencias. Execute manualmente: pip install -r requirements.txt"
            return $false
        }
        Write-OK "Dependencias instaladas com sucesso."
    } catch {
        Write-Fail "Erro ao executar pip: $_"
        return $false
    }

    return $true
}

# ---------------------------------------------------------------------------
# 4. Liberar porta 5000
# ---------------------------------------------------------------------------
function Clear-Port5000 {
    Write-Step "Verificando porta 5000..."

    $connections = Get-NetTCPConnection -LocalPort 5000 -ErrorAction SilentlyContinue
    if (-not $connections) {
        Write-OK "Porta 5000 disponivel."
        return
    }

    foreach ($conn in $connections) {
        $pid = $conn.OwningProcess
        if ($pid -and $pid -ne 0) {
            try {
                $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
                $procName = if ($proc) { $proc.Name } else { "PID $pid" }
                Write-Step "Encerrando processo '$procName' (PID $pid) que usa a porta 5000..."
                Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
                Write-OK "Processo encerrado."
            } catch {
                Write-Fail "Nao foi possivel encerrar o processo na porta 5000: $_"
            }
        }
    }

    Start-Sleep -Seconds 1
    $recheck = Get-NetTCPConnection -LocalPort 5000 -ErrorAction SilentlyContinue
    if ($recheck) {
        Write-Fail "A porta 5000 ainda esta em uso. Tente encerrar o processo manualmente."
    } else {
        Write-OK "Porta 5000 liberada."
    }
}

# ---------------------------------------------------------------------------
# 5. Obter IPs locais
# ---------------------------------------------------------------------------
function Get-LocalIPs {
    $ips = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object {
            $_.IPAddress -notmatch '^127\.' -and
            $_.IPAddress -notmatch '^169\.254\.' -and
            $_.PrefixOrigin -ne 'WellKnown'
        } |
        Select-Object -ExpandProperty IPAddress

    return $ips
}

# ---------------------------------------------------------------------------
# 6. Iniciar servidor e monitorar
# ---------------------------------------------------------------------------
function Start-FlaskServer {
    param([string]$PythonCmd)

    $appFile = $null
    foreach ($name in @("app.py", "main.py", "server.py", "run.py")) {
        $candidate = Join-Path $PSScriptRoot $name
        if (Test-Path $candidate) {
            $appFile = $candidate
            break
        }
    }

    if (-not $appFile) {
        Write-Fail "Nenhum arquivo de aplicacao encontrado (app.py, main.py, server.py, run.py)."
        return
    }

    Write-OK "Arquivo de aplicacao: $appFile"
    Write-Host ""

    # Abrir browser apos 2 segundos em job separado
    $null = Start-Job -ScriptBlock {
        Start-Sleep -Seconds 2
        Start-Process "http://localhost:5000"
    }

    # Exibir URLs
    $localIPs = Get-LocalIPs
    Write-Host "------------------------------------------------------------" -ForegroundColor DarkCyan
    Write-Host "  Servidor disponivel em:" -ForegroundColor White
    Write-Host "    Local:   http://localhost:5000" -ForegroundColor Green
    foreach ($ip in $localIPs) {
        Write-Host "    Rede:    http://${ip}:5000" -ForegroundColor Green
    }
    Write-Host "------------------------------------------------------------" -ForegroundColor DarkCyan
    Write-Host "  Pressione Ctrl+C para encerrar o servidor." -ForegroundColor DarkGray
    Write-Host ""

    $restartCount = 0

    while ($true) {
        try {
            if ($restartCount -gt 0) {
                Write-Step "Reiniciando servidor (tentativa $restartCount)..."
            } else {
                Write-Step "Iniciando servidor Flask..."
            }

            $proc = Start-Process `
                -FilePath $PythonCmd `
                -ArgumentList "`"$appFile`"" `
                -WorkingDirectory $PSScriptRoot `
                -PassThru `
                -NoNewWindow

            Write-OK "Servidor iniciado (PID $($proc.Id))."
            $proc.WaitForExit()
            $exitCode = $proc.ExitCode

            Write-Host ""
            if ($exitCode -eq 0) {
                Write-Host "[INFO] Servidor encerrado normalmente." -ForegroundColor DarkGray
                break
            } else {
                $restartCount++
                Write-Fail "Servidor encerrou com codigo $exitCode."
                Write-Step "O servidor sera reiniciado em 3 segundos... (Ctrl+C para cancelar)"
                Start-Sleep -Seconds 3
            }
        } catch {
            Write-Fail "Erro ao iniciar o servidor: $_"
            break
        }
    }
}

# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
try {
    Write-Header

    # Criar atalho na area de trabalho na primeira execucao
    $desktop = [System.Environment]::GetFolderPath('Desktop')
    $lnkPath = Join-Path $desktop 'CREDORES - Iniciar Servidor.lnk'
    if (-not (Test-Path $lnkPath)) {
        try {
            $wsh = New-Object -ComObject WScript.Shell
            $lnk = $wsh.CreateShortcut($lnkPath)
            $lnk.TargetPath       = 'powershell.exe'
            $lnk.Arguments        = "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
            $lnk.WorkingDirectory = $PSScriptRoot
            $lnk.Description      = 'CREDORES - Iniciar Servidor Web Flask'
            $lnk.IconLocation     = 'powershell.exe,0'
            $lnk.Save()
            Write-OK "Atalho 'CREDORES - Iniciar Servidor.lnk' criado na area de trabalho."
        } catch {}
    }

    $pythonCmd = Test-Python
    if (-not $pythonCmd) {
        Read-Host "Pressione Enter para sair"
        exit 1
    }

    if (-not (Test-Requirements)) {
        Read-Host "Pressione Enter para sair"
        exit 1
    }

    if (-not (Install-Dependencies -PythonCmd $pythonCmd)) {
        Read-Host "Pressione Enter para sair"
        exit 1
    }

    Clear-Port5000

    Start-FlaskServer -PythonCmd $pythonCmd

} catch {
    Write-Fail "Erro inesperado: $_"
} finally {
    Write-Host ""
    Write-Host "Servidor encerrado." -ForegroundColor DarkGray
    Read-Host "Pressione Enter para sair"
}
