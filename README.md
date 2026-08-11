# FormFlow Pro

PRD — Sistema de Digitalización y Automatización de Formularios

Versión: 1.0
Fecha: agosto 2026
Tipo: Aplicación móvil/web + agente de escritorio
Objetivo: Reducir el tiempo de registro de datos de aproximadamente 10 minutos a menos de 1 minuto por formulario.

1. Descripción del producto

El sistema permitirá escanear un documento de identidad utilizando un teléfono celular, extraer automáticamente la información mediante OCR/IA, permitir al operador verificar y corregir los datos y posteriormente enviarlos a un computador autorizado de la empresa.

El computador tendrá instalado un agente de escritorio encargado de recibir la información y utilizarla para completar automáticamente el formulario correspondiente dentro del sistema empresarial que funciona mediante Mozilla Firefox.

El sistema empresarial no será modificado. La automatización trabajará sobre el sistema existente.

2. Problema

Actualmente el operador debe leer manualmente un documento de identidad y trasladar sus datos al sistema de la empresa.

El proceso requiere aproximadamente:

10 minutos por registro.

Esto genera:

 Pérdida de tiempo.

 Digitación repetitiva.

 Posibilidad de errores.

 Fatiga del operador.

 Menor cantidad de registros procesados.

 Necesidad de revisar constantemente los datos introducidos.

3. Objetivo general

Desarrollar una solución que permita capturar automáticamente los datos de un documento de identidad y utilizarlos para completar un formulario del sistema empresarial, reduciendo significativamente el tiempo de digitación manual.

Objetivos específicos

 Permitir escanear documentos desde un teléfono.

 Detectar y extraer automáticamente los datos.

 Estructurar la información obtenida.

 Permitir la corrección manual de datos.

 Enviar los datos al computador autorizado.

 Automatizar el llenado del formulario empresarial.

 Mantener al operador como responsable de la validación final.

 Registrar el historial de operaciones realizadas.

 Detectar errores de lectura y campos incompletos.

 Reducir el tiempo de registro de aproximadamente 10 minutos a menos de 1 minuto.

4. Datos que se deben extraer

La primera versión trabajará con los siguientes datos:

CampoFuenteNúmero de documentoDocumento de identidadNombresDocumento de identidadApellidoDocumento de identidadGéneroDocumento de identidadEstado civilDocumento / fuente disponibleFecha de nacimientoDocumento de identidadBarrioDocumento / información complementariaAvenidaDocumento / información complementariaNúmero de puertaDocumento / información complementaria

Importante: durante el análisis del documento real se deberá verificar cuáles de estos datos aparecen físicamente en el documento de identidad y cuáles deberán obtenerse de otra fuente o introducirse manualmente.

5. Usuarios

Operador

Será el usuario principal.

Podrá:

 Escanear documentos.

 Revisar información.

 Editar datos.

 Enviar información al computador.

 Consultar el estado del procesamiento.

 Ver errores.

Administrador

Podrá:

 Administrar usuarios.

 Administrar computadores autorizados.

 Consultar historial.

 Configurar campos.

 Consultar errores.

 Administrar conexiones.

6. Arquitectura general

La solución estará compuesta por tres partes:

             ┌──────────────────────┐
             │      📱 CELULAR      │
             │                      │
             │ Cámara + OCR + IA    │
             └──────────┬───────────┘
                        │
                        ▼
             ┌──────────────────────┐
             │     ☁️ BACKEND       │
             │                      │
             │ Datos + autenticación│
             │ + comunicación       │
             └──────────┬───────────┘
                        │
                        ▼
             ┌──────────────────────┐
             │ 💻 AGENTE WINDOWS    │
             │                      │
             │ Recibe datos         │
             │ Automatiza Firefox   │
             └──────────┬───────────┘
                        │
                        ▼
             ┌──────────────────────┐
             │   🦊 FIREFOX         │
             │                      │
             │ Sistema empresarial  │
             └──────────────────────┘

7. Aplicación móvil

7.1 Inicio

La pantalla principal tendrá:

 Escanear documento

 Documentos pendientes

 Historial

 Estado de conexión

 Perfil del operador

