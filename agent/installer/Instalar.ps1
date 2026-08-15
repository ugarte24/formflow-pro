# Instala Digitalizador Agent como programa normal en el PC del operador.
# Se ejecuta desde la carpeta del paquete de instalación (junto a DigitalizadorAgent.exe).
# Uso: doble clic en Instalar.bat

param(
  [string]$Destino = "$env:LOCALAPPDATA\Digitalizador\DigitalizadorAgent"
)

$ErrorActionPreference = "Stop"
$Origen = $PSScriptRoot

if (-not (Test-Path (Join-Path $Origen "DigitalizadorAgent.exe"))) {
  Write-Host "ERROR: No se encuentra DigitalizadorAgent.exe junto a este instalador." -ForegroundColor Red
  pause
  exit 1
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Instalador Digitalizador Agent"
Write-Host "========================================"
Write-Host "Destino: $Destino"
Write-Host ""

New-Item -ItemType Directory -Force -Path $Destino | Out-Null

# Conservar .env existente
$envDest = Join-Path $Destino ".env"
$envBak = $null
if (Test-Path $envDest) {
  $envBak = Join-Path $env:TEMP "digitalizador-agent.env.bak"
  Copy-Item -Force $envDest $envBak
  Write-Host "Se conservará tu configuración (.env) actual."
}

Write-Host "Copiando archivos…"
Get-ChildItem $Origen -Force | Where-Object {
  $_.Name -notin @("Instalar.bat", "Instalar.ps1", "Desinstalar.bat", "Desinstalar.ps1")
} | ForEach-Object {
  Copy-Item -Recurse -Force $_.FullName -Destination $Destino
}

if ($envBak -and (Test-Path $envBak)) {
  Copy-Item -Force $envBak $envDest
  Remove-Item $envBak -ErrorAction SilentlyContinue
}

if (-not (Test-Path $envDest)) {
  $example = Join-Path $Destino ".env.example"
  if (Test-Path $example) {
    Copy-Item $example $envDest
  } else {
    @"
BASE_URL=https://formflow-pro-sigma.vercel.app
CODIGO_PC=
FIREFOX_MODE=persistent
POLL_SECONDS=4
"@ | Set-Content -Encoding UTF8 $envDest
  }
  Write-Host ""
  Write-Host "IMPORTANTE: Completá BASE_URL y CODIGO_PC (ej. PC-VEN-01) en el Bloc de notas." -ForegroundColor Yellow
  Write-Host "Ya no se usa token. El admin activa/desactiva operadores desde la web." -ForegroundColor Yellow
  Start-Process notepad $envDest
  Write-Host "Cuando guardes y cierres el Bloc de notas, pulsá Enter aquí…"
  Read-Host | Out-Null
}

# Acceso directo Escritorio
$desktop = [Environment]::GetFolderPath("Desktop")
$bat = Join-Path $Destino "Iniciar-Agente.bat"
if (-not (Test-Path $bat)) {
  @"
@echo off
cd /d "%~dp0"
DigitalizadorAgent.exe
pause
"@ | Set-Content -Encoding ASCII $bat
}

$wsh = New-Object -ComObject WScript.Shell
$lnkDesk = Join-Path $desktop "Digitalizador Agent.lnk"
$s = $wsh.CreateShortcut($lnkDesk)
$s.TargetPath = $bat
$s.WorkingDirectory = $Destino
$s.Description = "Agente Digitalizador — RUAT"
$s.Save()

# Menú Inicio
$startDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Digitalizador"
New-Item -ItemType Directory -Force -Path $startDir | Out-Null
$lnkStart = Join-Path $startDir "Digitalizador Agent.lnk"
$s2 = $wsh.CreateShortcut($lnkStart)
$s2.TargetPath = $bat
$s2.WorkingDirectory = $Destino
$s2.Description = "Agente Digitalizador — RUAT"
$s2.Save()

# Desinstalador en la carpeta instalada
Copy-Item -Force (Join-Path $Origen "Desinstalar.ps1") (Join-Path $Destino "Desinstalar.ps1") -ErrorAction SilentlyContinue
Copy-Item -Force (Join-Path $Origen "Desinstalar.bat") (Join-Path $Destino "Desinstalar.bat") -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "Instalación completada." -ForegroundColor Green
Write-Host "- Acceso directo en el Escritorio: Digitalizador Agent"
Write-Host "- Menú Inicio → Digitalizador"
Write-Host "- Carpeta: $Destino"
Write-Host ""
Write-Host "Para usarlo: doble clic en 'Digitalizador Agent'."
Write-Host "El primer arranque descarga Firefox (una sola vez)."
Write-Host ""
pause
