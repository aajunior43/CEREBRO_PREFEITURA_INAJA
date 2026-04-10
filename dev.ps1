# =============================================================================
# CREDORES_FIXOS_MENSAIR - Sistema de Controle de Empenhos Mensais
# Prefeitura Municipal de Inajá
# dev.ps1 - Ambiente de Desenvolvimento Completo
#           Flask + Cloudflare Tunnel + Telegram Bot
# =============================================================================

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Set-Location $PSScriptRoot

$host.UI.RawUI.WindowTitle = "CREDORES_FIXOS_MENSAIR - DEV"

# ---------------------------------------------------------------------------
# Helpers de output
# ---------------------------------------------------------------------------
function Write-Header {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "   CREDORES_FIXOS_MENSAIR - Ambiente de Desenvolvimento" -ForegroundColor Cyan
    Write-Host "   Prefeitura Municipal de Inajá" -ForegroundColor Cyan
    Write-Host "   Flask + Cloudflare Tunnel + Bot Telegram" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host ""
}

function Write-Starting {
    param([string]$Component)
    Write-Host "[INICIANDO] $Component..." -ForegroundColor Yellow
}

function Write-OK {
    param([string]$Message)
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-Fail {
    param([string]$Message)
    Write-Host "[ERRO] $Message" -ForegroundColor Red
}

function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor DarkCyan
}

function Write-Separator {
    Write-Host "------------------------------------------------------------" -ForegroundColor DarkGray
}

# ---------------------------------------------------------------------------
# Parsear arquivo .env (suporte a comentarios, espacos, aspas)
# ---------------------------------------------------------------------------
function Read-EnvFile {
    param([string]$EnvPath)
    $envVars = @{}
    if (-not (Test-Path $EnvPath)) { return $envVars }

    Get-Content $EnvPath -Encoding UTF8 | ForEach-Object {
        $trimmed = $_.Trim()
        if ($trimmed -eq "" -or $trimmed.StartsWith("#")) { return }

        $eqIndex = $trimmed.IndexOf('=')
        if ($eqIndex -le 0) { return }

        $key   = $trimmed.Substring(0, $eqIndex).Trim()
        $value = $trimmed.Substring($eqIndex + 1).Trim()

        if (($value.StartsWith('"') -and $value.EndsWith('"')) -or
            ($value.StartsWith("'") -and $value.EndsWith("'"))) {
            $value = $value.Substring(1, $value.Length - 2)
        }

        if ($value -match '^([^#]*?)\s*#') { $value = $Matches[1].Trim() }

        $envVars[$key] = $value
    }
    return $envVars
}

# ---------------------------------------------------------------------------
# Encontrar Python >= 3.8
# ---------------------------------------------------------------------------
function Get-PythonCommand {
    foreach ($cmd in @("python", "python3")) {
        try {
            $ver = & $cmd --version 2>&1
            if ($ver -match "Python (\d+)\.(\d+)") {
                if ([int]$Matches[1] -gt 3 -or ([int]$Matches[1] -eq 3 -and [int]$Matches[2] -ge 8)) {
                    return $cmd
                }
            }
        } catch {}
    }
    return $null
}

# ---------------------------------------------------------------------------
# Encontrar arquivo de aplicacao Flask
# ---------------------------------------------------------------------------
function Get-AppFile {
    foreach ($name in @("app.py", "main.py", "server.py", "run.py")) {
        $p = Join-Path $PSScriptRoot $name
        if (Test-Path $p) { return $p }
    }
    return $null
}

# ---------------------------------------------------------------------------
# Encontrar arquivo do bot
# ---------------------------------------------------------------------------
function Get-BotFile {
    foreach ($name in @("bot.py", "telegram_bot.py", "main_bot.py", "telegram-bot.py")) {
        $p = Join-Path $PSScriptRoot $name
        if (Test-Path $p) { return $p }
    }
    return $null
}

# ---------------------------------------------------------------------------
# Liberar porta 5000
# ---------------------------------------------------------------------------
function Clear-Port5000 {
    $conns = Get-NetTCPConnection -LocalPort 5000 -ErrorAction SilentlyContinue
    foreach ($conn in $conns) {
        $procId = $conn.OwningProcess
        if ($procId -and $procId -ne 0) {
            try { Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue } catch {}
        }
    }
}

