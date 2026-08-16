# Digitalizador Agent (Windows)

Agente de escritorio que consulta la API de FormFlow Pro y completa el registro **Contribuyente Natural** en RUAT (Firefox).

## Instalación para el PC del operador (.exe)

Ver guía completa: **[INSTALAR-EXE.md](./INSTALAR-EXE.md)**

Resumen:

```powershell
# En PC de desarrollo:
.\build_exe.ps1

# En PC del operador (con la carpeta dist generada):
.\Instalar-en-PC-Operador.ps1
```

## Requisitos (modo desarrollo / Python)

- Windows 10/11
- Python 3.11+
- Firefox (Playwright lo descarga)
- Misma cuenta de Digitalizador (email/contraseña de la web)
- Sesión RUAT en el perfil del agente (IP autorizada del PC)

## Configuración (desarrollo)

```powershell
cd agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install firefox
copy .env.example .env
# Editar .env: BASE_URL
```

## Modos de Firefox

| `FIREFOX_MODE` | Uso |
|---|---|
| `persistent` (default) | Abre un perfil en `%USERPROFILE%\DigitalizadorAgent\firefox-profile`. **Inicie sesión RUAT una vez** ahí; el agente reutiliza cookies/sesión. |
| `connect_cdp` | Adjunta a Firefox ya abierto. Ejecute antes `.\start-firefox-ruat.ps1`, inicie sesión RUAT, luego `python main.py`. |
| `launch` | Firefox limpio (solo pruebas). |

Ajuste selectores CSS/texto en `selectors.json` sin tocar Python.

## Ejecutar

```powershell
python main.py
```

Al arrancar pedirá **email y contraseña** (las mismas de la web) en una ventana. Luego corre en la **bandeja del sistema** (sin consola negra). Clic derecho en el icono → Ver log / Salir. La sesión se guarda en `session.json`; el log en `agent.log`.

Prueba de API sin tocar Firefox:

```powershell
# en .env: DRY_RUN=1
python main.py
```

El agente hace polling a `GET /api/public/agente/pendientes` (Bearer) y reporta con `POST /api/public/agente/resultado`. Cada cuenta solo ve **sus** trámites confirmados.

## Flujo RUAT automatizado

1. Menú → Contribuyente Natural  
2. Buscar CI (tipo cédula, depto en blanco)  
3. Si hay coincidencia → **Asociar** y completar faltantes  
4. Marcar DOCUMENTO DE IDENTIDAD → Grabar  
5. Datos generales (depto en blanco)  
6. Domicilio legal  
7. Modal apoderado → **Cancelar**  
8. Celular aleatorio (viene en el payload)  
9. Subir **solo fotografía** (≤ 90 KB)  
10. Reportar `formulario_completado` (modo seguro: el operador guarda)

## Calibración

### Método rápido (recomendado)

1. Configura `agent/.env` (`FIREFOX_MODE=persistent`, opcional `RUAT_START_URL`).
2. Abre el inspector:

```powershell
cd agent
.\.venv\Scripts\Activate.ps1
python inspect_page.py --wait 30
```

3. En los 30 s navega manualmente a **una** pantalla del flujo (ej. Buscar Contribuyente).
4. El script imprime links, botones, labels, inputs y selects reales.
5. Copia esos textos a `selectors.json` (ver tabla abajo).
6. Repite por cada pantalla: buscar → asociar → recepción → datos → domicilio → apoderado → celular → foto.

### Qué editar en `selectors.json`

| Pantalla RUAT | Clave en JSON | Qué poner |
|---|---|---|
| Menú | `contribuyente_natural.link_name` | Texto exacto del link (ej. `Contribuyente Natural`) |
| Buscar | `buscar.input_documento` | CSS del input CI (`name`/`id` del dump) |
| Buscar | `buscar.tipo_documento_label` | Texto de la opción del select |
| Buscar | `buscar.boton_buscar` | Regex del botón, ej. `^Buscar$` |
| Coincidencia | `asociar.link_name` | Texto del link Asociar |
| Recepción | `recepcion.check_documento` / `boton_grabar` | Texto del check y botón |
| Datos | `datos_generales.*` | Texto de cada label |
| Domicilio | `domicilio.*` | Labels de zona/puerta |
| Apoderado | `apoderado.boton_cancelar` | Texto del botón Cancelar del modal |
| Celular | `info_adicional.celular` | Label del teléfono |
| Foto | `imagenes.input_file` | CSS del `input[type=file]` |

### Tips

- Usa `^Texto$` cuando el botón debe coincidir exacto (evita clics en “Buscar otro”).
- Si el label tiene tilde o `(a)`, prueba alternativas con `|`: `Número|Numero|Nro`.
- Tras editar JSON, reinicia `python main.py` (se carga al inicio).
- Si falla un paso, en la app verás `error_automatizacion` con el mensaje; ajusta solo esa clave.
- No hace falta tocar `ruat_flow.py` salvo casos raros (iframes, shadow DOM).

### Alternativa manual (DevTools)

En Firefox: clic derecho → Inspeccionar → anota `id`/`name` del input y el texto visible del botón/label → pégalo en `selectors.json`.
