# Desinstala Digitalizador Agent del PC del operador.

$ErrorActionPreference = "Stop"
$Destino = "$env:LOCALAPPDATA\Digitalizador\DigitalizadorAgent"

Write-Host "Se desinstalará: $Destino" -ForegroundColor Yellow
$ok = Read-Host "Escribí SI para confirmar"
if ($ok -ne "SI") { Write-Host "Cancelado."; pause; exit 0 }

# Quitar accesos directos
$desktop = [Environment]::GetFolderPath("Desktop")
Remove-Item (Join-Path $desktop "Digitalizador Agent.lnk") -Force -ErrorAction SilentlyContinue
$startDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Digitalizador"
Remove-Item -Recurse -Force $startDir -ErrorAction SilentlyContinue

if (Test-Path $Destino) {
  Remove-Item -Recurse -Force $Destino
}

$parent = Split-Path $Destino -Parent
if ((Test-Path $parent) -and -not (Get-ChildItem $parent -Force -ErrorAction SilentlyContinue)) {
  Remove-Item -Force $parent -ErrorAction SilentlyContinue
}

Write-Host "Desinstalado." -ForegroundColor Green
pause