# ---------------------------------------------------------------------------
# Aguardar porta 5000 responder (max 20s)
# ---------------------------------------------------------------------------
function Wait-ForFlask {
    Write-Starting "Aguardando Flask responder na porta 5000"

    $maxWait   = 20
    $elapsed   = 0
    $interval  = 1

    while ($elapsed -lt $maxWait) {
        $test = Test-NetConnection -ComputerName "localhost" -Port 5000 -WarningAction SilentlyContinue -InformationLevel Quiet
        if ($test) {
            Write-OK "Flask respondendo em http://localhost:5000 (${elapsed}s)"
            return $true
        }
        Start-Sleep -Seconds $interval
        $elapsed += $interval
        Write-Host "  ... aguardando porta 5000 ($elapsed/$maxWait s)" -ForegroundColor DarkGray
    }

    Write-Fail "Flask nao respondeu em ${maxWait}s."
    return $false
}

# ---------------------------------------------------------------------------
# Iniciar Flask como background job
# ---------------------------------------------------------------------------
function Start-FlaskJob {
    param([string]$PythonCmd, [string]$AppFile, [string]$WorkDir)

    Write-Starting "Servidor Flask"
    Clear-Port5000

    $job = Start-Job -ScriptBlock {
        param($py, $app, $wd)
        Set-Location $wd
        $env:APP_DEBUG    = '1'
        $env:APP_RELOADER = '1'
        & $py $app 2>&1
    } -ArgumentList $PythonCmd, $AppFile, $WorkDir

    Write-OK "Servidor Flask iniciado (Job ID: $($job.Id))"
    return $job
}

# ---------------------------------------------------------------------------
# Iniciar Cloudflare Tunnel como background job e capturar URL
# ---------------------------------------------------------------------------
function Start-CloudflareJob {
    param([string]$CloudflaredPath, [string]$WorkDir)

    Write-Starting "Cloudflare Tunnel"

    $job = Start-Job -ScriptBlock {
        param($exe, $wd)
        Set-Location $wd
        & $exe tunnel --url http://localhost:5000 2>&1
    } -ArgumentList $CloudflaredPath, $WorkDir

    # Aguardar URL (max 60s)
    $timeout  = 60
    $elapsed  = 0
    $publicUrl = $null

    while ($elapsed -lt $timeout) {
        Start-Sleep -Seconds 2
        $elapsed += 2

        $output = Receive-Job -Job $job -Keep 2>&1
        foreach ($line in ($output -split "`n")) {
            if ($line -match "(https://[a-zA-Z0-9\-]+\.trycloudflare\.com)") {
                $publicUrl = $Matches[1].Trim()
                break
            }
        }

        if ($publicUrl) { break }

        if ($job.State -ne "Running") {
            Write-Fail "Cloudflared encerrou inesperadamente."
            $errOut = Receive-Job -Job $job 2>&1
            Write-Host $errOut -ForegroundColor DarkRed
            Remove-Job -Job $job -Force
            return $null
        }

        Write-Host "  ... aguardando URL do tunnel ($elapsed s)" -ForegroundColor DarkGray
    }

    if (-not $publicUrl) {
        Write-Fail "Tempo esgotado aguardando URL do tunnel."
        Stop-Job -Job $job
        Remove-Job -Job $job -Force
        return $null
    }

    Write-OK "Tunnel ativo: $publicUrl"
    return @{ Url = $publicUrl; Job = $job }
}

# ---------------------------------------------------------------------------
# Iniciar Bot Telegram em foreground
# ---------------------------------------------------------------------------
function Start-BotForeground {
    param([string]$PythonCmd, [string]$BotFile)

    Write-Starting "Bot Telegram"
    Write-Info "O bot sera executado em primeiro plano. Pressione Ctrl+C para encerrar tudo."
    Write-Host ""

    try {
        $proc = Start-Process `
            -FilePath $PythonCmd `
            -ArgumentList "`"$BotFile`"" `
            -WorkingDirectory $PSScriptRoot `
            -PassThru `
            -NoNewWindow

        Write-OK "Bot Telegram iniciado (PID $($proc.Id))."
        $proc.WaitForExit()
    } catch {
        Write-Fail "Erro ao iniciar bot: $_"
    }
}

