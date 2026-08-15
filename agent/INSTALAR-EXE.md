# Instalación del Agente Digitalizador en el PC del operador

## Forma recomendada (desde la web)

1. Entrá a **Admin** en Digitalizador
2. Pulsá **Descargar DigitalizadorAgent-Setup.zip**
3. Pasá el ZIP al PC del operador (USB / Drive / WhatsApp)
4. Descomprimí → doble clic en **Instalar.bat**
5. Completá `BASE_URL` y `CODIGO_PC` (ej. `PC-VEN-01`) — **sin token**
6. Usá el icono **Digitalizador Agent** del Escritorio

El programa queda en `%LOCALAPPDATA%\Digitalizador\DigitalizadorAgent`.

## Publicar una versión nueva (PC de desarrollo)

```powershell
cd agent
.\build_exe.ps1
.\Crear-Paquete-Instalacion.ps1
.\Publicar-Instalador.ps1
```

También podés subir el ZIP desde Admin → **Publicar nueva versión**.

## Actualizar en el PC del operador

1. Descargá el ZIP nuevo desde Admin
2. Descomprimí y ejecutá otra vez **Instalar.bat** (conserva el `.env` / código de PC)

## Notas

- No hace falta instalar Python en el PC del operador
- El primer arranque descarga Firefox de Playwright (una sola vez)
- Fase 2 Grabar automático: `GRABAR_AUTOMATICO=1` en `.env`
