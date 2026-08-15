# Empaqueta el agente como carpeta Windows (DigitalizadorAgent.exe).
# Requisitos: Python 3.11+ en PATH.
# Uso (desde esta carpeta agent):
#   .\build_exe.ps1

$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot

Write-Host "==> Instalando dependencias de build…" -ForegroundColor Cyan
$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
  Write-Host "Creando .venv…"
  python -m venv .venv
  $py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
}
& $py -m pip install -U pip
& $py -m pip install -r requirements.txt "pyinstaller>=6.0"
if ($LASTEXITCODE -ne 0) { throw "Falló la instalación de dependencias" }

$ErrorActionPreference = "Stop"

Write-Host "==> Limpiando builds anteriores…" -ForegroundColor Cyan
Remove-Item -Recurse -Force dist, build -ErrorAction SilentlyContinue

Write-Host "==> PyInstaller (carpeta dist\DigitalizadorAgent)…" -ForegroundColor Cyan
& $py -m PyInstaller --noconfirm DigitalizadorAgent.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller falló" }

$out = Join-Path $PSScriptRoot "dist\DigitalizadorAgent"
if (-not (Test-Path (Join-Path $out "DigitalizadorAgent.exe"))) {
  throw "No se generó DigitalizadorAgent.exe"
}

# Asegurar .env.example junto al exe (por si el datas no lo copió)
Copy-Item -Force ".env.example" (Join-Path $out ".env.example") -ErrorAction SilentlyContinue
Copy-Item -Force "selectors.json" (Join-Path $out "selectors.json") -ErrorAction SilentlyContinue

# Script de ayuda para el operador
@"
@echo off
cd /d "%~dp0"
if not exist ".env" (
  echo Falta el archivo .env
  echo Copie .env.example a .env y complete BASE_URL y CODIGO_PC
  pause
  exit /b 1
)
DigitalizadorAgent.exe
pause
"@ | Set-Content -Encoding ASCII (Join-Path $out "Iniciar-Agente.bat")

Write-Host ""
Write-Host "Listo: $out" -ForegroundColor Green
Write-Host "Copie esa carpeta al PC del operador, cree .env y ejecute Iniciar-Agente.bat"
Write-Host "El primer arranque descarga Firefox de Playwright (una sola vez)."
