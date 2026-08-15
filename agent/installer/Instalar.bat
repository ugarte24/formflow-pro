@echo off
setlocal
cd /d "%~dp0"
title Instalador Digitalizador Agent
echo.
echo  Instalador Digitalizador Agent
echo  ==============================
echo.

where powershell >nul 2>&1
if errorlevel 1 (
  echo ERROR: No se encontro PowerShell en este PC.
  echo.
  pause
  exit /b 1
)

if not exist "%~dp0DigitalizadorAgent.exe" (
  echo ERROR: Falta DigitalizadorAgent.exe en esta carpeta.
  echo Extraiga TODO el ZIP antes de instalar ^(no ejecute desde dentro del ZIP^).
  echo.
  pause
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Instalar.ps1"
set ERR=%ERRORLEVEL%
echo.
if not "%ERR%"=="0" (
  echo La instalacion termino con error %ERR%.
  echo Si la ventana se cerro antes, ejecute Instalar.bat otra vez.
)
echo.
pause
endlocal