# ---------------------------------------------------------------------------
# Limpeza geral ao sair
# ---------------------------------------------------------------------------
function Invoke-Cleanup {
    param([System.Management.Automation.Job[]]$Jobs)

    Write-Host ""
    Write-Separator
    Write-Starting "Encerrando todos os componentes"

    foreach ($job in $Jobs) {
        if ($job -and $job.State -eq "Running") {
            try {
                Stop-Job -Job $job -ErrorAction SilentlyContinue
                Write-OK "Job $($job.Name) (ID $($job.Id)) encerrado."
            } catch {}
        }
        if ($job) {
            try { Remove-Job -Job $job -Force -ErrorAction SilentlyContinue } catch {}
        }
    }

    # Matar cloudflared remanescente
    $cfProcs = Get-Process -Name "cloudflared" -ErrorAction SilentlyContinue
    foreach ($p in $cfProcs) {
        try {
            Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
            Write-OK "cloudflared (PID $($p.Id)) encerrado."
        } catch {}
    }

    Write-OK "Limpeza concluida."
}

# ---------------------------------------------------------------------------
# Exibir resumo do ambiente
# ---------------------------------------------------------------------------
function Show-Summary {
    param([string]$TunnelUrl, [string[]]$LocalIPs)

    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "   AMBIENTE DE DESENVOLVIMENTO ATIVO" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "  [Flask]" -ForegroundColor White
    Write-Host "    Local:   http://localhost:5000" -ForegroundColor Green
    foreach ($ip in $LocalIPs) {
        Write-Host "    Rede:    http://${ip}:5000" -ForegroundColor Green
    }
    Write-Host ""

    if ($TunnelUrl) {
        Write-Host "  [Cloudflare Tunnel]" -ForegroundColor White
        Write-Host "    Publico: $TunnelUrl" -ForegroundColor Cyan
    }

    Write-Host ""
    Write-Host "  [Bot Telegram] em execucao" -ForegroundColor White
    Write-Host ""
    Write-Host "  Pressione Ctrl+C para encerrar todo o ambiente." -ForegroundColor DarkGray
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host ""
}

# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
$allJobs = @()

