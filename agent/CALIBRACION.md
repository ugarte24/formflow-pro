# Calibración RUAT — notas por pantalla

Municipio: **Gobierno Municipal de Riberalta** · App: Contribuyentes · Ver. **6.44.123**

| # | Pantalla | Estado | Notas |
|---|---|---|---|
| 1 | Menú principal | **ok** | Clic en «Contribuyente Natural» |
| 2 | Submenú Contribuyente Natural | **ok** | Clic en «Registro Contribuyente Natural» |
| 3 | Buscar contribuyente | **ok** | CI + cédula + depto en blanco + Buscar |
| 4 | Colocar CI (ejemplo llenado) | **ok** | Ejemplo: `5953040`, complemento vacío |
| 5 | Coincidencia / Asociar | **ok** | Otros municipios → Asociar sin foto, mejor nombre |
| 5b | Ya registrado en Riberalta | **ok** | Solo mensaje; no Nuevo Contribuyente |
| 22 | Asociar otros municipios | **ok** | Sin marcar Imagen; continuar datos faltantes |
| 6 | Recepcionar documentación | **ok** | Solo DOCUMENTO DE IDENTIDAD → Grabar |
| 7 | Datos generales | **ok** | Nombre(s), apellidos, género, SOLTERO(A), fecha DD/MM/AAAA → Aceptar |
| 9 | Resultados dirección | **ok** | Asociar mismo barrio + misma avenida; si no → SIN NOMINAR |
| 10 | Domicilio post-Asociar | **ok** | Puerta o Sin Número → Aceptar |
| 11 | Modal apoderado | **ok** | «¿Desea registrar un Apoderado…?» → **Cancelar** |
| 12 | Información adicional | **ok** | Solo celular aleatorio → Aceptar |
| 13 | Registrar imágenes | **parcial** | Solo Fotografía ≤90 KB; falta Aceptar final |
| 14 | Diálogo carpeta Imágenes | **ok** | No usar carpeta local; inyectar `foto_url` del escaneo |
| 15 | Seleccionar + Abrir | **ok** | Equivale a `set_input_files` con la foto del trámite |
| 16 | Editar Fotografía → Procesar | **ok** | Cuadro remarcado → Procesar |
| 17 | Editar Fotografía → Finalizar | **ok** | Con panel EDITADO visible → **Finalizar** |
| 18 | Registrar imágenes → Aceptar | **ok** | Bajar y **Aceptar** (sin anverso/reverso) |
| 19 | Confirmar trámite | **ok** | **Imprimir Reporte**; Grabar/Salir = operador |
| 20 | Aviso al operador | **ok** | API `formulario_completado`: revisar datos del reporte |
| 21 | Ya registrado en Riberalta | **ok** | Solo mensaje; no iniciar alta |

## Detalle por captura

### 1. Inicio — Menú principal

- **URL:** `http://municipios.ruat.net/ContribuyentesWeb/Administracion/menuPrincipal/MenuPrincipalController.jpf`
- **Columna:** REGISTRO CONTRIBUYENTES
- **Acción:** clic en **Contribuyente Natural**

### 2. Submenú — Contribuyente Natural

- **URL:** `http://municipios.ruat.net/ContribuyentesWeb/Administracion/menuPrincipal/armadoSubmenu.do`
- **Acción:** **Registro Contribuyente Natural**

### 3. Buscar Contribuyente

- **Título:** REGISTRO CONTRIBUYENTE NATURAL — BUSCAR CONTRIBUYENTE
- **Sección:** Criterios Búsqueda
- **Campos:**
  | Label | Acción agente |
  |---|---|
  | *Número Documento | Llenar caja grande con CI (sin complemento). Caja chica tras «-» → vacía |
  | *Tipo Documento | `CEDULA DE IDENTIDAD` (ya suele venir seleccionado) |
  | Departamento Expedido | **Opción en blanco** (nota roja del sistema) |
- **Botón:** **Buscar**
- **No usar:** Búsqueda Avanzada

