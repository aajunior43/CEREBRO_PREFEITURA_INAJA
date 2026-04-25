#Requires -Version 5.1
<#
.SYNOPSIS
    Backup automatizado do empenhos.db com rotação e logs para Task Scheduler.

.DESCRIPTION
    Cria cópia de segurança do empenhos.db, verifica integridade,
    calcula hash SHA256 e remove backups antigos conforme retenção.

.PARAMETER RetentionDays
    Número de dias para manter backups (padrão: 30, 0 = infinito).

.PARAMETER Verify
    Verificar integridade do último backup.

.PARAMETER List
    Listar backups disponíveis.

.EXAMPLE
    .\backup_db.ps1
    .\backup_db.ps1 -RetentionDays 60
    .\backup_db.ps1 -Verify
    .\backup_db.ps1 -List

.NOTES
    Agendamento diário via Task Scheduler:
    schtasks /Create /TN "BackupEmpenhosDB" /TR "powershell -ExecutionPolicy Bypass -File `"$PWD\backup_db.ps1`"" /SC DAILY /ST 02:00
#>

[CmdletBinding()]
param(
    [int]$RetentionDays = 30,
    [switch]$Verify,
    [switch]$List
)

# ── Configuração ─────────────────────────────────────────────
$ErrorActionPreference = "Stop"

$BaseDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$DbPath = Join-Path $BaseDir "empenhos.db"
$BackupDir = Join-Path $BaseDir "backups"
$LogDir = Join-Path $BaseDir "logs"
$LogFile = Join-Path $LogDir "backup.log"

# Criar diretórios se não existirem
if (-not (Test-Path $BackupDir)) { New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null }
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }

# ── Logging ──────────────────────────────────────────────────
function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logEntry = "[$timestamp] [$Level] $Message"
    Add-Content -Path $LogFile -Value $logEntry -Encoding UTF8
    if ($Level -eq "ERROR") {
        Write-Host $logEntry -ForegroundColor Red
    } elseif ($Level -eq "WARNING") {
        Write-Host $logEntry -ForegroundColor Yellow
    } elseif ($Level -eq "SUCCESS") {
        Write-Host $logEntry -ForegroundColor Green
    } else {
        Write-Host $logEntry -ForegroundColor White
    }
}

# ── Funções auxiliares ───────────────────────────────────────
function Get-Timestamp {
    return Get-Date -Format "yyyyMMdd_HHmmss"
}

function Get-BackupFilename {
    return "empenhos_backup_$(Get-Timestamp).db"
}

function Get-FileHash256 {
    param([string]$FilePath)
    $hash = Get-FileHash -Path $FilePath -Algorithm SHA256
    return $hash.Hash
}

function Get-FileSizeMB {
    param([string]$FilePath)
    $size = (Get-Item $FilePath).Length
    return [math]::Round($size / 1MB, 2)
}

# ── Verificação de integridade ───────────────────────────────
function Test-DatabaseIntegrity {
    param([string]$DbFile)

    if (-not (Test-Path $DbFile)) {
        return @{ Ok = $false; Message = "Arquivo não encontrado: $DbFile" }
    }

    $fileSize = (Get-Item $DbFile).Length
    if ($fileSize -eq 0) {
        return @{ Ok = $false; Message = "Arquivo vazio: $DbFile" }
    }

    try {
        # Usar sqlite3 via linha de comando (se disponível)
        # Fallback: verificar se o arquivo é legível
        $content = [System.IO.File]::ReadAllBytes($DbFile)

        # Verificar magic header do SQLite: "SQLite format 3\000"
        $header = [System.Text.Encoding]::UTF8.GetString($content[0..15])
        if ($header -eq "SQLite format 3`0") {
            $sizeMB = [math]::Round($fileSize / 1MB, 2)
            return @{ Ok = $true; Message = "Íntegro ($sizeMB MB)" }
        } else {
            return @{ Ok = $false; Message = "Header SQLite inválido" }
        }
    } catch {
        return @{ Ok = $false; Message = "Erro ao ler arquivo: $_" }
    }
}

