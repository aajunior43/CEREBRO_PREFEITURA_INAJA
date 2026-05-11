# =============================================================================
# CREDORES_FIXOS_MENSAIR - Sistema de Controle de Empenhos Mensais
# Prefeitura Municipal de Inajá
# bot.ps1 - Iniciador do Bot Telegram
# =============================================================================

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Set-Location $PSScriptRoot

$host.UI.RawUI.WindowTitle = "CREDORES_FIXOS_MENSAIR - Bot Telegram"

function Write-Header {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "   CREDORES_FIXOS_MENSAIR - Sistema de Empenhos Mensais" -ForegroundColor Cyan
    Write-Host "   Prefeitura Municipal de Inajá" -ForegroundColor Cyan
    Write-Host "   Iniciando Bot Telegram..." -ForegroundColor Cyan
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

function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor DarkCyan
}

# ---------------------------------------------------------------------------
# 1. Encontrar Python
# ---------------------------------------------------------------------------
function Get-PythonCommand {
    foreach ($cmd in @("python", "python3")) {
        try {
            $ver = & $cmd --version 2>&1
            if ($ver -match "Python (\d+)\.(\d+)") {
                $major = [int]$Matches[1]
                $minor = [int]$Matches[2]
                if ($major -gt 3 -or ($major -eq 3 -and $minor -ge 8)) {
                    return $cmd
                }
            }
        } catch {}
    }
    return $null
}

# ---------------------------------------------------------------------------
# 2. Parsear arquivo .env com suporte a comentarios e espacos
# ---------------------------------------------------------------------------
function Read-EnvFile {
    param([string]$EnvPath)

    $envVars = @{}

    if (-not (Test-Path $EnvPath)) {
        return $envVars
    }

    $lines = Get-Content $EnvPath -Encoding UTF8
    foreach ($line in $lines) {
        # Ignorar linhas vazias e comentarios
        $trimmed = $line.Trim()
        if ($trimmed -eq "" -or $trimmed.StartsWith("#")) { continue }

        # Dividir na primeira ocorrencia de '='
        $eqIndex = $trimmed.IndexOf('=')
        if ($eqIndex -le 0) { continue }

        $key   = $trimmed.Substring(0, $eqIndex).Trim()
        $value = $trimmed.Substring($eqIndex + 1).Trim()

        # Remover aspas envolventes (simples ou duplas)
        if (($value.StartsWith('"') -and $value.EndsWith('"')) -or
            ($value.StartsWith("'") -and $value.EndsWith("'"))) {
            $value = $value.Substring(1, $value.Length - 2)
        }

        # Remover comentarios inline (ex: TOKEN=abc123 # comentario)
        if ($value -match '^([^#]*?)\s*#') {
            $value = $Matches[1].Trim()
        }

        $envVars[$key] = $value
    }

    return $envVars
}

# ---------------------------------------------------------------------------
# 3. Validar variaveis de ambiente do Telegram
# ---------------------------------------------------------------------------
function Test-TelegramConfig {
    param([hashtable]$EnvVars)

    Write-Step "Validando configuracao do Telegram..."

    $envPath = Join-Path $PSScriptRoot ".env"
    if (-not (Test-Path $envPath)) {
        Write-Fail "Arquivo .env nao encontrado em: $envPath"
        Write-Host "  Crie um arquivo .env com as variaveis TELEGRAM_TOKEN e TELEGRAM_CHAT_ID." -ForegroundColor DarkYellow
        return $false
    }

    $token  = $EnvVars["TELEGRAM_TOKEN"]
    $chatId = $EnvVars["TELEGRAM_CHAT_ID"]

    $valid = $true

    if (-not $token -or $token.Trim() -eq "") {
        Write-Fail "TELEGRAM_TOKEN nao definido ou vazio no arquivo .env"
        $valid = $false
    } else {
        # Validacao basica de formato: XXXXXXXXX:YYYYYYY...
        if ($token -match '^\d+:[A-Za-z0-9_\-]{35,}$') {
            Write-OK "TELEGRAM_TOKEN: configurado (****$($token.Substring([Math]::Max(0, $token.Length - 6))))"
        } else {
            Write-Host "[AVISO] TELEGRAM_TOKEN parece ter formato invalido." -ForegroundColor DarkYellow
            Write-OK "TELEGRAM_TOKEN: presente (nao validado por formato)"
        }
    }

    if (-not $chatId -or $chatId.Trim() -eq "") {
        Write-Fail "TELEGRAM_CHAT_ID nao definido ou vazio no arquivo .env"
        $valid = $false
    } else {
        Write-OK "TELEGRAM_CHAT_ID: $chatId"
    }

    return $valid
}

# ---------------------------------------------------------------------------
# 4. Verificar dependencias do bot
# ---------------------------------------------------------------------------
function Test-BotDependencies {
    param([string]$PythonCmd)

    Write-Step "Verificando dependencias do bot..."

    $deps = @{
        "requests"           = "requests"
        "python-telegram-bot" = "telegram"
    }

    $missing = @()
    foreach ($pkg in $deps.Keys) {
        $importName = $deps[$pkg]
        $check = & $PythonCmd -c "import $importName" 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Host "    [ ] $pkg - NAO instalado" -ForegroundColor DarkYellow
            $missing += $pkg
        } else {
            Write-Host "    [v] $pkg" -ForegroundColor DarkGreen
        }
    }

    if ($missing.Count -eq 0) {
        Write-OK "Todas as dependencias do bot estao instaladas."
        return $true
    }

    Write-Step "Instalando dependencias ausentes: $($missing -join ', ')..."
    try {
        & $PythonCmd -m pip install @($missing) --quiet
        if ($LASTEXITCODE -ne 0) {
            Write-Fail "Falha ao instalar dependencias."
            return $false
        }
        Write-OK "Dependencias instaladas."
    } catch {
        Write-Fail "Erro ao executar pip: $_"
        return $false
    }

    return $true
}

