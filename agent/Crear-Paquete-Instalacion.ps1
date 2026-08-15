# Genera un paquete de instalación listo para el PC del operador.
# El operador solo descomprime y hace doble clic en Instalar.bat
# (queda como programa normal: Escritorio + Menú Inicio).
#
# Uso:
#   cd agent
#   .\build_exe.ps1          # si aún no hay dist\
#   .\Crear-Paquete-Instalacion.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$dist = Join-Path $PSScriptRoot "dist\DigitalizadorAgent"
if (-not (Test-Path (Join-Path $dist "DigitalizadorAgent.exe"))) {
  Write-Host "No hay build. Ejecutando build_exe.ps1…" -ForegroundColor Yellow
  & .\build_exe.ps1
}

$stage = Join-Path $PSScriptRoot "dist\Instalador-DigitalizadorAgent"
Remove-Item -Recurse -Force $stage -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $stage | Out-Null

Write-Host "Preparando paquete de instalación…" -ForegroundColor Cyan
Copy-Item -Recurse -Force (Join-Path $dist "*") $stage
Copy-Item -Force (Join-Path $PSScriptRoot "installer\Instalar.bat") $stage
Copy-Item -Force (Join-Path $PSScriptRoot "installer\Instalar.ps1") $stage
Copy-Item -Force (Join-Path $PSScriptRoot "installer\Desinstalar.bat") $stage
Copy-Item -Force (Join-Path $PSScriptRoot "installer\Desinstalar.ps1") $stage

# README corto para el operador
@"
Digitalizador Agent — Instalación
=================================

1. Descomprimí este ZIP en cualquier carpeta (ej. Escritorio).
2. Doble clic en Instalar.bat
3. Completá BASE_URL y CODIGO_PC (ej. PC-VEN-01) cuando se abra el Bloc de notas.
   Ya no se usa token. El admin activa/desactiva operadores desde la web.
4. Usá el icono "Digitalizador Agent" del Escritorio.

No hace falta copiar carpetas a mano después de instalar.
Para quitar el programa: Desinstalar.bat (o el de la carpeta instalada).
"@ | Set-Content -Encoding UTF8 (Join-Path $stage "LEEME.txt")

$zip = Join-Path $PSScriptRoot "dist\DigitalizadorAgent-Setup.zip"
Remove-Item -Force $zip -ErrorAction SilentlyContinue
Compress-Archive -Path (Join-Path $stage "*") -DestinationPath $zip -Force

Write-Host ""
Write-Host "Listo para llevar al PC del operador:" -ForegroundColor Green
Write-Host "  $zip"
Write-Host ""
Write-Host "El operador: descomprime → doble clic en Instalar.bat"
Write-Host "(También quedó la carpeta: $stage)"
Write-Host ""
Write-Host "Para publicarlo en la web (Admin → Descargar):" -ForegroundColor Cyan
Write-Host "  .\Publicar-Instalador.ps1"
