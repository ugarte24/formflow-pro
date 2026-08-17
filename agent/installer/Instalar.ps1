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

  Write-Host "Cerrando Digitalizador Agent si esta abierto..." -ForegroundColor Yellow
  Get-Process -Name "DigitalizadorAgent" -ErrorAction SilentlyContinue | ForEach-Object {
    try { Stop-Process -Id $_.Id -Force -ErrorAction Stop } catch {}
  }
  # Firefox del agente (Playwright) tambien puede bloquear DLLs
  Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object {
      $_.Name -match 'firefox|Digitalizador' -and
      ($_.CommandLine -match 'DigitalizadorAgent|ms-playwright|playwright' -or $_.ExecutablePath -match 'Digitalizador|ms-playwright')
    } |
    ForEach-Object {
      try { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue } catch {}
    }
  Start-Sleep -Seconds 2

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
  $maxTries = 5
  for ($try = 1; $try -le $maxTries; $try++) {
    try {
      Get-ChildItem $Origen -Force | Where-Object {
        $_.Name -notin @("Instalar.bat", "Instalar.ps1", "Desinstalar.bat", "Desinstalar.ps1")
      } | ForEach-Object {
        $target = Join-Path $Destino $_.Name
        if ($_.PSIsContainer) {
          if (Test-Path $target) {
            Remove-Item -Recurse -Force $target -ErrorAction Stop
          }
          Copy-Item -Recurse -Force $_.FullName -Destination $Destino -ErrorAction Stop
        } else {
          Copy-Item -Force $_.FullName -Destination $Destino -ErrorAction Stop
        }
      }
      break
    } catch {
      if ($try -eq $maxTries) { throw }
      Write-Host "Archivo en uso (intento $try/$maxTries). Cerrando procesos y reintentando..." -ForegroundColor Yellow
      Get-Process -Name "DigitalizadorAgent" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
      Start-Sleep -Seconds 2
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
      "RUAT_START_URL=http://municipios.ruat.net/ContribuyentesWeb/Administracion/menuPrincipal/MenuPrincipalController.jpf"
    ) | Set-Content -Encoding ASCII $envDest
    Write-Host "Se creo .env automaticamente (solo BASE_URL)." -ForegroundColor Green
  } else {
    $envTxt = Get-Content -Raw $envDest
    if ($envTxt -notmatch '(?m)^\s*RUAT_START_URL\s*=') {
      Add-Content -Encoding ASCII $envDest "`r`nRUAT_START_URL=http://municipios.ruat.net/ContribuyentesWeb/Administracion/menuPrincipal/MenuPrincipalController.jpf"
      Write-Host "Se agrego RUAT_START_URL (municipios.ruat.net) al .env." -ForegroundColor Green
    }
  }

  Write-Host "Al iniciar el agente, use el mismo email y contrasena de la web." -ForegroundColor Cyan

  $bat = Join-Path $Destino "Iniciar-Agente.bat"
  if (-not (Test-Path $bat)) {
    @(
      "@echo off"
      "cd /d `"%~dp0`""
      "start `"`" `"DigitalizadorAgent.exe`""
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
  Write-Host "1) Cierre Digitalizador Agent (clic derecho icono bandeja -> Salir)."
  Write-Host "2) Si sigue el error: Ctrl+Shift+Esc -> finalizar DigitalizadorAgent.exe"
  Write-Host "3) Extraiga el ZIP a una carpeta y ejecute Instalar.bat de nuevo."
  Write-Host "4) Pruebe clic derecho -> Ejecutar como administrador."
  Write-Host ""
  exit 1
}