**Reglas**

- Solo número de CI en el primer input
- Complemento vacío
- No filtrar por departamento expedido

### 4. Colocar CI — ejemplo llenado (antes de Buscar)

Confirma el estado correcto del formulario:

| Campo | Valor ejemplo | Regla |
|---|---|---|
| Número Documento (caja grande) | `5953040` | Solo dígitos del CI |
| Complemento (caja chica tras «-») | *(vacío)* | No completar |
| Tipo Documento | CEDULA DE IDENTIDAD | Ya seleccionado / forzar |
| Departamento Expedido | *(en blanco)* | Nota roja del sistema |
| Siguiente acción | clic **Buscar** | No usar Búsqueda Avanzada |

*(El CI de ejemplo es solo para calibración de layout; en producción viene del OCR.)*

### 21. Contribuyente ya registrado en Riberalta

Tras Buscar, **Resultados** muestra p. ej.:

| PMC | Documento | Nombre | Gobierno Municipal |
|---|---|---|---|
| 5953040018 | CI 5953040 | RENY GUARI TABORGA | **RIBERALTA** |

- **Acción del agente:** NO continuar alta, NO pulsar Nuevo Contribuyente
- **Mensaje al operador** (app Verificar):  
  *«El contribuyente ya tiene un registro en Riberalta…»*
- Nota roja del sistema: si no existe → Nuevo Contribuyente; si otro expedido → Modificación

### 22. Registrado en OTROS municipios → Asociar

Ejemplo: CI `179208` → filas MONTERO / QUILLACOLLO / COCHABAMBA (ninguna RIBERALTA).

| Regla | Acción |
|---|---|
| Checkbox **Imagen** / Fotografía | No usar |
| Links **Asociar** | **No usar** |
| Acción | Clic **Nuevo Contribuyente** |
| Después | Continuar Recepcionar → Datos → Domicilio → … (igual que alta sin resultados) |

Si no hay filas foráneas → **Nuevo Contribuyente**.

### 5–6. Recepcionar documentación

- **Título:** INICIO TRAMITE RECEPCIONAR DOCUMENTACION — REGISTRO CONTRIBUYENTE NATURAL
- **Sección Documentos Requeridos:**
  | Opción | Acción |
  |---|---|
  | *DOCUMENTO DE IDENTIDAD | **Marcar** (checkbox) |
  | PODER | No marcar |
  | FACTURA LUZ/AGUA | No marcar |
- **Datos Tramitador:** dejar vacío — **no** usar link «Registrar» (sin Gestor Trámite)
- **Botones:** **Grabar** (no Limpiar)

Nota: en esta captura no apareció pantalla Asociar (alta nueva). Si tras Buscar hay coincidencia, sigue pendiente documentar Asociar.

### 6. Datos Generales

- **Título:** REGISTRO CONTRIBUYENTE NATURAL — DATOS GENERALES
- **Solo lectura / no tocar:** Número Trámite, Número Documento, Tipo Documento
- **Departamento Expedido:** dejar **en blanco**
- **Campos a completar (si vacíos):**

| Label RUAT | Ejemplo | Origen |
|---|---|---|
| *Nombre(s) | RENY | OCR `nombres` |
| *Primer Apellido | GUARI | OCR primer apellido |
| Segundo Apellido | TABORGA | OCR segundo apellido |
| Apellido Esposo | *(vacío)* | No llenar |
| *Género | MASCULINO / FEMENINO | radios |
| *Estado Civil | SOLTERO(A) | mapear SOLTERO→SOLTERO(A) |
| *Fecha Nacimiento | 07/09/1981 | formato **DD/MM/AAAA** |

- **Botón:** **Aceptar** (no Limpiar ni Cancelar Trámite)

### 7. Domicilio Legal — Búsqueda Avanzada

- **Título:** REGISTRO CONTRIBUYENTE NATURAL — DOMICILIO LEGAL
- **Acción inmediata:** clic en el link **Búsqueda Avanzada**  
  (texto: *«Para obtener la ubicación por área municipio, tipo lugar y nombre lugar, ir a Búsqueda Avanzada.»*)