Ejemplo:

┌──────────────────────────────┐
│ Digitalizador                │
│                              │
│ Hola, Operador               │
│                              │
│       ┌──────────────┐       │
│       │ 📷 ESCANEAR  │       │
│       │  DOCUMENTO   │       │
│       └──────────────┘       │
│                              │
│ Pendientes              2    │
│ Procesados hoy         18    │
│                              │
│ Inicio  Historial  Perfil   │
└──────────────────────────────┘

8. Escaneo del documento

Al seleccionar Escanear documento, se abrirá la cámara.

La aplicación deberá:

 Detectar los bordes del documento.

 Recomendar colocar el documento correctamente.

 Detectar iluminación insuficiente.

 Detectar movimiento o imagen borrosa.

 Capturar automáticamente cuando la imagen sea adecuada.

 Permitir captura manual.

Validaciones

✓ Documento detectado
✓ Imagen suficientemente clara
✓ Documento completo

Procesando...

Si la imagen no es adecuada:

⚠️ Imagen borrosa

Coloque nuevamente el documento
y mantenga el teléfono estable.

[Volver a escanear]

9. OCR e inteligencia artificial

Después de capturar el documento, el sistema procesará la imagen.

Proceso:

Imagen
   ↓
Preprocesamiento
   ↓
OCR
   ↓
Reconocimiento de campos
   ↓
Normalización
   ↓
Validación
   ↓
Datos estructurados

Ejemplo:

{
  "numeroDocumento": "7845123",
  "nombres": "JUAN CARLOS",
  "apellidos": "PEREZ GOMEZ",
  "genero": "MASCULINO",
  "estadoCivil": "SOLTERO",
  "fechaNacimiento": "15/04/1995",
  "barrio": "SAN JOSE",
  "avenida": "AV. BENI",
  "numeroPuerta": "245"
}

10. Pantalla de verificación

Esta será una de las pantallas más importantes.

La aplicación no debe enviar inmediatamente los datos al sistema empresarial.

Primero mostrará los datos detectados.

El operador podrá:

 Editar.

 Confirmar.

 Volver a escanear.

 Cancelar.

Los campos con baja confianza deberán destacarse.

Ejemplo:

⚠️ DATOS QUE REQUIEREN REVISIÓN

Número de documento
7845123                         ✓

Nombres
JUAN CARLOS                    ✓

Apellidos
PEREZ GOMEZ                    ✓

Barrio
SAN JOSE                       ⚠️

Número de puerta
245                            ✓

[ VOLVER A ESCANEAR ]

[ CONFIRMAR DATOS ]

11. Envío al computador

Una vez confirmados los datos:

CONFIRMAR
    ↓
Servidor
    ↓
Computador autorizado
    ↓
Agente de escritorio

El usuario verá:

✓ Datos enviados

Esperando procesamiento...

12. Agente de escritorio

El computador autorizado tendrá instalado un pequeño programa denominado provisionalmente:

Digitalizador Agent

Su función será servir como puente entre la aplicación y el sistema empresarial.

Funciones

 Iniciar automáticamente con Windows.

 Autenticar el computador.

 Mantener comunicación con el servidor.

 Recibir formularios.

 Detectar Firefox.

 Interactuar con el sistema empresarial.

 Introducir los datos.

 Informar errores.

 Enviar el resultado al servidor.

13. Automatización de Firefox

El agente deberá utilizar el método de automatización que resulte compatible con el sistema empresarial.

Se evaluarán:

Primera opción

Automatización directa de elementos HTML.

Segunda opción

Automatización mediante navegador/RPA.

Tercera opción

Automatización mediante teclado y mouse.

La decisión final se tomará después de analizar las capturas y el comportamiento real del sistema empresarial.

14. Flujo de automatización

Una vez recibido un registro:

1. Recibir datos
        ↓
2. Validar datos
        ↓
3. Comprobar Firefox
        ↓
4. Comprobar sistema empresarial
        ↓
5. Abrir formulario
        ↓
6. Introducir Nº documento
        ↓
7. Introducir nombres
        ↓
8. Introducir apellidos
        ↓