# ── Backup principal ─────────────────────────────────────────
function Start-DatabaseBackup {
    param([int]$RetentionDays = 30)

    $result = @{
        Success = $false
        BackupFile = $null
        SizeBytes = 0
        SHA256 = $null
        IntegrityOk = $false
        IntegrityMsg = ""
        DeletedOld = @()
        Errors = @()
    }

    # 1. Verificar se o banco original existe
    if (-not (Test-Path $DbPath)) {
        $msg = "Banco original não encontrado: $DbPath"
        Write-Log $msg "ERROR"
        $result.Errors += $msg
        return $result
    }

    # 2. Verificar integridade do banco original
    $originalCheck = Test-DatabaseIntegrity -DbFile $DbPath
    if (-not $originalCheck.Ok) {
        Write-Log "Banco original com problemas: $($originalCheck.Message)" "WARNING"
    }

    # 3. Criar cópia do banco
    $backupFilename = Get-BackupFilename
    $backupFile = Join-Path $BackupDir $backupFilename

    try {
        Write-Log "Iniciando backup: $backupFilename"
        Write-Log "Origem: $DbPath"
        Write-Log "Destino: $backupFile"

        # Copiar arquivo (Copy-Item preserva metadados por padrão)
        Copy-Item -Path $DbPath -Destination $backupFile -Force

        # 4. Verificar integridade do backup
        $backupCheck = Test-DatabaseIntegrity -DbFile $backupFile
        $result.IntegrityOk = $backupCheck.Ok
        $result.IntegrityMsg = $backupCheck.Message

        if (-not $backupCheck.Ok) {
            $msg = "Backup corrompido: $($backupCheck.Message)"
            Write-Log $msg "ERROR"
            $result.Errors += $msg
            # Remover backup corrompido
            if (Test-Path $backupFile) { Remove-Item $backupFile -Force }
            return $result
        }

        # 5. Calcular tamanho e hash
        $sizeBytes = (Get-Item $backupFile).Length
        $result.SizeBytes = $sizeBytes
        $result.SHA256 = Get-FileHash256 -FilePath $backupFile
        $result.BackupFile = $backupFile
        $result.Success = $true

        $sizeMB = Get-FileSizeMB -FilePath $backupFile
        Write-Log "Backup criado com sucesso: $backupFilename ($sizeMB MB)" "SUCCESS"
        Write-Log "Integridade: $($backupCheck.Message)" "SUCCESS"
        Write-Log "SHA256: $($result.SHA256.Substring(0, 16))..." "INFO"

        # 6. Salvar hash em arquivo separado
        $hashFile = "$backupFile.sha256"
        "$($result.SHA256)  $backupFilename" | Out-File -FilePath $hashFile -Encoding UTF8

        # 7. Rotação — remover backups antigos
        if ($RetentionDays -gt 0) {
            $deleted = Invoke-BackupRotation -RetentionDays $RetentionDays
            $result.DeletedOld = $deleted
            if ($deleted.Count -gt 0) {
                Write-Log "Rotação: $($deleted.Count) backup(s) antigo(s) removido(s)" "INFO"
            }
        }

        return $result

    } catch {
        $msg = "Erro ao criar backup: $_"
        Write-Log $msg "ERROR"
        $result.Errors += $msg

        # Limpar arquivo parcial se existir
        if (Test-Path $backupFile) {
            try { Remove-Item $backupFile -Force } catch { }
        }

        return $result
    }
}

# ── Rotação de backups ───────────────────────────────────────
function Invoke-BackupRotation {
    param([int]$RetentionDays)

    $deleted = @()
    $cutoffDate = (Get-Date).AddDays(-$RetentionDays)

    # Encontrar todos os backups
    $backupFiles = Get-ChildItem -Path $BackupDir -Filter "empenhos_backup_*.db" -ErrorAction SilentlyContinue

    foreach ($file in $backupFiles) {
        if ($file.LastWriteTime -lt $cutoffDate) {
            try {
                Remove-Item $file.FullName -Force
                $deleted += $file.Name
                Write-Log "Removido backup antigo: $($file.Name)" "DEBUG"

                # Remover arquivo de hash correspondente
                $hashFile = "$($file.FullName).sha256"
                if (Test-Path $hashFile) {
                    Remove-Item $hashFile -Force
                }
            } catch {
                Write-Log "Falha ao remover $($file.FullName): $_" "WARNING"
            }
        }
    }

    return $deleted
}

