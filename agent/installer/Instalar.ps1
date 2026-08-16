# Instala Digitalizador Agent en el PC del operador.
# Uso: doble clic en Instalar.bat

param(
  [string]$Destino = "$env:LOCALAPPDATA\Digitalizador\DigitalizadorAgent"
)

$ErrorActionPreference = "Stop"

try {
  $Origen = $PSScriptRoot
  if (-not $Origen) { $Origen = Split-Path -Parent $MyInvocation.MyCommand.Path }

  Write-Host ""
  Write-Host "========================================" -ForegroundColor Cyan
  Write-Host "  Instalador Digitalizador Agent"
  Write-Host "========================================"
  Write-Host "Origen : $Origen"
  Write-Host "Destino: $Destino"
  Write-Host ""

  $exe = Join-Path $Origen "DigitalizadorAgent.exe"
  if (-not (Test-Path $exe)) {
    throw "No se encuentra DigitalizadorAgent.exe. Extraiga el ZIP completo antes de instalar."
  }

  New-Item -ItemType Directory -Force -Path $Destino | Out-Null

  # Conservar .env existente
  $envDest = Join-Path $Destino ".env"
  $envBak = $null
  if (Test-Path $envDest) {
    $envBak = Join-Path $env:TEMP "digitalizador-agent.env.bak"
    Copy-Item -Force $envDest $envBak
    Write-Host "Se conservara tu configuracion (.env) actual."
  }

  Write-Host "Copiando archivos..."
  Get-ChildItem $Origen -Force | Where-Object {
    $_.Name -notin @("Instalar.bat", "Instalar.ps1", "Desinstalar.bat", "Desinstalar.ps1")
  } | ForEach-Object {
    $target = Join-Path $Destino $_.Name
    if ($_.PSIsContainer) {
      if (Test-Path $target) {
        Remove-Item -Recurse -Force $target -ErrorAction SilentlyContinue
      }
      Copy-Item -Recurse -Force $_.FullName -Destination $Destino
    } else {
      Copy-Item -Force $_.FullName -Destination $Destino
    }
  }

  if ($envBak -and (Test-Path $envBak)) {
    Copy-Item -Force $envBak $envDest
    Remove-Item $envBak -ErrorAction SilentlyContinue
  }

  if (-not (Test-Path $envDest)) {
    @(
      "BASE_URL=https://formflow-pro-sigma.vercel.app"
      "POLL_SECONDS=4"
      "FIREFOX_MODE=persistent"
    ) | Set-Content -Encoding ASCII $envDest
    Write-Host "Se creo .env automaticamente (solo BASE_URL)." -ForegroundColor Green
  }

  Write-Host "Al iniciar el agente, use el mismo email y contrasena de la web." -ForegroundColor Cyan

  $bat = Join-Path $Destino "Iniciar-Agente.bat"
  if (-not (Test-Path $bat)) {
    @(
      "@echo off"
      "cd /d `"%~dp0`""
      "DigitalizadorAgent.exe"
      "pause"
    ) | Set-Content -Encoding ASCII $bat
  }

  $desktop = [Environment]::GetFolderPath("Desktop")
  $wsh = New-Object -ComObject WScript.Shell
  $exeDest = Join-Path $Destino "DigitalizadorAgent.exe"
  $icoDest = Join-Path $Destino "DigitalizadorAgent.ico"
  $iconLoc = if (Test-Path $icoDest) { "$icoDest,0" } else { "$exeDest,0" }

  $lnkDesk = Join-Path $desktop "Digitalizador Agent.lnk"
  $s = $wsh.CreateShortcut($lnkDesk)
  $s.TargetPath = $exeDest
  $s.WorkingDirectory = $Destino
  $s.Description = "Agente Digitalizador - RUAT"
  $s.IconLocation = $iconLoc
  $s.Save()

  $startDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Digitalizador"
  New-Item -ItemType Directory -Force -Path $startDir | Out-Null
  $lnkStart = Join-Path $startDir "Digitalizador Agent.lnk"
  $s2 = $wsh.CreateShortcut($lnkStart)
  $s2.TargetPath = $exeDest
  $s2.WorkingDirectory = $Destino
  $s2.Description = "Agente Digitalizador - RUAT"
  $s2.IconLocation = $iconLoc
  $s2.Save()

  Copy-Item -Force (Join-Path $Origen "Desinstalar.ps1") (Join-Path $Destino "Desinstalar.ps1") -ErrorAction SilentlyContinue
  Copy-Item -Force (Join-Path $Origen "Desinstalar.bat") (Join-Path $Destino "Desinstalar.bat") -ErrorAction SilentlyContinue

  Write-Host ""
  Write-Host "Instalacion completada." -ForegroundColor Green
  Write-Host "- Acceso directo Escritorio: Digitalizador Agent"
  Write-Host "- Menu Inicio -> Digitalizador"
  Write-Host "- Carpeta: $Destino"
  Write-Host ""
  Write-Host "Para usarlo: doble clic en 'Digitalizador Agent'."
  Write-Host "El primer arranque descarga Firefox (una sola vez)."
  Write-Host ""
  exit 0
}
catch {
  Write-Host ""
  Write-Host "ERROR en la instalacion:" -ForegroundColor Red
  Write-Host $_.Exception.Message -ForegroundColor Red
  Write-Host ""
  Write-Host "Consejos:"
  Write-Host "1) Extraiga el ZIP a una carpeta (Escritorio) y ejecute Instalar.bat desde ahi."
  Write-Host "2) Cierre Digitalizador Agent si estaba abierto."
  Write-Host "3) Pruebe clic derecho -> Ejecutar como administrador."
  Write-Host ""
  exit 1
}