9. Seleccionar género
        ↓
10. Seleccionar estado civil
        ↓
11. Introducir fecha nacimiento
        ↓
12. Introducir barrio
        ↓
13. Introducir avenida
        ↓
14. Introducir Nº puerta
        ↓
15. Verificar formulario
        ↓
16. Esperar confirmación del operador
        ↓
17. Guardar

15. Modo seguro de funcionamiento

Para la primera versión recomiendo:

Automatización hasta completar el formulario.

Pero no guardar automáticamente.

El sistema deberá dejar el formulario listo y mostrar:

✓ FORMULARIO COMPLETADO

Revise la información antes de guardar.

[ GUARDAR EN SISTEMA ]

[ CANCELAR ]

Esto evita que un error del OCR provoque un registro incorrecto.

Posteriormente podremos agregar:

Modo automático

Escanear
 ↓
Extraer
 ↓
Validar
 ↓
Completar
 ↓
Guardar

si las pruebas demuestran una precisión suficiente.

16. Seguridad

Debido a que se manejarán datos personales, la seguridad es crítica.

El sistema deberá implementar:

 Autenticación de usuarios.

 Comunicación HTTPS.

 Tokens de acceso.

 Identificación de computadores autorizados.

 Control de sesiones.

 Registro de operaciones.

 Cifrado de información sensible cuando corresponda.

 Eliminación automática de imágenes después del período establecido.

 Control de permisos.

 Registro de errores.

El agente NO deberá guardar contraseñas del sistema empresarial.

La idea es trabajar sobre la sesión que el operador ya tenga autorizada en el computador.

17. Restricción por IP

El sistema empresarial seguirá funcionando con su mecanismo actual.

No se intentará modificar la restricción de IP.

📱 Celular
    ↓
Tu aplicación
    ↓
💻 PC autorizado
    ↓
Internet
    ↓
IP autorizada
    ↓
Sistema empresarial

Por lo tanto, el sistema empresarial seguirá viendo la IP autorizada de la empresa.

18. Historial

Cada operación deberá registrar:

 Fecha.

 Hora.

 Operador.

 Documento procesado.

 Estado.

 Resultado.

 Errores.

 Tiempo de procesamiento.

Ejemplo:

FechaDocumentoEstadoTiempo11/08/267845123✓ Completado42 s11/08/264521789✓ Completado38 s11/08/269854211⚠️ Revisado55 s

19. Estados del documento

Cada documento tendrá un estado:

CAPTURADO
    ↓
PROCESANDO
    ↓
DATOS EXTRAÍDOS
    ↓
PENDIENTE DE REVISIÓN
    ↓
CONFIRMADO
    ↓
ENVIADO AL PC
    ↓
FORMULARIO COMPLETADO
    ↓
REGISTRADO

En caso de error:

ERROR OCR
ERROR DE CONEXIÓN
ERROR DE AUTOMATIZACIÓN
ERROR DEL SISTEMA EMPRESARIAL
CANCELADO

20. Requisitos funcionales

RF-01

El sistema debe permitir capturar fotografías de documentos desde el celular.

RF-02

El sistema debe procesar la imagen mediante OCR.

RF-03

El sistema debe identificar los campos definidos.

RF-04

El usuario debe poder modificar los datos detectados.

RF-05

El sistema debe validar los datos antes de enviarlos.

RF-06

El sistema debe enviar información al computador autorizado.

RF-07

El agente debe recibir los datos.

RF-08

El agente debe interactuar con Firefox.

RF-09

El agente debe completar los campos correspondientes.

RF-10

El sistema debe informar si la automatización fue exitosa.

RF-11

El sistema debe mantener un historial.

RF-12

El sistema debe controlar usuarios y computadores autorizados.

21. Requisitos no funcionales

Rendimiento

La extracción de datos debería realizarse idealmente en:

2–10 segundos.

La automatización del formulario debería ejecutarse en:

2–10 segundos, dependiendo del sistema empresarial.

Disponibilidad

La aplicación deberá poder funcionar durante la jornada laboral sin interrupciones.

Seguridad

Los datos deberán transmitirse mediante conexiones seguras.

