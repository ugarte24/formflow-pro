# Publica DigitalizadorAgent-Setup.zip en Supabase Storage
# para que el administrador lo descargue desde la web (Admin).
#
# Uso (después de Crear-Paquete-Instalacion.ps1):
#   .\Publicar-Instalador.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$zip = Join-Path $PSScriptRoot "dist\DigitalizadorAgent-Setup.zip"
if (-not (Test-Path $zip)) {
  Write-Host "No hay ZIP. Generando…" -ForegroundColor Yellow
  & .\Crear-Paquete-Instalacion.ps1
}

$root = Split-Path $PSScriptRoot -Parent
$envFile = Join-Path $root ".env"
if (-not (Test-Path $envFile)) { throw "Falta $envFile con SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY" }

# Cargar .env simple
Get-Content $envFile | ForEach-Object {
  if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
  $p = $_.Split('=', 2)
  if ($p.Length -eq 2) {
    $name = $p[0].Trim()
    $val = $p[1].Trim().Trim('"').Trim("'")
    [Environment]::SetEnvironmentVariable($name, $val, "Process")
  }
}

$url = $env:SUPABASE_URL
$key = $env:SUPABASE_SERVICE_ROLE_KEY
if (-not $url -or -not $key) { throw "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY incompletos en .env" }

$objectPath = "releases/DigitalizadorAgent-Setup.zip"
$endpoint = "$($url.TrimEnd('/'))/storage/v1/object/agente/$objectPath"

Write-Host "Subiendo instalador a Storage (agente/$objectPath)…" -ForegroundColor Cyan
$bytes = [System.IO.File]::ReadAllBytes($zip)
$headers = @{
  "Authorization" = "Bearer $key"
  "apikey" = $key
  "Content-Type" = "application/zip"
  "x-upsert" = "true"
}

# Invoke-RestMethod con body binario
Invoke-RestMethod -Method Post -Uri $endpoint -Headers $headers -Body $bytes | Out-Null

$sizeMb = [math]::Round((Get-Item $zip).Length / 1MB, 1)
Write-Host ""
Write-Host "Publicado ($sizeMb MB)." -ForegroundColor Green
Write-Host "El administrador lo descarga en: Admin → Instalador PC operador"