# ---------------------------------------------------------------------------
# 5. Encontrar arquivo do bot
# ---------------------------------------------------------------------------
function Get-BotFile {
    $candidates = @("bot.py", "telegram_bot.py", "main_bot.py", "telegram-bot.py")
    foreach ($name in $candidates) {
        $path = Join-Path $PSScriptRoot $name
        if (Test-Path $path) {
            return $path
        }
    }
    return $null
}

# ---------------------------------------------------------------------------
# 6. Executar bot com auto-restart e backoff
# ---------------------------------------------------------------------------
function Start-BotWithRestart {
    param(
        [string]$PythonCmd,
        [string]$BotFile
    )

    # Backoff: 5s, 10s, 30s (depois mantém 30s)
    $backoffSequence = @(5, 10, 30)
    $restartCount = 0

    Write-Host ""
    Write-Host "------------------------------------------------------------" -ForegroundColor DarkCyan
    Write-Host "  Bot iniciado. Pressione Ctrl+C para encerrar." -ForegroundColor White
    Write-Host "------------------------------------------------------------" -ForegroundColor DarkCyan
    Write-Host ""

    while ($true) {
        if ($restartCount -gt 0) {
            $backoffIndex = [Math]::Min($restartCount - 1, $backoffSequence.Count - 1)
            $waitSeconds  = $backoffSequence[$backoffIndex]
            Write-Host ""
            Write-Host "[RESTART #$restartCount] Bot reiniciando em $waitSeconds segundo(s)... (Ctrl+C para cancelar)" -ForegroundColor DarkYellow
            Start-Sleep -Seconds $waitSeconds
            Write-Host ""
        }

        Write-Step "Iniciando bot (execucao $($restartCount + 1))..."

        try {
            $proc = Start-Process `
                -FilePath $PythonCmd `
                -ArgumentList "`"$BotFile`"" `
                -WorkingDirectory $PSScriptRoot `
                -PassThru `
                -NoNewWindow

            Write-OK "Bot em execucao (PID $($proc.Id))."
            Write-Info "Status: ONLINE"

            $proc.WaitForExit()
            $exitCode = $proc.ExitCode

            Write-Host ""
            if ($exitCode -eq 0) {
                Write-Host "[INFO] Bot encerrado normalmente (codigo 0)." -ForegroundColor DarkGray
                break
            } else {
                $restartCount++
                Write-Fail "Bot encerrou com codigo de saida: $exitCode (reinicio #$restartCount)"
            }
        } catch [System.OperationCanceledException] {
            Write-Host ""
            Write-Host "[INFO] Bot encerrado pelo usuario." -ForegroundColor DarkGray
            break
        } catch {
            $restartCount++
            Write-Fail "Erro ao executar o bot: $_ (reinicio #$restartCount)"
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
    $lnkPath = Join-Path $desktop 'CREDORES - Bot Telegram.lnk'
    if (-not (Test-Path $lnkPath)) {
        try {
            $wsh = New-Object -ComObject WScript.Shell
            $lnk = $wsh.CreateShortcut($lnkPath)
            $lnk.TargetPath       = 'powershell.exe'
            $lnk.Arguments        = "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
            $lnk.WorkingDirectory = $PSScriptRoot
            $lnk.Description      = 'CREDORES - Bot Telegram'
            $lnk.IconLocation     = 'powershell.exe,0'
            $lnk.Save()
            Write-OK "Atalho 'CREDORES - Bot Telegram.lnk' criado na area de trabalho."
        } catch {}
    }

    # Python
    Write-Step "Verificando Python..."
    $pythonCmd = Get-PythonCommand
    if (-not $pythonCmd) {
        Write-Fail "Python >= 3.8 nao encontrado. Instale em https://www.python.org/downloads/"
        Read-Host "Pressione Enter para sair"
        exit 1
    }
    $pyVer = & $pythonCmd --version 2>&1
    Write-OK "Python: $pyVer"

    # .env
    $envPath = Join-Path $PSScriptRoot ".env"
    $envVars = Read-EnvFile -EnvPath $envPath

    if (-not (Test-TelegramConfig -EnvVars $envVars)) {
        Read-Host "Pressione Enter para sair"
        exit 1
    }

    # Dependencias
    if (-not (Test-BotDependencies -PythonCmd $pythonCmd)) {
        Read-Host "Pressione Enter para sair"
        exit 1
    }

    # Arquivo do bot
    Write-Step "Procurando arquivo do bot..."
    $botFile = Get-BotFile
    if (-not $botFile) {
        Write-Fail "Arquivo do bot nao encontrado (bot.py, telegram_bot.py, main_bot.py, telegram-bot.py)."
        Read-Host "Pressione Enter para sair"
        exit 1
    }
    Write-OK "Arquivo do bot: $botFile"

    # Iniciar com restart automatico
    Start-BotWithRestart -PythonCmd $pythonCmd -BotFile $botFile

} catch {
    Write-Fail "Erro inesperado: $_"
} finally {
    Write-Host ""
    Write-Host "Bot encerrado." -ForegroundColor DarkGray
    Read-Host "Pressione Enter para sair"
}
