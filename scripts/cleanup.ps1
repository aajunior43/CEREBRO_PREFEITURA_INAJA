$fontsDir = 'j:\CEREBRO_PREFEITURA_INAJA-main\CEREBRO_PREFEITURA_INAJA-main\static\fonts'

# Deletar as 6 fontes TTF (manter apenas .woff2)
foreach ($f in Get-ChildItem $fontsDir -Filter '*.ttf') {
    $kb = [math]::Round($f.Length/1KB, 1)
    Remove-Item $f.FullName -Force
    Write-Host "DELETADO: $($f.Name) ($kb KB)"
}

# Deletar brasao_b64.js
$b64 = 'j:\CEREBRO_PREFEITURA_INAJA-main\CEREBRO_PREFEITURA_INAJA-main\static\js\brasao_b64.js'
if (Test-Path $b64) {
    $sz = [math]::Round((Get-Item $b64).Length/1KB, 1)
    Remove-Item $b64 -Force
    Write-Host "DELETADO: brasao_b64.js ($sz KB)"
}

# Deletar pref.zip (arquivo temporario)
$zip = 'j:\CEREBRO_PREFEITURA_INAJA-main\CEREBRO_PREFEITURA_INAJA-main\pref.zip'
if (Test-Path $zip) {
    $sz = [math]::Round((Get-Item $zip).Length/1KB, 1)
    Remove-Item $zip -Force
    Write-Host "DELETADO: pref.zip ($sz KB)"
}

Write-Host ""
Write-Host "Verificando o que sobrou em static/fonts:"
foreach ($f in Get-ChildItem $fontsDir) {
    $kb = [math]::Round($f.Length/1KB, 1)
    Write-Host "  $($f.Name) - $kb KB"
}
