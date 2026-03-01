# Diagrama de Flujo — Eki WhatsApp Bot

## Flujo Principal del Webhook

```
                    ┌─────────────────┐
                    │  Mensaje entrante│
                    │  /webhook/ POST  │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  Parsear payload │
                    │  (JSON o Form)   │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ ¿Tiene audio?   │──── SÍ ──→ Transcribir (Whisper)
                    └────────┬────────┘                    │
                         NO  │◄────────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │ Limpiar teléfono│
                    │ Guardar en Log  │
                    └────────┬────────┘
                             │
                ┌────────────▼────────────┐
                │ ¿Estudiante registrado? │
                └────┬──────────────┬─────┘
                     │              │
                    SÍ             NO
                     │              │
                     │    ┌─────────▼──────────┐
                     │    │ ¿Prospecto existe?  │
                     │    └────┬──────────┬─────┘
                     │         │          │
                     │        SÍ         NO
                     │         │          │
                     │         │    ┌─────▼──────────┐
                     │         │    │ Crear Prospecto │
                     │         │    │ B2B             │
                     │         │    └─────┬───────────┘
                     │         │          │
                     │    ┌────▼──────────▼──────┐
                     │    │ enviar_mensaje_ventas│
                     │    │ [Template no_registr]│
                     │    └──────────────────────┘
                     │
            ┌────────▼────────┐
            │  Máquina de     │
            │  estados        │
            └────────┬────────┘
                     │
     ┌───────┬───────┼───────┬───────┬──────────┐
     ▼       ▼       ▼       ▼       ▼          ▼
  HABEAS   CEDULA  CONFIRM  AYUDA  ACTIVO    LEGACY
   DATA    (2FA)    DATOS   MODIF           (tutor IA,
                                             examen)
```

## Flujo de Onboarding (Nuevos Estudiantes)

```
Estudiante importado por Excel
    │
    ▼
estado_chat = ESPERANDO_HABEAS_DATA
    │
    ▼ (primer mensaje)
┌───────────────────────────┐
│ enviar_habeas_data()      │
│ Template: [Acepto][No]    │
└─────────────┬─────────────┘
              │
    ┌─────────▼──────────┐
    │ Respuesta: ¿Acepto? │
    └──┬──────────────┬───┘
       │              │
    "Acepto"       "No acepto"
       │              │
       │         ┌────▼──────────┐
       │         │ Mensaje: "Sin │
       │         │ aceptación no │
       │         │ podemos..."   │
       │         └───────────────┘
       │
       ▼
estado_chat = ESPERANDO_CEDULA
       │
       ▼ (escribe cédula)
  ┌────────────────────┐
  │ ¿cedula == BD?     │
  └──┬──────────────┬──┘
     │              │
    SÍ             NO
     │              │
     │         "Cédula no coincide,
     │          intenta de nuevo"
     │
     ▼
estado_chat = CONFIRMANDO_DATOS
     │
     ▼
┌────────────────────────────┐
│ enviar_confirmacion_datos()│
│ Template: [Sí][Modificar]  │
└──────────────┬─────────────┘
               │
    ┌──────────▼───────────┐
    │ ¿Datos correctos?    │
    └──┬────────────────┬──┘
       │                │
    "Sí, todo         "Modificar"
     bien"              │
       │          ┌─────▼──────────────┐
       │          │ Centro de Ayuda:    │
       │          │ 1. Soporte email    │
       │          │ 2. Coordinador      │
       │          │ 3. Reintentar cédula│
       │          └────────────────────┘
       │
       ▼
estado_chat = ACTIVO
       │
       ▼
┌──────────────────────────┐
│ enviar_menu_principal()  │
│ [Mis cursos][Puntos][?]  │
└──────────────────────────┘
```

## Flujo de Cursos

```
"Mis cursos" / botón
     │
     ▼
┌──────────────────────────┐
│ enviar_lista_cursos()    │
│ Template dinámico:       │
│  1 curso → listadocursos1│
│  2 cursos → listadocursos2│
│  3 cursos → listadocursos3│
└──────────┬───────────────┘
           │
           ▼ (selecciona curso)
┌──────────────────────────┐
│ ProgresoEstudiante       │
│ (crear o retomar)        │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│ Mostrar Módulo actual    │
│ + contenido + multimedia │
└──────────┬───────────────┘
           │
           ▼ (escribe "listo")
┌──────────────────────────┐
│ ¿Examen obligatorio?     │
├── SÍ ──→ Examen          │
│          (aprobar ≥ X%)   │
└── NO ──→ Siguiente módulo │
           │
     ┌─────▼──────────────┐
     │ ¿Módulo impar?     │── SÍ ──→ Profesor Gerónimo (IA)
     │ ¿Módulo 4?         │── SÍ ──→ María (Revisión progreso)
     └─────┬──────────────┘
           │
           ▼ (último módulo)
┌──────────────────────────┐
│ ¡Curso completado!       │
│ Certificado disponible   │
└──────────────────────────┘
```

## Flujo de Campañas

```
Admin crea Campaña
     │
     ├── Content SID de Twilio (directo)
     └── O Plantilla Django con Content SID
     │
     ▼
Seleccionar audiencia:
     ├── Individual (M2M destinatarios)
     └── Grupo (todos los del grupo)
     │
     ▼ (acción: Ejecutar Campaña)
┌──────────────────────────┐
│ Para cada destinatario:  │
│   enviar_template_twilio │
│   (content_sid, vars)    │
│   Registrar en EnvioLog  │
└──────────┬───────────────┘
           │
           ▼
Estadísticas actualizadas:
  total_enviados, respuestas_si, respuestas_no
```

## Flujo de Importación Excel

```
Admin sube archivo .xlsx
     │
     ▼
Validar formato (8 columnas)
     │
     ▼
Por cada fila:
  ├── Validar campos obligatorios (6)
  ├── Normalizar: .lower(), teléfono 57XX
  ├── Normalizar género (masculino/femenino/otro/no reporta)
  ├── Buscar o crear Estudiante
  ├── Asignar cliente (si se especifica)
  └── Inscribir en curso (si se especifica) → ProgresoEstudiante
     │
     ▼
Reporte: creados / actualizados / inscritos / advertencias
```
