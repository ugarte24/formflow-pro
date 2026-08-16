# Instalación del Agente Digitalizador en el PC del operador

## Forma recomendada (desde la web)

1. Entrá a **Admin** en Digitalizador
2. Pulsá **Descargar DigitalizadorAgent-Setup.zip**
3. Pasá el ZIP al PC del operador (USB / Drive / WhatsApp)
4. Descomprimí → doble clic en **Instalar.bat**
5. Abrí **Digitalizador Agent** e iniciá sesión con el **mismo email y contraseña** de la web
6. El agente queda en la **bandeja del sistema** (junto al reloj); no usa ventana negra
7. Dejá Firefox/RUAT listo; los trámites que confirmés en el celular llegan a **tu** cola

El programa queda en `%LOCALAPPDATA%\Digitalizador\DigitalizadorAgent`.

## Publicar una versión nueva (PC de desarrollo)

```powershell
cd agent
.\build_exe.ps1
.\Crear-Paquete-Instalacion.ps1
.\Publicar-Instalador.ps1
```

También podés publicar con:
.\Publicar-Instalador.ps1 -Version 1.1.0

## Actualizar en el PC del operador

1. Descargá el ZIP nuevo desde Admin
2. Descomprimí y ejecutá otra vez **Instalar.bat** (conserva el `.env` y la sesión)

## Notas

- No hace falta instalar Python en el PC del operador
- El primer arranque descarga Firefox de Playwright (una sola vez)
- **Nightly:** una sola ventana del agente. RUAT solo cambia el diseño (menú → submenú → formularios). No hace falta abrir otra Nightly. Si se pierde el control: cerrá Nightly → Digitalizador Agent → login RUAT → reenviá
- Fase 2 Grabar automático: `GRABAR_AUTOMATICO=1` en `.env`