- **Campos visibles (se completan vía Búsqueda Avanzada / después):**
  - Área Municipio: URBANO | RURAL (default observado: URBANO)
  - Distrito/Comunidad, Barrio, Tipo Lugar, Nombre Lugar (selects)
  - Número Puerta + check Sin Número
  - Dirección Descriptiva
  - Sección Edificio (opcional): Nombre Edificio, Bloque, Piso, Departamento

### 8. Búsqueda Avanzada Dirección

- **Título:** REGISTRO CONTRIBUYENTE NATURAL — BUSQUEDA AVANZADA DIRECCION
- **Campos:**
  | Campo | Valor |
  |---|---|
  | Área Municipio | **URBANO** |
  | Tipo Lugar | **AVENIDA** |
  | Nombre Lugar | avenida del CI (ej. `PAQUIO`) |
- **Botón:** **Buscar**
- **Links:** Anterior · Nueva Búsqueda

#### Regla de negocio (confirmada)

1. Tipo Lugar = **AVENIDA**
2. Nombre Lugar = avenida del CI → **Buscar**
3. En **Resultados** (columnas: Distrito/Comunidad · Barrio · Tipo Lugar · Nombre Lugar · Asociar):
   - Buscar la fila donde **Barrio = barrio del CI** y **Nombre Lugar = avenida del CI**
   - Clic en **Asociar** de esa fila
4. **Solo si no está esa combinación:**
   - Nombre Lugar = **SIN NOMINAR** → **Buscar**
   - Asociar la fila **BARRIO SIN NOMINAR** + **AVENIDA SIN NOMINAR**
   - Eso regresa al domicilio (sección 7)

Ejemplo captura: búsqueda `PAQUIO` → 13 filas DISTRITO 5 / AVENIDA PAQUIO / barrios distintos → asociar solo el barrio que coincida con el CI.

### 9. Resultados — Asociar barrio + avenida

- Tabla **Resultados** con link **Asociar** por fila
- Emparejar **ambos** campos del CI (no solo la avenida)
- Si falla el match → recién aplicar fallback SIN NOMINAR del paso 8

### 10. Domicilio Legal — tras Asociar

Ejemplo observado: DISTRITO 5 · LOS TAJIBOS · AVENIDA · PAQUIO (ya cargados).

| Campo | Regla |
|---|---|
| Distrito / Barrio / Tipo / Nombre Lugar | Ya vienen de Asociar — no retocar |
| **Número Puerta** | Si el CI trae número → escribirlo y **NO** marcar Sin Número |
| **Sin Número** | Solo si el CI **no** trae número de puerta (queda S/N) |
| Dirección Descriptiva | **En blanco** |
| Edificio / Nombre / Bloque / Piso / Depto | **En blanco** (no marcar Edificio) |
| Botón | Bajar y **Aceptar** |

### 11. Modal Apoderado / Representante Legal

- **Mensaje:** `¿Desea registrar un Apoderado/Representante Legal?`
- **Botones:** Aceptar | **Cancelar**
- **Acción fija:** siempre **Cancelar** (dismiss del confirm del navegador)
- Fondo muestra «En progreso…» mientras aparece el diálogo

### 12. Información Adicional

- **Título:** REGISTRO CONTRIBUYENTE NATURAL — INFORMACION ADICIONAL
- **Solo llenar:** *Teléfono Celular* con número aleatorio (ej. `78998541`, viene de la API)
- **Dejar en blanco:** Teléfono Domicilio/Referencia, Oficina, correos, casillas, páginas web
- **Botón:** **Aceptar** (no Limpiar / Cancelar Trámite / Anterior)

### 13. Registrar Imágenes

- **Título:** REGISTRO CONTRIBUYENTE NATURAL — REGISTRAR IMAGENES
- **Secciones:**
  | Sección | Máx. | Acción agente |
  |---|---|---|
  | **Fotografía** | 90 KB | Clic **Examinar…** y subir la foto del contribuyente |
  | Documento Identidad Anverso | 60 KB | **No** subir |
  | Documento Identidad Reverso | 60 KB | **No** subir |