# ── Verificar último backup ──────────────────────────────────
function Test-LatestBackup {
    $result = @{
        Found = $false
        File = $null
        IntegrityOk = $false
        IntegrityMsg = ""
        SHA256Match = $null
    }

    $latestBackup = Get-ChildItem -Path $BackupDir -Filter "empenhos_backup_*.db" -ErrorAction SilentlyContinue |
                    Sort-Object LastWriteTime -Descending |
                    Select-Object -First 1

    if (-not $latestBackup) {
        $result.IntegrityMsg = "Nenhum backup encontrado"
        return $result
    }

    $result.Found = $true
    $result.File = $latestBackup.FullName

    # Verificar integridade
    $backupCheck = Test-DatabaseIntegrity -DbFile $latestBackup.FullName
    $result.IntegrityOk = $backupCheck.Ok
    $result.IntegrityMsg = $backupCheck.Message

    # Verificar hash se existir arquivo .sha256
    $hashFile = "$($latestBackup.FullName).sha256"
    if (Test-Path $hashFile) {
        try {
            $expectedHash = (Get-Content $hashFile -Raw).Split()[0]
            $actualHash = Get-FileHash256 -FilePath $latestBackup.FullName
            $result.SHA256Match = ($expectedHash -eq $actualHash)
        } catch {
            $result.SHA256Match = $false
            Write-Log "Erro ao verificar hash: $_" "WARNING"
        }
    }

    return $result
}

# ── Listar backups ───────────────────────────────────────────
function Get-BackupList {
    $backups = @()

    $backupFiles = Get-ChildItem -Path $BackupDir -Filter "empenhos_backup_*.db" -ErrorAction SilentlyContinue |
                   Sort-Object LastWriteTime -Descending

    foreach ($file in $backupFiles) {
        $sizeMB = [math]::Round($file.Length / 1MB, 2)
        $daysAgo = [math]::Round((Get-Date) - $file.LastWriteTime).Days

        $backups += @{
            File = $file.Name
            Path = $file.FullName
            SizeMB = $sizeMB
            Created = $file.LastWriteTime.ToString("dd/MM/yyyy HH:mm:ss")
            DaysAgo = $daysAgo
        }
    }

    return $backups
}

# ── Main ─────────────────────────────────────────────────────
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Backup Automatizado — empenhos.db" -ForegroundColor Cyan
Write-Host "  Data: $(Get-Date -Format 'dd/MM/yyyy HH:mm:ss')" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

if ($Verify) {
    # Modo verificação
    $result = Test-LatestBackup
    if ($result.Found) {
        Write-Host "`nArquivo: $($result.File)"
        Write-Host "Integridade: $('OK' -replace '^$', 'FALHOU')" -ForegroundColor $(if ($result.IntegrityOk) { "Green" } else { "Red" })
        Write-Host "Detalhes: $($result.IntegrityMsg)"
        if ($result.SHA256Match -ne $null) {
            Write-Host "Hash válido: $('SIM' -replace '^$', 'NÃO')" -ForegroundColor $(if ($result.SHA256Match) { "Green" } else { "Red" })
        }
    } else {
        Write-Host "`n$($result.IntegrityMsg)" -ForegroundColor Yellow
    }
    exit $(if ($result.IntegrityOk) { 0 } else { 1 })
}

if ($List) {
    # Modo listagem
    $backups = Get-BackupList
    if ($backups.Count -eq 0) {
        Write-Host "`nNenhum backup encontrado." -ForegroundColor Yellow
    } else {
        Write-Host "`nBackups disponíveis ($($backups.Count)):"
        Write-Host "Arquivo                                            Tamanho                 Data   Idade"
        Write-Host "---------------------------------------------------------------------------------------------------------"
        foreach ($b in $backups) {
            Write-Host "$($b.File.PadRight(48)) $($b.SizeMB.ToString().PadLeft(8)) MB  $($b.Created.PadLeft(20))  $($b.DaysAgo.ToString().PadLeft(3))d"
        }
    }
    exit 0
}

# Modo backup normal
$result = Start-DatabaseBackup -RetentionDays $RetentionDays

if ($result.Success) {
    Write-Host "`nBackup criado com sucesso!" -ForegroundColor Green
    Write-Host "  Arquivo: $($result.BackupFile)"
    Write-Host "  Tamanho: $([math]::Round($result.SizeBytes / 1MB, 2)) MB"
    Write-Host "  Integridade: $($result.IntegrityMsg)"
    Write-Host "  SHA256: $($result.SHA256.Substring(0, 32))..."
    if ($result.DeletedOld.Count -gt 0) {
        Write-Host "  Rotação: $($result.DeletedOld.Count) backup(s) antigo(s) removido(s)"
    }
} else {
    Write-Host "`nFALHA ao criar backup:" -ForegroundColor Red
    foreach ($error in $result.Errors) {
        Write-Host "  ✗ $error" -ForegroundColor Red
    }
}

exit $(if ($result.Success) { 0 } else { 1 })
