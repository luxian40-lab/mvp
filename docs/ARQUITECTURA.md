# Arquitectura del Sistema Eki

## Visión General

Eki es una plataforma B2B de educación agrícola por WhatsApp, construida con Django 5.2 y desplegada en AWS Elastic Beanstalk.

## Stack Tecnológico

| Componente | Tecnología |
|---|---|
| **Backend** | Django 5.2.9 (Python 3.14) |
| **Base de datos** | PostgreSQL (RDS) en producción, SQLite local |
| **Almacenamiento** | AWS S3 (bucket: `eki-produccion`) |
| **Hosting** | AWS Elastic Beanstalk (us-east-2) |
| **WhatsApp** | Twilio Content Templates API |
| **IA** | OpenAI GPT-4o-mini (tutores IA) |
| **Admin** | Django Admin + Jazzmin (tema Flatly) |
| **Audio** | Whisper (transcripción de notas de voz) |

## Diagrama de Componentes

```
┌──────────────────────────────────────────────────────────┐
│                    AWS Elastic Beanstalk                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │  Django App  │  │   Gunicorn  │  │   Nginx     │     │
│  │  (core/)     │  │  (WSGI)     │  │  (proxy)    │     │
│  └──────┬───────┘  └─────────────┘  └─────────────┘     │
│         │                                                 │
│  ┌──────┴───────┐  ┌─────────────┐  ┌─────────────┐     │
│  │  Webhook     │  │  Admin UI   │  │  Dashboard  │     │
│  │  /webhook/   │  │  /admin/    │  │  /admin/    │     │
│  └──────────────┘  └─────────────┘  └─────────────┘     │
└──────────────────────────────────────────────────────────┘
         │                   │                │
    ┌────┴────┐        ┌────┴────┐      ┌────┴────┐
    │ Twilio  │        │ AWS RDS │      │ AWS S3  │
    │ WhatsApp│        │ Postgres│      │ Media   │
    └─────────┘        └─────────┘      └─────────┘
```

## Estructura de la App `core/`

```
core/
├── models.py                    # Modelos principales (Estudiante, Curso, Campana, etc.)
├── models_certificados.py       # PlantillaCertificado, Certificado
├── models_extras.py             # ArchivoModulo, modelos auxiliares
├── admin.py                     # Admin registrations (~5000 líneas)
├── admin_campana_actualizado.py # CampanaUnica admin (legacy, oculto)
├── views.py                     # Webhook, dashboard, importación, reportes
├── whatsapp_service.py          # Funciones de envío WhatsApp (templates Twilio)
├── selector_curso.py            # Lógica de selección y avance de cursos
├── security_handler.py          # Verificación de seguridad, soporte
├── tutor_ia_modulo.py           # Agentes IA (Gerónimo, María)
├── gamificacion.py              # PerfilGamificacion, puntos, niveles
├── services.py                  # Servicios de ejecución de campañas
├── utils.py                     # Utilidades (enviar_whatsapp_twilio raw)
├── pregunta_handler.py          # Validación de respuestas de exámenes
├── helpers_examenes.py          # Lógica de avance de módulos
└── migrations/                  # 54 migraciones (0001-0054)
```

## Modelos Principales

### Estudiante
- Campos: `cedula` (unique), `telefono` (unique), `nombre`, `municipio`, `departamento`, `genero`
- Estado: `estado_chat` (máquina de estados: ESPERANDO_HABEAS_DATA → ESPERANDO_CEDULA → CONFIRMANDO_DATOS → ACTIVO)
- Relaciones: FK `cliente`, M2M `grupos`

### Curso → Modulo → Examen → PreguntaExamen
- Curso tiene N módulos ordenados por `numero`
- Cada módulo puede tener examen obligatorio
- ProgresoEstudiante trackea avance por módulo

### Campaña (unificada)
- Envío masivo de Content Templates de Twilio
- Soporta: `template_twilio_id` (SID directo) o `plantilla` (FK a Plantilla Django)
- Audiencia: individual o por grupo
- Programación opcional con `fecha_programada`
- Estadísticas: `total_enviados`, `respuestas_si`, `respuestas_no`

### Certificado
- Se genera al completar un curso
- Plantilla: imagen S3 (método principal) o PDF con variables
- Se sube a S3 automáticamente

## Flujo de WhatsApp (Webhook)

```
Mensaje entrante → /webhook/ (POST)
    │
    ├── ¿Registrado? → NO → enviar_mensaje_ventas() [Template no_registrado]
    │                           → ProspectoB2B (Lead B2B)
    │
    └── ¿Registrado? → SÍ → Máquina de estados:
            │
            ├── ESPERANDO_HABEAS_DATA → enviar_habeas_data() [Botones]
            ├── ESPERANDO_CEDULA → validar cédula → enviar_confirmacion_datos()
            ├── CONFIRMANDO_DATOS → enviar_menu_principal()
            ├── ESPERANDO_AYUDA_MODIFICAR → centro de ayuda
            └── ACTIVO → Menú:
                    ├── "Mis cursos" → enviar_lista_cursos() [Templates dinámicos]
                    ├── "Mis puntos" → enviar_gamificacion_visual()
                    ├── "Ayuda" → procesar_solicitud_soporte()
                    └── "Menú" → enviar_menu_principal()
```

## Content Templates de Twilio

| Template | Content SID | Uso |
|---|---|---|
| habeas_data | HXc7923656da... | Onboarding: botones Acepto/No acepto |
| confirmar_datos_v2 | HX34fd358719... | Confirmar datos: Sí/Modificar |
| menu_principal | HXc9027f1ab8... | Menú: Mis cursos/Mis puntos/Ayuda |
| no_registrado | HX763a774eada... | No registrado: 3 botones |
| listadocursos1 | HX6a31cb9924... | 1 curso (1 botón) |
| listadocursos2 | HXcb7abe9df9... | 2 cursos (2 botones) |
| listadocursos3 | HX09b9105e56... | 3 cursos (3 botones) |

## Importación de Estudiantes

Formato Excel (8 columnas):

| Col | Campo | Obligatorio |
|---|---|---|
| A | Cédula | ✅ |
| B | Nombre | ✅ |
| C | Teléfono | ✅ |
| D | Municipio | ✅ |
| E | Departamento | ✅ |
| F | Género | ✅ |
| G | Curso | Opcional |
| H | Cliente | Opcional |

- Todos los textos se normalizan a minúsculas (`.lower()`)
- El teléfono se normaliza a formato colombiano (57XXXXXXXXXX)
- Los géneros aceptados: masculino, femenino, otro, no reporta (+ variantes)

## Despliegue

- **Rama**: `fresh-push-3`
- **EB Environment**: `eki-prod-final`
- **Región**: `us-east-2`
- **Procfile**: `web: gunicorn mvp_project.wsgi --log-file -`

```bash
git add -A && git commit -m "descripción" && git push origin fresh-push-3
eb deploy
```