- Observaciones: en blanco
- Nota RUAT: foto obligatoria si es propietario de vehículo; de todos modos en MVP siempre se sube la foto

**Pendiente:** captura tras seleccionar el archivo + botón final (Aceptar / Grabar).

### 14. Diálogo Windows «Carga de archivos»

- Al pulsar Examinar, Windows abre una carpeta (ej. Imágenes) con muchas fotos.
- **El agente NO navega esa carpeta ni elige a ojo.**
- En su lugar descarga la foto del trámite desde la API (`foto_url`, la que se escaneó en Digitalizador, ≤90 KB) y la asigna al `input[type=file]` con Playwright (`set_input_files`).
- Así se evita el diálogo nativo y se garantiza que sea **la foto de ese contribuyente**, no otra de la carpeta.

### 15. Seleccionar imagen → Abrir (equivalente manual)

- Flujo manual humano: elegir el archivo (ej. `Image_20260815_0001`) → **Abrir**
- Flujo agente: equivalente automático con la foto del escaneo del mismo trámite
  - No hace clic en Abrir del diálogo Windows
  - `set_input_files(ruta_foto_descargada)` = seleccionar + Abrir en un solo paso
- Resultado esperado en RUAT: «archivo seleccionado» en la sección **Fotografía**

### 16. Editar Fotografía

- **Título:** REGISTRO CONTRIBUYENTE NATURAL — EDITAR FOTOGRAFÍA
- Muestra la foto (ej. con leyenda C.I. abajo) y un **cuadro remarcado** (recorte)
- Ajustar el cuadro para que quede solo el área deseada (rostro/hombros; fuera del cuadro queda atenuado)
- Botones: **Procesar** · Rotar · Finalizar
- **Acción:** ajustar → **Procesar**
- Agente MVP: si el recorte por defecto de RUAT ya enmarca bien, pulsa **Procesar** (y **Finalizar** si sigue visible)

### 17. Tras Procesar — Finalizar

- Pantalla sigue en EDITAR FOTOGRAFÍA
- Izquierda: **ORIGINAL** (con cuadro)
- Derecha: **EDITADO** (recorte final)
- Cuando la imagen ya está enmarcada en EDITADO → clic **Finalizar**
- No usar Rotar salvo que la foto venga de lado

### 18. Registrar Imágenes — Aceptar

- Tras **Finalizar**, vuelve a REGISTRAR IMAGENES con la fotografía ya asociada (miniatura)
- **No** subir anverso ni reverso
- Observaciones en blanco
- **Bajar** en la página y clic **Aceptar**
- Fin del flujo de imágenes del MVP (modo seguro: operador revisa/guarda el trámite si aplica)

### 19. Confirmar Trámite — Pasos Finales

- **Título:** REGISTRO CONTRIBUYENTE NATURAL — CONFIRMAR TRAMITE

| Paso | Botón | Quién |
|---|---|---|
| 1 | **Imprimir Reporte** | Agente |
| 2 | **Grabar** | MVP: operador · **Fase 2: agente** (`GRABAR_AUTOMATICO=1`) |
| 3 | **Salir** | Operador |

- Tras Imprimir Reporte el agente reporta `formulario_completado` a la API
- No usar Anterior / Cancelar Trámite
- **Decisión:** en Fase 2 sí se automatiza Grabar

### 20. Aviso al operador (revisar datos)

- Tras **Imprimir Reporte** se abre el PDF «REPORTE DE CONTROL DE DATOS»
- El agente **no** pulsa Grabar ni Salir
- Envía a Digitalizador estado `formulario_completado` con mensaje para el operador, p. ej.:
  > Revise el Reporte de Control de Datos, confirme con el contribuyente y luego pulse Grabar en RUAT.
- En la app (Verificar) el operador ve ese aviso
