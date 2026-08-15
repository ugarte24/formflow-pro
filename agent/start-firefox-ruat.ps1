# Abre Firefox con depuración remota para que el agente se conecte (FIREFOX_MODE=connect_cdp).
# 1) Cierre todas las ventanas de Firefox.
# 2) Ejecute este script.
# 3) Inicie sesión en RUAT en la ventana que se abre.
# 4) En otra terminal: cd agent; python main.py  (con FIREFOX_MODE=connect_cdp)

param(
  [int]$Port = 9222,
  [string]$StartUrl = ""
)

$firefox = @(
  "${env:ProgramFiles}\Mozilla Firefox\firefox.exe",
  "${env:ProgramFiles(x86)}\Mozilla Firefox\firefox.exe",
  "$env:LOCALAPPDATA\Mozilla Firefox\firefox.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $firefox) {
  Write-Error "No se encontró firefox.exe"
  exit 1
}

$profile = Join-Path $env:USERPROFILE "DigitalizadorAgent\firefox-profile-cdp"
New-Item -ItemType Directory -Force -Path $profile | Out-Null

Write-Host "Iniciando Firefox con --remote-debugging-port=$Port"
Write-Host "Perfil: $profile"
Write-Host "Luego configure agent/.env:"
Write-Host "  FIREFOX_MODE=connect_cdp"
Write-Host "  FIREFOX_CDP_URL=http://127.0.0.1:$Port"

$args = @(
  "-profile", $profile,
  "-remote-debugging-port", "$Port",
  "-no-remote"
)
if ($StartUrl) { $args += $StartUrl }

Start-Process -FilePath $firefox -ArgumentList $args
