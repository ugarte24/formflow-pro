# Publica DigitalizadorAgent-Setup.zip + version.json en Supabase Storage
# para que el administrador lo descargue desde la web (Admin).
#
# Uso:
#   .\Publicar-Instalador.ps1              # usa agent/VERSION
#   .\Publicar-Instalador.ps1 -Version 1.1.0

param(
  [string]$Version = ""
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$versionFile = Join-Path $PSScriptRoot "VERSION"
if (-not $Version) {
  if (Test-Path $versionFile) {
    $Version = (Get-Content $versionFile -Raw).Trim()
  } else {
    $Version = "1.0.0"
  }
}
if ($Version -notmatch '^\d+\.\d+\.\d+') {
  throw "Versión inválida: $Version (use formato X.Y.Z)"
}
Set-Content -Encoding ascii -NoNewline -Path $versionFile -Value $Version

$zip = Join-Path $PSScriptRoot "dist\DigitalizadorAgent-Setup.zip"
if (-not (Test-Path $zip)) {
  Write-Host "No hay ZIP. Generando…" -ForegroundColor Yellow
  & .\Crear-Paquete-Instalacion.ps1
}

$root = Split-Path $PSScriptRoot -Parent
$envFile = Join-Path $root ".env"
if (-not (Test-Path $envFile)) { throw "Falta $envFile con SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY" }

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

$base = $url.TrimEnd('/')
$headersZip = @{
  "Authorization" = "Bearer $key"
  "apikey" = $key
  "Content-Type" = "application/zip"
  "x-upsert" = "true"
}

$zipPath = "releases/DigitalizadorAgent-Setup.zip"
$metaPath = "releases/version.json"
$zipBytes = [System.IO.File]::ReadAllBytes($zip)
$size = (Get-Item $zip).Length
$publicado = (Get-Date).ToUniversalTime().ToString("o")

$meta = @{
  version = $Version
  archivo = "DigitalizadorAgent-Setup.zip"
  bytes = $size
  publicado_at = $publicado
} | ConvertTo-Json -Compress

Write-Host "Subiendo instalador v$Version…" -ForegroundColor Cyan
Invoke-RestMethod -Method Post -Uri "$base/storage/v1/object/agente/$zipPath" -Headers $headersZip -Body $zipBytes | Out-Null

# Algunos buckets restringen MIME: subir meta como octet-stream también funciona
$headersMeta = @{
  "Authorization" = "Bearer $key"
  "apikey" = $key
  "Content-Type" = "application/octet-stream"
  "x-upsert" = "true"
}
Invoke-RestMethod -Method Post -Uri "$base/storage/v1/object/agente/$metaPath" -Headers $headersMeta -Body ([System.Text.Encoding]::UTF8.GetBytes($meta)) | Out-Null

$sizeMb = [math]::Round($size / 1MB, 1)
Write-Host ""
Write-Host "Publicado v$Version ($sizeMb MB)." -ForegroundColor Green
Write-Host "Admin → Instalador PC operador → Descargar"