Usabilidad

El proceso principal debería requerir pocos pasos:

Escanear → revisar → confirmar.

22. Objetivo de rendimiento

La situación actual:

DOCUMENTO
   ↓
LECTURA MANUAL
   ↓
DIGITACIÓN
   ↓
VERIFICACIÓN
   ↓
REGISTRO

≈ 10 minutos

Objetivo:

ESCANEAR
   ↓
OCR
   ↓
REVISAR
   ↓
AUTOMATIZAR
   ↓
REGISTRAR

≈ 30–60 segundos

El tiempo definitivo dependerá de la estructura real del sistema empresarial.

23. Tecnologías propuestas

Para una primera arquitectura:

Aplicación móvil

React + TypeScript / PWA o aplicación móvil nativa/híbrida.

Funciones:

 Cámara.

 OCR.

 Interfaz.

 Autenticación.

 Comunicación con backend.

Backend

Podría utilizarse:

 Supabase.

 PostgreSQL.

 Storage.

 API.

 Autenticación.

Agente Windows

Podría desarrollarse con:

C#/.NET, o

Python, dependiendo de la tecnología de automatización que resulte más adecuada.

Automatización

La tecnología definitiva dependerá de cómo esté construido el sistema empresarial.

24. MVP — Primera versión

No recomiendo desarrollar todo desde el principio.

El MVP debería hacer únicamente esto:

📱 Escanear documento
       ↓
🤖 Extraer datos
       ↓
✏️ Editar
       ↓
✅ Confirmar
       ↓
📤 Enviar al PC
       ↓
💻 Agente recibe
       ↓
🦊 Firefox
       ↓
✍️ Completar formulario
       ↓
👤 Operador revisa
       ↓
💾 Guardar

Los primeros datos serán:

 Número de documento

 Nombres

 Apellidos

 Género

 Estado civil

 Fecha de nacimiento

 Barrio

 Avenida

 Número de puerta

25. Fase 2

Después de comprobar que el MVP funciona:

 Guardado automático.

 Mayor precisión del OCR.

 Detección automática del documento.

 Historial avanzado.

 Estadísticas.

 Múltiples operadores.

 Múltiples computadores.

 Cola de documentos.

 Reintentos automáticos.

 Notificaciones.

 Control administrativo.

26. Indicadores de éxito

El proyecto será considerado exitoso si consigue:

Tiempo

Reducir el registro de aproximadamente 10 minutos a menos de 1 minuto.

Precisión

Conseguir una alta precisión en los campos extraídos, con revisión humana antes del registro.

Automatización

Completar automáticamente el formulario empresarial sin necesidad de escribir manualmente los datos.

Confiabilidad

Mantener una comunicación estable entre celular → servidor → PC → sistema empresarial.

27. Lo que falta definir

Hay una parte del PRD que deliberadamente no podemos cerrar todavía: la automatización del sistema empresarial.

Cuando tengas las capturas, necesitamos analizar:

 Formulario completo.

 Campos y nombres de cada campo.

 Botones.

 Menús desplegables.

 Ventanas emergentes.

 Pasos necesarios para llegar al formulario.

 Qué sucede después de introducir el número de documento.

 Cómo se guarda el registro.

 Si existen validaciones.

 Cómo está estructurada técnicamente la página.

Con eso podremos convertir este PRD inicial en un PRD técnico mucho más preciso y determinar exactamente cómo desarrollar el Agente Windows.
QUE EL DISEÑO SEA PROFESIONAL

This project was built with [Lovable](https://lovable.dev).

## Build with Lovable

Continue developing this project in the [Lovable editor](https://lovable.dev/projects/4374ffff-8312-4ef5-bd09-a68077549626).

- **Ship faster**: describe what you want to build and Lovable handles the code.
- **Stay in sync**: every change made in Lovable is committed straight to this repository.
- **Full ownership**: this code is yours. Push to `main` on GitHub and your changes sync back into Lovable, ready for your next prompt.

## Development

Prefer working locally? You need Node.js and npm — [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

```sh
git clone <this-repository-url>
cd <repository-name>
npm i
npm run dev
```
