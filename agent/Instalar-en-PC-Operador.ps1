# Copia el build al PC del operador y crea acceso directo en el Escritorio.
# Ejecutar DESPUÉS de build_exe.ps1, en el PC destino (o desde USB).
# Uso:
#   .\Instalar-en-PC-Operador.ps1
#   .\Instalar-en-PC-Operador.ps1 -Destino "C:\Digitalizador\DigitalizadorAgent"

param(
  [string]$Destino = "$env:LOCALAPPDATA\Digitalizador\DigitalizadorAgent",
  [string]$Origen = ""
)

$ErrorActionPreference = "Stop"

if (-not $Origen) {
  $Origen = Join-Path $PSScriptRoot "dist\DigitalizadorAgent"
}

if (-not (Test-Path (Join-Path $Origen "DigitalizadorAgent.exe"))) {
  throw "No se encuentra DigitalizadorAgent.exe en $Origen. Primero ejecute build_exe.ps1"
}

Write-Host "Instalando en $Destino …" -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path $Destino | Out-Null

# Conservar .env si ya existía
$envExistente = Join-Path $Destino ".env"
$envBackup = $null
if (Test-Path $envExistente) {
  $envBackup = Join-Path $env:TEMP "digitalizador-agent.env.bak"
  Copy-Item -Force $envExistente $envBackup
  Write-Host "Se conservará el .env actual"
}

Copy-Item -Recurse -Force (Join-Path $Origen "*") $Destino

if ($envBackup -and (Test-Path $envBackup)) {
  Copy-Item -Force $envBackup $envExistente
  Remove-Item $envBackup -ErrorAction SilentlyContinue
}

$envDest = Join-Path $Destino ".env"
if (-not (Test-Path $envDest)) {
  Copy-Item (Join-Path $Destino ".env.example") $envDest
  Write-Host "Se creó .env desde .env.example — COMPLETE BASE_URL y CODIGO_PC (sin token)" -ForegroundColor Yellow
  notepad $envDest
}

# Acceso directo en Escritorio
$desktop = [Environment]::GetFolderPath("Desktop")
$lnkPath = Join-Path $desktop "Digitalizador Agent.lnk"
$wsh = New-Object -ComObject WScript.Shell
$lnk = $wsh.CreateShortcut($lnkPath)
$lnk.TargetPath = Join-Path $Destino "Iniciar-Agente.bat"
$lnk.WorkingDirectory = $Destino
$lnk.Description = "Agente Digitalizador — RUAT"
$lnk.Save()

Write-Host ""
Write-Host "Instalación lista." -ForegroundColor Green
Write-Host "Carpeta: $Destino"
Write-Host "Acceso directo: $lnkPath"
Write-Host "1) Edite .env (BASE_URL + CODIGO_PC)"
Write-Host "2) Doble clic en 'Digitalizador Agent' del Escritorio"
Write-Host "3) Primer arranque: descarga Firefox (esperar). Luego inicie sesión RUAT una vez."
