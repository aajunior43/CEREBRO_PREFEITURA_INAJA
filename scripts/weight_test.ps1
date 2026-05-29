$base = 'j:\CEREBRO_PREFEITURA_INAJA-main\CEREBRO_PREFEITURA_INAJA-main'
function fmtSize($b) { if($b -ge 1MB){"{0:N2} MB" -f ($b/1MB)} elseif($b -ge 1KB){"{0:N1} KB" -f ($b/1KB)} else{"$b B"} }

"=== ANALISE DE PESO DO SITE ==="
""
"--- HTMLs raiz ---"
foreach($n in @('index.html','login.html')){
  $f = Get-Item (Join-Path $base $n)
  "$($f.Name.PadRight(35)) $(fmtSize $f.Length)"
}
""
"--- HTMLs pages/ (maiores primeiro) ---"
Get-ChildItem (Join-Path $base 'pages') -Filter '*.html' | Sort-Object Length -Descending | ForEach-Object {
  "$($_.Name.PadRight(50)) $(fmtSize $_.Length)"
}
""
"--- CSS static/css/ ---"
Get-ChildItem (Join-Path $base 'static\css') | Sort-Object Length -Descending | ForEach-Object {
  "$($_.Name.PadRight(50)) $(fmtSize $_.Length)"
}
""
"--- JS static/js/ ---"
Get-ChildItem (Join-Path $base 'static\js') -Filter '*.js' | Sort-Object Length -Descending | ForEach-Object {
  "$($_.Name.PadRight(50)) $(fmtSize $_.Length)"
}
""
"--- JS static/js/despesa/ ---"
Get-ChildItem (Join-Path $base 'static\js\despesa') -Filter '*.js' | Sort-Object Length -Descending | ForEach-Object {
  "$($_.Name.PadRight(50)) $(fmtSize $_.Length)"
}
""
"--- Fontes static/fonts/ ---"
Get-ChildItem (Join-Path $base 'static\fonts') | Sort-Object Length -Descending | ForEach-Object {
  "$($_.Name.PadRight(50)) $(fmtSize $_.Length)"
}
""
"--- Imagens static/img/ ---"
Get-ChildItem (Join-Path $base 'static\img') | Sort-Object Length -Descending | ForEach-Object {
  "$($_.Name.PadRight(50)) $(fmtSize $_.Length)"
}
""
"--- TOTAIS ---"
$htmlRoot  = @('index.html','login.html') | ForEach-Object { (Get-Item (Join-Path $base $_)).Length } | Measure-Object -Sum | Select-Object -ExpandProperty Sum
$htmlPages = (Get-ChildItem (Join-Path $base 'pages') -Filter '*.html' | Measure-Object -Property Length -Sum).Sum
$cssTotal  = (Get-ChildItem (Join-Path $base 'static\css') | Measure-Object -Property Length -Sum).Sum
$jsTotal   = (Get-ChildItem (Join-Path $base 'static\js') -Recurse -Filter '*.js' | Measure-Object -Property Length -Sum).Sum
$fontsTotal= (Get-ChildItem (Join-Path $base 'static\fonts') | Measure-Object -Property Length -Sum).Sum
$imgTotal  = (Get-ChildItem (Join-Path $base 'static\img') | Measure-Object -Property Length -Sum).Sum
$total     = $htmlRoot + $htmlPages + $cssTotal + $jsTotal + $fontsTotal + $imgTotal
"HTML raiz:   $(fmtSize $htmlRoot)"
"HTML pages:  $(fmtSize $htmlPages)"
"CSS:         $(fmtSize $cssTotal)"
"JavaScript:  $(fmtSize $jsTotal)"
"Fontes:      $(fmtSize $fontsTotal)"
"Imagens:     $(fmtSize $imgTotal)"
"TOTAL GERAL: $(fmtSize $total)"
