# 🚀 Eki Platform - MVP Sistema de Gestión Educativa

Sistema completo de gestión y administración educativa basado en **Django** con integración de **WhatsApp Cloud API** y **Twilio**. Plataforma centralizada para la gestión de estudiantes, campañas de mensajería multi-canal, envío de notificaciones con imágenes y monitoreo en tiempo real.

## 📋 Características Principales

### 🎯 Gestión de Campañas Multi-Canal
* **Creación de Campañas:** Sistema completo para crear y ejecutar campañas de mensajería
* **Múltiples Proveedores:** Soporte para Meta WhatsApp, Twilio SMS y Twilio WhatsApp
* **Plantillas con Imágenes:** Soporte para mensajes con imágenes vía WhatsApp API
* **Envío Masivo:** Importación de estudiantes desde Excel y envío automatizado
* **Seguimiento en Tiempo Real:** Monitoreo del estado de envíos (exitosos, fallidos, pendientes)

### 📊 Dashboard de Métricas
* **Métricas en Tiempo Real:** Visualización actualizada de estadísticas clave
* **Análisis de Campañas:** Total de campañas creadas y ejecutadas
* **Estadísticas de WhatsApp:** Mensajes enviados, recibidos y estados
* **Historial de Mensajes:** Últimos 10 mensajes con detalles completos
* **Diseño Moderno:** Interfaz con gradientes y estilos personalizados

### 📱 Integración Multi-Proveedor
* **Meta WhatsApp Cloud API:** Integración completa con Meta Cloud API v19.0
* **Twilio SMS:** Envío de mensajes SMS tradicionales
* **Twilio WhatsApp:** Envío de WhatsApp vía Twilio API
* **Mensajes con Imágenes:** Envío de mensajes tipo 'image' con caption en ambos proveedores
* **Webhook Configurado:** Recepción de mensajes entrantes y notificaciones
* **Detección de Intenciones:** Sistema inteligente de respuestas automáticas
* **Logs Detallados:** Registro completo de todos los mensajes

### 👥 Gestión de Estudiantes
* **CRUD Completo:** Alta, baja y modificación de estudiantes
* **Importación Masiva:** Carga de estudiantes desde archivos Excel
* **Validación de Teléfonos:** Normalización automática a formato internacional
* **Filtros y Búsqueda:** Sistema de búsqueda avanzada en el admin
* **Exportación de Reportes:** Descarga de datos en formato Excel

### 📧 Sistema de Plantillas
* **Editor de Mensajes:** Creación de plantillas personalizables
* **Soporte de Variables:** Personalización con {nombre} y otros campos
* **Gestión de Imágenes:** Campo URL para imágenes en mensajes
* **Vista Previa:** Previsualización de plantillas antes de enviar
* **Reutilización:** Uso de plantillas en múltiples campañas

## 🛠️ Tecnologías

* **Backend:** Python 3.11+ / Django 5.2.9
* **Base de Datos:** SQLite (desarrollo) / PostgreSQL (producción)
* **Admin Interface:** Django Jazzmin 3.0.1
* **API Integration:** 
  - WhatsApp Cloud API v19.0 (Meta)
  - Twilio API v8.0+ (SMS y WhatsApp)
* **Excel Processing:** OpenPyXL 3.1.5
* **HTTP Client:** Requests 2.32+
* **Frontend:** Django Templates + CSS Custom + Bootstrap

## 📁 Estructura del Proyecto

```
eki_mvp/
├── core/                          # Aplicación principal
│   ├── models.py                  # Modelos: Estudiante, Plantilla, Campaña, EnvioLog, WhatsappLog
│   ├── admin.py                   # Configuración del admin de Django
│   ├── views.py                   # Vistas del dashboard y reportes
│   ├── api.py                     # Endpoints REST para progreso
│   ├── services.py                # Lógica de negocio y envío de campañas
│   ├── utils.py                   # Utilidades (envío WhatsApp)
│   ├── intent_detector.py         # Detección de intenciones en mensajes
│   ├── response_templates.py      # Templates de respuestas automáticas
│   └── migrations/                # Migraciones de base de datos
├── mvp_project/                   # Configuración del proyecto
│   ├── settings.py                # Configuración general
│   ├── urls.py                    # Rutas principales
│   └── wsgi.py                    # Configuración WSGI
├── templates/                     # Plantillas HTML
│   └── admin/
│       ├── dashboard_metrics.html # Dashboard principal
│       ├── importar_estudiantes.html
│       └── descargar_reportes.html
├── staticfiles/                   # Archivos estáticos recopilados
├── db.sqlite3                     # Base de datos (desarrollo)
├── manage.py                      # Comando Django
├── requirements.txt               # Dependencias Python
└── .env                          # Variables de entorno (no versionado)
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
- `plantilla`: Relación con Plantilla
- `destinatarios`: ManyToMany con Estudiantes
- `archivo_excel`: Carga masiva de destinatarios
- `canal_envio`: whatsapp, sms, email, voz
- `proveedor`: meta, twilio_sms, twilio_whatsapp
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

### Últimas Actualizaciones (v2.1)
- ✅ Integración multi-proveedor (Meta y Twilio)
- ✅ Soporte para SMS vía Twilio
- ✅ Soporte para WhatsApp vía Twilio API
- ✅ Selector de proveedor en campañas
- ✅ Funciones de envío unificadas en utils.py
- ✅ Script de pruebas para Twilio
- ✅ Documentación actualizada con configuración Twilio
- ✅ Soporte completo de imágenes en plantillas WhatsApp
- ✅ Dashboard rediseñado con gradientes modernos
- ✅ Reconfiguración de archivos estáticos (STATICFILES_DIRS)
- ✅ URLs optimizadas para evitar conflictos con admin
- ✅ PlantillaAdmin con vista previa de imágenes
- ✅ Mejoras en UX de botones de acción
- ✅ Integración completa con WhatsApp Cloud API
- ✅ Sistema de logs mejorado

### Próximas Funcionalidades
- [ ] Programación automática de campañas
- [ ] Reportes con gráficos y estadísticas avanzadas
- [ ] Respuestas automáticas basadas en IA
- [ ] Integración con Email
- [ ] Sistema de roles y permisos
- [ ] API REST completa con autenticación
- [ ] Dashboard de análisis de conversaciones
- [ ] Integración con CRM externo

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

Proyecto desarrollado para **Eki Platform** © 2025. Todos los derechos reservados.

## 👨‍💻 Autor

**Julian Ramirez** - Desarrollo Full Stack
- GitHub: [@luxian40-lab](https://github.com/luxian40-lab)

## 🤝 Contribuciones

Este es un proyecto privado de Eki Platform. Para consultas o colaboraciones, contactar al equipo de desarrollo.

---

**Versión:** 2.1.0  
**Última Actualización:** Diciembre 2025  
**Estado:** ✅ En Producción