# 🌾 EKI - Plataforma de Educación Agrícola Digital

**v1.0.0 - PRODUCTO FINAL**

[![Status](https://img.shields.io/badge/Status-Production%20Ready-green)]()
[![Version](https://img.shields.io/badge/Version-1.0.0-blue)]()
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)]()
[![Django](https://img.shields.io/badge/Django-5.2.9-darkgreen)]()

Sistema completo de educación agrícola para campesinos colombianos. Integra WhatsApp, cursos interactivos, certificados digitales, gamificación y un dashboard administrativo profesional.

**🎯 Target:** Campesinos / Cooperativas Agrícolas  
**🌍 Idioma:** Español  
**📱 Plataforma:** Web + WhatsApp  
**🔒 Seguridad:** HABEAS DATA (Ley 1581/2012 Colombia)  

---

## 📚 Documentación

| Documento | Descripción |
|-----------|-------------|
| [PRODUCT_RELEASE_v1.0.md](PRODUCT_RELEASE_v1.0.md) | 📋 Documento oficial de release |
| [README_DEPLOY.md](README_DEPLOY.md) | 🚀 Guía de deployment |
| [GUIA_COMPLETA.md](GUIA_COMPLETA.md) | 📖 Manual completo de features |
| [CERTIFICADOS_URLS_FUNCIONALES.md](CERTIFICADOS_URLS_FUNCIONALES.md) | 📜 Sistema de certificados |
| [DEPLOYMENT_LUNES_CHECKLIST.md](DEPLOYMENT_LUNES_CHECKLIST.md) | ✅ Checklist pre-producción |

---

## ✨ Features Principales v1.0

### ✨ Nuevo: Onboarding Personalizado (v4.0)
* **Flujo de 4 Pasos:**
  1. Aceptación de Habeas Data (Ley 1581 de 2012 - Colombia)
  2. Selección de tipo de documento (CC/TI/CE/PP)
  3. Registro de número de documento
  4. **Captura de nombre real** ✨ NUEVO
* **Experiencia Personalizada:** Cada usuario con su nombre real desde el inicio
* **Validaciones Legales:** Cumplimiento con normativa colombiana
* **Estados Rastreables:** Sistema de estados para seguimiento completo

### 🎯 Sistema de Menú Numérico Simplificado
* **Opciones Deterministas:**
  - 1️⃣ Ver mi progreso → Muestra avance en cursos
  - 2️⃣ Ver cursos disponibles → Lista de cursos activos
  - 3️⃣ Ayuda y soporte → Asistencia inmediata
* **Reconocimiento de Audio:** Números hablados ("uno", "dos", "tres") se normalizan automáticamente
* **Sin Ambigüedades:** Lógica simplificada para sandbox de Twilio
* **Context-Aware:** El sistema entiende el contexto para inscripción en cursos

### 📚 Cursos Profesionales Integrados
* **☕ Café Arábigo: Producción Sostenible** (8 semanas, 5 módulos)
  - Establecimiento del cultivo (variedades, distancias, germinadores)
  - Nutrición y fertilización (NPK, análisis de suelo)
  - Manejo integrado de plagas (roya, broca, control biológico)
  - Cosecha y beneficio (fermentación, secado, calidad)
  - Sostenibilidad y BPA (certificaciones, conservación)
  
* **🥑 Aguacate Hass: Producción Comercial** (7 semanas, 5 módulos)
  - Establecimiento del huerto (selección de sitio, polinización)
  - Nutrición y manejo del suelo (análisis foliar, fertirrigación)
  - Manejo integrado de plagas (Phytophthora, trips)
  - Poda y manejo del dosel (técnicas, épocas)
  - Cosecha y post-cosecha (índices de madurez, cadena de frío)

### 📤 Importación Masiva de Estudiantes
* **Botón Profesional en Admin:** Interfaz moderna con gradiente y animaciones
* **Selección de Curso:** Inscripción automática al importar
* **Formato Excel:** 4 columnas (Teléfono, Nombre, Tipo Doc, Número Doc)
* **Validaciones Automáticas:** Teléfono único, cédula única, formatos correctos
* **Estado Completo:** Estudiantes importados ya tienen onboarding completado

## 🌐 Modelo de Negocio B2B

**EKI opera como plataforma B2B de educación agrícola por WhatsApp.**

### Funcionamiento
- ✅ **Solo EKI accede al Django Admin** (sin acceso para clientes)
- 📤 **EKI envía plantilla Excel** a organizaciones interesadas
- 📥 **Clientes completan plantilla** con datos de sus estudiantes
- ⚙️ **EKI importa estudiantes** y asigna al cliente correspondiente
- 🎓 **EKI gestiona cursos y campañas** para cada cliente
- 📊 **EKI genera reportes** periódicos para clientes

### Clientes Objetivo
- 🌾 Cooperativas agrícolas
- 🏛️ ONGs de desarrollo rural
- 🏢 Empresas del sector agro
- 📚 Instituciones educativas agrícolas

### Facturación
- **Opción 1:** $0.50-$1.00 USD por estudiante activo/mes
- **Opción 2:** $200-$500 USD tarifa plana mensual

Ver documentación completa en:
- [PROCESO_ONBOARDING_CLIENTES.md](PROCESO_ONBOARDING_CLIENTES.md)
- [INSTRUCCIONES_PLANTILLA_CLIENTES.md](INSTRUCCIONES_PLANTILLA_CLIENTES.md)

## �📋 Características Principales

### 🎯 Gestión de Campañas por WhatsApp
* **Creación de Campañas:** Sistema completo para crear y ejecutar campañas de mensajería
* **WhatsApp Cloud API:** Integración con Twilio WhatsApp
* **Plantillas con Imágenes:** Soporte para mensajes con imágenes vía WhatsApp API
* **Envío Masivo:** Importación de estudiantes desde Excel y envío automatizado
* **Seguimiento en Tiempo Real:** Monitoreo del estado de envíos (exitosos, fallidos, pendientes)

### 📊 Dashboard de Métricas
* **Métricas en Tiempo Real:** Estadísticas actualizadas constantemente
* **Análisis de Campañas:** Total de campañas creadas y ejecutadas
* **Estadísticas de WhatsApp:** Mensajes enviados, recibidos y estados
* **Gamificación:** Niveles, badges, puntos y rachas de estudiantes
* **Cursos Activos:** Inscripciones, progreso y completados
* **Historial de Mensajes:** Últimos mensajes con detalles completos
* **Diseño Moderno:** Interfaz profesional con Jazzmin theme

### 📱 Integración WhatsApp
* **Twilio WhatsApp Sandbox:** Envío de mensajes en desarrollo
* **Twilio Production:** Migración lista para botones interactivos
* **Webhook Configurado:** Recepción de mensajes entrantes y respuestas
* **Sistema de Intents:** Detección inteligente de intenciones del usuario
* **Logs Detallados:** Registro completo de conversaciones
* **Agentes IA Especializados:** OpenAI GPT-3.5-turbo + Cohere fallback
* **Normalización de Audio:** Transcripción y normalización de números hablados
* **Context Detection:** Detecta automáticamente el contexto de la conversación

### 🔐 Sistema de Seguridad y Cumplimiento
* **Habeas Data Obligatorio:** Aceptación de términos antes de usar la plataforma
* **Ley 1581 de 2012:** Cumplimiento con normativa colombiana de datos
* **4 Tipos de Documento:** CC, TI, CE, PP
* **Validación de Documentos:** 6-15 dígitos, solo números
* **Nombres Personalizados:** Captura de nombre real del usuario
* **Estados de Onboarding:** Seguimiento completo del proceso

### 👥 Gestión de Estudiantes
* **CRUD Completo:** Alta, baja y modificación de estudiantes
* **Importación Masiva con Curso:** 📤 Botón profesional para importar Excel y asignar curso
* **Validación de Teléfonos:** Normalización automática a formato internacional
* **Validación de Documentos:** Tipos (CC/TI/CE/PP) y números únicos
* **Onboarding Completo:** 4 pasos con nombre personalizado
* **Filtros Avanzados:** Por cliente, curso, estado, fecha
* **Exportación de Reportes:** Descarga de datos en formato Excel con cursos

### 📧 Sistema de Plantillas con Twilio
* **Twilio Content Templates:** Sistema de plantillas aprobadas para WhatsApp
* **Content SIDs:** Gestión de identificadores de plantillas aprobadas
* **Editor de Mensajes:** Creación de plantillas personalizables en Django Admin
* **Soporte de Variables:** Personalización con {nombre}, {telefono}, {curso}
* **Estado de Aprobación:** Badges visuales para plantillas aprobadas/pendientes
* **Vista Previa:** Previsualización de plantillas antes de enviar
* **Reutilización:** Uso de plantillas en múltiples campañas
* **Guía Completa:** Ver [GUIA_TWILIO_TEMPLATES.md](GUIA_TWILIO_TEMPLATES.md)

### 🎮 Gamificación Integrada
* **Sistema de Puntos:** 50 pts por módulo, 200 pts bonus por curso
* **10 Niveles Progresivos:** De 🌱 Semilla a 👑 Maestro Campesino
* **25+ Badges:** Por nivel, racha, cursos, participación y especiales
* **Racha de Estudio:** Contador de días consecutivos activos
* **Ranking/Leaderboard:** Top estudiantes por puntos y racha
* **Notificaciones WhatsApp:** Avisos de nivel-up y badges obtenidos
* **Admin Dashboard:** Gestión completa de perfiles, badges y transacciones

Ver documentación completa en [GAMIFICACION_README.md](GAMIFICACION_README.md)

### 🏢 Multi-Tenancy B2B
* **Sistema de Clientes:** Modelo Cliente para organizaciones
* **Aislamiento de Datos:** Cada cliente tiene sus propios estudiantes
* **Cursos Específicos:** Cursos generales o personalizados por cliente
* **Campañas Segmentadas:** Filtrado automático por cliente
* **Reportes Individualizados:** Excel con datos solo del cliente
* **Importación Masiva:** Plantilla Excel para registro de estudiantes

Ver proceso completo en [PROCESO_ONBOARDING_CLIENTES.md](PROCESO_ONBOARDING_CLIENTES.md)

## 🛠️ Tecnologías

* **Backend:** Python 3.11+ / Django 5.2.9
* **Base de Datos:** SQLite (desarrollo) / PostgreSQL (producción)
* **Admin Interface:** Django Jazzmin 3.0.1
* **IA/ML:**
  - OpenAI GPT-3.5-turbo (agentes especializados)
  - Cohere API (fallback)
  - Sistema multi-agente (Tutor, Motivador, Evaluador)
* **API Integration:** 
  - Twilio WhatsApp Sandbox (desarrollo)
  - Twilio WhatsApp Production (lista para migración)
  - Twilio Content API (templates)
* **Excel Processing:** OpenPyXL 3.1.5
* **HTTP Client:** Requests 2.32+
* **Frontend:** Django Templates + CSS Custom + Jazzmin Theme

## 📁 Estructura del Proyecto

```
eki_mvp/
├── core/                          # Aplicación principal
│   ├── models.py                  # Modelos: Estudiante, Curso, Módulo, ProgresoEstudiante, etc.
│   ├── admin.py                   # Admin con botón de importar estudiantes
│   ├── views.py                   # Vistas del dashboard, reportes y webhooks
│   ├── api.py                     # Endpoints REST para progreso de estudiantes
│   ├── services.py                # Lógica de negocio y envío de campañas
│   ├── utils.py                   # Utilidades (envío WhatsApp vía Twilio)
│   ├── intent_detector.py         # Detección de intenciones (opcion_1/2/3)
│   ├── response_templates.py      # Templates de respuestas con menú numérico
│   ├── message_handler.py         # Procesamiento de mensajes + normalización audio
│   ├── security_handler.py        # Habeas Data + onboarding de 4 pasos
│   ├── agentes_ia.py              # Sistema multi-agente (OpenAI + Cohere)
│   ├── gamificacion.py            # Sistema de puntos, niveles y badges
│   ├── selector_curso.py          # Lógica de selección de cursos
│   └── migrations/                # Migraciones de base de datos
│       └── 0028_agregar_estado_esperando_nombre.py  # ✨ Última migración
├── mvp_project/                   # Configuración del proyecto
│   ├── settings.py                # Configuración general
│   ├── urls.py                    # Rutas principales
│   └── wsgi.py                    # Configuración WSGI
├── templates/                     # Plantillas HTML
│   └── admin/
│       ├── dashboard_metrics.html         # Dashboard principal
│       ├── estudiante_changelist.html     # ✨ Lista con botón de importar
│       └── importar_estudiantes.html      # Formulario de importación
├── staticfiles/                   # Archivos estáticos recopilados
├── db.sqlite3                     # Base de datos (desarrollo)
├── manage.py                      # Comando Django
├── requirements.txt               # Dependencias Python
├── .env                          # Variables de entorno (no versionado)
├── LOGICA_NUMEROS_SIMPLIFICADA.md        # ✨ Documentación del menú
├── FLUJO_ONBOARDING_NOMBRE.md            # ✨ Documentación del onboarding
├── CORRECCIONES_REALIZADAS.md            # ✨ Últimos cambios
└── test_*.py                      # Scripts de testing
```

## ⚙️ Instalación y Configuración

### 1. Clonar el repositorio
```bash
git clone https://github.com/luxian40-lab/mvp.git
cd mvp
```

### 2. Crear y activar entorno virtual
```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Mac/Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno
Crear archivo `.env` en la raíz del proyecto basado en `.env.example`:
```env
# Django
SECRET_KEY=tu-clave-secreta-aqui
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Meta WhatsApp Cloud API
WHATSAPP_TOKEN=tu-token-de-whatsapp
WHATSAPP_PHONE_ID=tu-phone-id
WHATSAPP_API_VERSION=v19.0

# Twilio Configuration (SMS y WhatsApp)
TWILIO_ACCOUNT_SID=tu-account-sid-de-twilio
TWILIO_AUTH_TOKEN=tu-auth-token-de-twilio
TWILIO_PHONE_NUMBER=+1234567890
TWILIO_WHATSAPP_NUMBER=whatsapp:+1234567890

# Seguridad
CSRF_TRUSTED_ORIGINS=http://localhost:8000,https://tu-dominio.com
```

#### Configuración de Twilio

1. **Crear cuenta en Twilio:**
   - Ir a https://www.twilio.com/try-twilio
   - Registrarse y verificar email/teléfono

2. **Obtener credenciales:**
   - Account SID: En el dashboard principal
   - Auth Token: En el dashboard principal

3. **Configurar número SMS:**
   - Ir a Phone Numbers > Manage > Buy a number
   - Seleccionar un número con capacidad SMS
   - Copiar el número a `TWILIO_PHONE_NUMBER`

4. **Configurar WhatsApp Sandbox:**
   - Ir a Messaging > Try it out > Send a WhatsApp message
   - Seguir instrucciones para activar sandbox
   - Copiar el número sandbox a `TWILIO_WHATSAPP_NUMBER`
   - Enviar mensaje de activación desde tu WhatsApp

### 5. Ejecutar migraciones
```bash
python manage.py migrate
```

### 6. Crear superusuario
```bash
python manage.py createsuperuser
```

### 7. Recopilar archivos estáticos
```bash
python manage.py collectstatic --noinput
```

### 8. Generar plantilla de Excel (opcional)
```bash
python generate_template.py
```

### 9. Iniciar el servidor
```bash
python manage.py runserver
```

Accede a:
- **Admin:** http://127.0.0.1:8000/admin/
- **Dashboard:** http://127.0.0.1:8000/admin/dashboard/
- **API Estudiante:** http://127.0.0.1:8000/api/estudiante/{telefono}/

## 📊 Modelos de Datos

### Estudiante
- `nombre`: Nombre del estudiante
- `telefono`: Número en formato internacional (57XXXXXXXXXX)
- `activo`: Estado del estudiante
- `fecha_registro`: Fecha de alta

### Plantilla
- `nombre_interno`: Identificador de la plantilla
- `cuerpo_mensaje`: Texto del mensaje con variables
- `tiene_imagen`: Boolean para indicar si incluye imagen
- `url_imagen`: URL de la imagen a enviar

### Campaña
- `nombre`: Nombre de la campaña
- `tema`: Tema para organizar campañas (café, aguacate, maíz, etc.)
- `plantilla`: Relación con Plantilla (filtrada por tema)
- `destinatarios`: ManyToMany con Estudiantes
- `archivo_excel`: Carga masiva de destinatarios
- `canal_envio`: whatsapp (único canal soportado)
- `linea_origen`: Línea de WhatsApp a usar
- `fecha_programada`: Programación de envío
- `ejecutada`: Estado de ejecución

### EnvioLog
- `campana`: Relación con Campaña
- `estudiante`: Relación con Estudiante
- `estado`: ENVIADO, FALLIDO, PENDIENTE
- `respuesta_api`: Respuesta del servidor WhatsApp
- `fecha_envio`: Timestamp del envío

### WhatsappLog
- `telefono`: Número del remitente/destinatario
- `mensaje`: Contenido del mensaje
- `mensaje_id`: ID único de WhatsApp
- `estado`: SENT, INCOMING, PENDING, ERROR
- `fecha`: Timestamp del registro

## 🔌 API REST Endpoints

### Obtener información de estudiante
```http
GET /api/estudiante/{telefono}/
```

### Obtener progreso del estudiante
```http
GET /api/estudiante/{telefono}/progreso/
```
**Respuesta:**
```json
{
  "success": true,
  "estudiante": {
    "nombre": "Juan Pérez",
    "telefono": "573001234567"
  },
  "progreso": {
    "porcentaje": 75,
    "total_tareas": 20,
    "tareas_completadas": 15,
    "tareas_fallidas": 2,
    "modulo_actual": "Matemáticas Básicas",
    "estado": "En progreso"
  }
}
```

### Obtener siguiente tarea
```http
GET /api/estudiante/{telefono}/siguiente-tarea/
```

### Webhook WhatsApp
```http
POST /webhook/whatsapp/
```
**Validación GET:**
```http
GET /webhook/whatsapp/?hub.mode=subscribe&hub.challenge=XXXXX&hub.verify_token=XXXXX
```

## 🎨 Características del Dashboard

### Métricas Principales
- 📤 **Mensajes Entregados:** Total de envíos exitosos
- ❌ **Envíos Fallidos:** Mensajes con error
- 📢 **Campañas Creadas:** Total de campañas en el sistema
- 🎓 **Estudiantes Activos:** Usuarios activos en la plataforma

### Métricas de WhatsApp
- 💬 **Total Mensajes:** Suma de todos los mensajes
- 📤 **Mensajes Enviados:** Total de mensajes salientes
- 📥 **Mensajes Recibidos:** Total de mensajes entrantes

### Acciones Rápidas
- ➕ Nueva Campaña
- 👤 Nuevo Estudiante
- 📥 Importar Estudiantes
- 📊 Descargar Reportes
- 📋 Ver Historial

## 🔧 Funcionalidades Administrativas

### Gestión de Campañas
1. Crear campaña con nombre descriptivo
2. Seleccionar plantilla de mensaje
3. Elegir canal de envío (WhatsApp por defecto)
4. Agregar destinatarios manualmente o vía Excel
5. Programar envío o ejecutar inmediatamente
6. Monitorear resultados en tiempo real

### Importación de Estudiantes
1. Descargar plantilla Excel desde el admin
2. Rellenar datos: Nombre (columna A), Teléfono (columna B)
3. Subir archivo desde interfaz de importación
4. Sistema valida y normaliza teléfonos automáticamente
5. Confirmación de estudiantes creados/actualizados

### Descarga de Reportes
1. Seleccionar rango de fechas
2. Elegir tipo: Envíos de Campaña o Mensajes WhatsApp
3. Generar Excel con formato profesional
4. Incluye: IDs, nombres, teléfonos, estados, fechas, respuestas API

## 🧪 Pruebas

### Probar Integración con Twilio
Usa el script de pruebas incluido para verificar tu configuración:

```bash
python test_twilio.py
```

El script ofrece 3 opciones:
1. **Test SMS:** Envía un mensaje SMS de prueba
2. **Test WhatsApp:** Envía mensajes por WhatsApp (requiere sandbox activado)
3. **Ambos:** Ejecuta ambas pruebas

**Requisitos previos para WhatsApp:**
- Activar sandbox de Twilio WhatsApp
- Enviar código de activación desde tu WhatsApp
- Usar número verificado en Twilio

### Probar Meta WhatsApp
```bash
python test_whatsapp.py
```

### Probar Webhooks
```bash
python test_webhook_local.py
```

## 🚀 Despliegue

### Variables de Entorno para Producción
```env
DEBUG=False
ALLOWED_HOSTS=tu-dominio.com,www.tu-dominio.com
SECRET_KEY=clave-secreta-muy-segura-aqui
```

### Comandos de Despliegue
```bash
# Recopilar archivos estáticos
python manage.py collectstatic --noinput

# Aplicar migraciones
python manage.py migrate

# Iniciar con Gunicorn
gunicorn mvp_project.wsgi:application --bind 0.0.0.0:8000
```

## 📝 Notas de Desarrollo

### ✨ Últimas Actualizaciones (v4.0 - Enero 2026)
- ✅ **Onboarding con Nombre Personalizado** (4 pasos con captura de nombre real)
- ✅ **Menú Numérico Simplificado** (opciones 1/2/3 deterministas)
- ✅ **Normalización de Audio** (números hablados "uno" → "1")
- ✅ **Botón de Importar Profesional** (gradiente, animaciones, UX mejorada)
- ✅ **Importación con Curso** (selección de curso al importar estudiantes)
- ✅ **Cursos Profesionales** (Café Arábigo + Aguacate Hass completos)
- ✅ **Context Detection** (sistema entiende contexto de conversación)
- ✅ **Sistema de Estados** (esperando_nombre, esperando_cedula, completado)
- ✅ **Validaciones Mejoradas** (tipo documento CC/TI/CE/PP, número único)
- ✅ **Tests de Integración** (onboarding + menú numérico validados)

### Versiones Anteriores (v3.0)
- ✅ Sistema multi-agente de IA (Tutor, Frustración, Motivador, Evaluador)
- ✅ Sistema de temas para organizar plantillas y campañas
- ✅ Integración WhatsApp vía Twilio API
- ✅ Dashboard rediseñado con gradientes modernos
- ✅ Comando unificado `python manage.py eki`
- ✅ Health check completo para producción

### 🚀 Próximas Funcionalidades
- [ ] **Migración a Twilio Production** (botones interactivos en WhatsApp)
- [ ] **Deployment AWS** (RDS + S3 + App Runner)
- [ ] Sistema de exámenes y evaluaciones
- [ ] Certificados digitales de finalización
- [ ] Dashboard de analytics avanzado
- [ ] Integración con CRM externo
- [ ] API REST completa con autenticación JWT
- [ ] App móvil nativa (React Native)

## 🐛 Troubleshooting

### Error 404 en archivos estáticos
```bash
python manage.py collectstatic --noinput --clear
```

### Error en importación de Excel
- Verificar que el archivo sea .xlsx o .xls
- Asegurar que la columna A contenga nombres y columna B teléfonos
- Revisar que los teléfonos tengan formato numérico

### Problemas con WhatsApp API (Meta)
- Verificar que WHATSAPP_TOKEN esté configurado
- Confirmar que WHATSAPP_PHONE_ID sea correcto
- Revisar que la URL del webhook esté configurada en Meta

### Problemas con Twilio
- Verificar credenciales TWILIO_ACCOUNT_SID y TWILIO_AUTH_TOKEN
- Para SMS: Número verificado o cuenta premium
- Para WhatsApp: Activar sandbox primero
- Revisar formato de números: +57XXXXXXXXXX

## 📄 Licencia

Proyecto desarrollado para **Eki Platform** © 2026. Todos los derechos reservados.

## 👨‍💻 Autor

**Julian Ramirez** - Desarrollo Full Stack
- GitHub: [@luxian40-lab](https://github.com/luxian40-lab)

## 🤝 Contribuciones

Este es un proyecto privado de Eki Platform. Para consultas o colaboraciones, contactar al equipo de desarrollo.

---

**Versión:** 4.0.0  
**Última Actualización:** Enero 10, 2026  
**Estado:** ✅ Listo para Demo (Fondo Nacional de Cafeteros)  
**Cliente Principal:** Fondo Nacional de Cafeteros - Colombia ☕