try {
    Write-Header

    # Criar atalho na area de trabalho na primeira execucao
    $desktop = [System.Environment]::GetFolderPath('Desktop')
    $lnkPath = Join-Path $desktop 'CREDORES - Dev.lnk'
    if (-not (Test-Path $lnkPath)) {
        try {
            $wsh = New-Object -ComObject WScript.Shell
            $lnk = $wsh.CreateShortcut($lnkPath)
            $lnk.TargetPath       = 'powershell.exe'
            $lnk.Arguments        = "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
            $lnk.WorkingDirectory = $PSScriptRoot
            $lnk.Description      = 'CREDORES - Ambiente de Desenvolvimento'
            $lnk.IconLocation     = 'powershell.exe,0'
            $lnk.Save()
            Write-OK "Atalho 'CREDORES - Dev.lnk' criado na area de trabalho."
        } catch {}
    }

    # ---- Verificacoes iniciais ----
    Write-Separator
    Write-Info "Verificando pre-requisitos..."
    Write-Host ""

    # Python
    $pythonCmd = Get-PythonCommand
    if (-not $pythonCmd) {
        Write-Fail "Python >= 3.8 nao encontrado."
        Read-Host "Pressione Enter para sair"
        exit 1
    }
    $pyVer = & $pythonCmd --version 2>&1
    Write-OK "Python: $pyVer"

    # App Flask
    $appFile = Get-AppFile
    if (-not $appFile) {
        Write-Fail "Arquivo Flask nao encontrado (app.py, main.py, server.py, run.py)."
        Read-Host "Pressione Enter para sair"
        exit 1
    }
    Write-OK "Aplicacao Flask: $appFile"

    # Cloudflared
    $cfPath = $null
    $localCf = Join-Path $PSScriptRoot "cloudflared.exe"
    if (Test-Path $localCf) {
        $cfPath = $localCf
    } else {
        $inPath = Get-Command "cloudflared" -ErrorAction SilentlyContinue
        if ($inPath) { $cfPath = $inPath.Source }
    }

    if ($cfPath) {
        Write-OK "cloudflared: $cfPath"
    } else {
        Write-Host "[AVISO] cloudflared.exe nao encontrado - tunnel nao sera iniciado." -ForegroundColor DarkYellow
    }

    # .env e Telegram
    $envPath = Join-Path $PSScriptRoot ".env"
    $envVars = Read-EnvFile -EnvPath $envPath
    $telegramToken  = $envVars["TELEGRAM_TOKEN"]
    $telegramChatId = $envVars["TELEGRAM_CHAT_ID"]
    $botFile        = Get-BotFile

    if ($telegramToken -and $telegramChatId -and $botFile) {
        Write-OK "Telegram configurado. Bot: $botFile"
    } else {
        Write-Host "[AVISO] Configuracao Telegram incompleta - bot nao sera iniciado." -ForegroundColor DarkYellow
        if (-not $botFile)        { Write-Host "  - Arquivo do bot nao encontrado." -ForegroundColor DarkGray }
        if (-not $telegramToken)  { Write-Host "  - TELEGRAM_TOKEN ausente no .env." -ForegroundColor DarkGray }
        if (-not $telegramChatId) { Write-Host "  - TELEGRAM_CHAT_ID ausente no .env." -ForegroundColor DarkGray }
    }

    Write-Host ""
    Write-Separator
    Write-Host ""

    # ---- Iniciar Flask ----
    $flaskJob = Start-FlaskJob -PythonCmd $pythonCmd -AppFile $appFile -WorkDir $PSScriptRoot
    $allJobs += $flaskJob

    # Aguardar Flask subir
    if (-not (Wait-ForFlask)) {
        Write-Fail "Flask nao iniciou corretamente. Verifique erros acima."
        $output = Receive-Job -Job $flaskJob 2>&1
        Write-Host $output -ForegroundColor DarkRed
        Invoke-Cleanup -Jobs $allJobs
        Read-Host "Pressione Enter para sair"
        exit 1
    }

    # IPs locais
    $localIPs = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object {
            $_.IPAddress -notmatch '^127\.' -and
            $_.IPAddress -notmatch '^169\.254\.' -and
            $_.PrefixOrigin -ne 'WellKnown'
        } |
        Select-Object -ExpandProperty IPAddress

    Write-Host ""

    # ---- Iniciar Cloudflare Tunnel ----
    $tunnelUrl = $null
    $cfJob     = $null

    if ($cfPath) {
        $cfResult = Start-CloudflareJob -CloudflaredPath $cfPath -WorkDir $PSScriptRoot
        if ($cfResult) {
            $tunnelUrl = $cfResult.Url
            $cfJob     = $cfResult.Job
            $allJobs  += $cfJob

            # Copiar URL para clipboard
            try {
                Set-Clipboard -Value $tunnelUrl
                Write-Info "URL publica copiada para a area de transferencia."
            } catch {}
        }
    }

    Write-Host ""

    # ---- Resumo ----
    Show-Summary -TunnelUrl $tunnelUrl -LocalIPs $localIPs

    # ---- Iniciar Bot (foreground) ----
    if ($botFile -and $telegramToken -and $telegramChatId) {
        Write-Separator
        Start-BotForeground -PythonCmd $pythonCmd -BotFile $botFile
    } else {
        Write-Info "Bot Telegram nao configurado. Servidor ativo. Pressione Ctrl+C para encerrar."
        # Aguardar indefinidamente ate Ctrl+C
        while ($true) {
            Start-Sleep -Seconds 5

            # Verificar se Flask ainda esta rodando
            if ($flaskJob.State -ne "Running") {
                Write-Host ""
                Write-Fail "Servidor Flask encerrou inesperadamente."
                $output = Receive-Job -Job $flaskJob 2>&1
                if ($output) { Write-Host $output -ForegroundColor DarkRed }
                break
            }
        }
    }

} catch [System.Management.Automation.PipelineStoppedException] {
    # Ctrl+C capturado
    Write-Host ""
    Write-Info "Interrupcao recebida (Ctrl+C)."
} catch {
    Write-Fail "Erro inesperado: $_"
} finally {
    Invoke-Cleanup -Jobs $allJobs
    Write-Host ""
    Write-Host "Ambiente de desenvolvimento encerrado." -ForegroundColor DarkGray
    Read-Host "Pressione Enter para sair"
}
