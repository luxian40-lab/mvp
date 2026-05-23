from pathlib import Path
import os
from dotenv import load_dotenv

# 1. RUTAS DEL PROYECTO
BASE_DIR = Path(__file__).resolve().parent.parent
# Cargar .env si existe (tanto local como produccion)
env_file = BASE_DIR / '.env'
if env_file.exists():
    load_dotenv(env_file)

# 2. SEGURIDAD
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-mvp-clave-secreta-cambiar-en-produccion')
DEBUG = os.environ.get('DJANGO_DEBUG', 'True') == 'True'  # False en producción

# ALLOWED_HOSTS: acepta múltiples dominios separados por coma
# testserver: httpx de pytest-django / django.test Client
allowed_hosts_str = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1,testserver,eki-mvp.onrender.com,eki-prod-docker.eba-84g5zn3s.us-east-2.elasticbeanstalk.com')
ALLOWED_HOSTS = [host.strip() for host in allowed_hosts_str.split(',')]
# Permitir todos los dominios de ngrok
ALLOWED_HOSTS.append('.ngrok-free.dev')
ALLOWED_HOSTS.append('.ngrok.io')

# CONFIGURACION DE SEGURIDAD PARA PRODUCCION
if not DEBUG:
    # HTTPS y seguridad
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000  # 1 año
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    
    # Seguridad adicional
    X_FRAME_OPTIONS = 'DENY'
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True

# 3. APLICACIONES INSTALADAS
INSTALLED_APPS = [
    'jazzmin',                  # <--- IMPORTANTE: JAZZMIN SIEMPRE DE PRIMERO
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'storages',                 # <--- AWS S3 para almacenar audios
    'core',                     # <--- Orquestador + modelos compartidos
    'formulario',               # GEI / encuestas
    'learning',                 # Bounded context educación (migración gradual)
    'agents_edu',               # Darío, Claudia, tutor
    'agents_commercial',        # Nati, RAG comercial
    'analytics',                # Dashboards, métricas, Excel
    'integrations',             # API LXP / Angular
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Para servir archivos estáticos en producción
    'core.middleware.RequestContextMiddleware',  # request_id y latencia básica
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'core.middleware.RateLimitMiddleware',  # 🔒 Rate limiting
    'core.middleware.CertificadoAccessMiddleware',  # 🔐 Auditoría de acceso a certificados
]

ROOT_URLCONF = 'mvp_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        # 👇 CAMBIO 1: Agregamos la ruta de templates para que encuentre el HTML del dashboard
        'DIRS': [BASE_DIR / 'templates'], 
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'mvp_project.wsgi.application'

# 4. BASE DE DATOS
import os

# Prioridad: variables individuales DB_* → DATABASE_URL → SQLite
if (
    os.environ.get('DB_NAME')
    and os.environ.get('DB_USER')
    and os.environ.get('DB_PASSWORD')
    and os.environ.get('DB_HOST')
):
    print('[OK] MODO PRODUCCION DETECTADO: Conectando a PostgreSQL (DB_* vars)...')
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ['DB_NAME'],
            'USER': os.environ['DB_USER'],
            'PASSWORD': os.environ['DB_PASSWORD'],
            'HOST': os.environ['DB_HOST'],
            'PORT': os.environ.get('DB_PORT', '5432'),
        }
    }
elif os.environ.get('DATABASE_URL'):
    # Parsear DATABASE_URL (formato: postgresql://user:pass@host:port/dbname)
    import urllib.parse
    db_url = os.environ['DATABASE_URL']
    try:
        parsed = urllib.parse.urlparse(db_url)
        print(f'[OK] PostgreSQL via DATABASE_URL: {parsed.hostname}/{parsed.path.lstrip("/")}')
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': parsed.path.lstrip('/'),
                'USER': parsed.username or '',
                'PASSWORD': parsed.password or '',
                'HOST': parsed.hostname or 'localhost',
                'PORT': str(parsed.port or 5432),
                'OPTIONS': {
                    'connect_timeout': 5,
                },
            }
        }
        # Verificar conexion real; si falla (ej. local sin acceso a RDS), usar SQLite
        # Solo verificar si NO estamos en EB (variable ELASTIC_BEANSTALK indica EB)
        if not os.environ.get('ELASTIC_BEANSTALK'):
            try:
                import psycopg
                conn = psycopg.connect(
                    host=parsed.hostname,
                    port=parsed.port or 5432,
                    user=parsed.username,
                    password=parsed.password,
                    dbname=parsed.path.lstrip('/'),
                    connect_timeout=3,
                )
                conn.close()
                print('[OK] Conexion PostgreSQL verificada.')
            except Exception as conn_err:
                print(f'[WARN] PostgreSQL no accesible localmente ({conn_err}). Usando SQLite.')
                DATABASES = {
                    'default': {
                        'ENGINE': 'django.db.backends.sqlite3',
                        'NAME': BASE_DIR / 'db.sqlite3',
                    }
                }
    except Exception as e:
        print(f'[WARN] Error parseando DATABASE_URL: {e}. Usando SQLite.')
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': BASE_DIR / 'db.sqlite3',
            }
        }
else:
    print('[WARN] MODO LOCAL DETECTADO: Usando SQLite.')
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Reusar conexiones DB para reducir overhead en webhooks concurrentes.
if DATABASES.get('default', {}).get('ENGINE') == 'django.db.backends.postgresql':
    DATABASES['default']['CONN_MAX_AGE'] = int(os.environ.get('DB_CONN_MAX_AGE', '60') or '60')

# 5. VALIDACIÓN DE CONTRASEÑAS
AUTH_PASSWORD_VALIDATORS = [
    { 'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator', },
    { 'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', },
    { 'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator', },
    { 'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator', },
]

# 6. IDIOMA Y ZONA HORARIA (Colombia)
LANGUAGE_CODE = 'es-co'
TIME_ZONE = 'America/Bogota'
USE_I18N = True
USE_TZ = True

# 7. ARCHIVOS ESTÁTICOS
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]
# WhiteNoise para servir archivos estáticos en producción
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Middlewares de seguridad para producción
csrf_origins_str = os.environ.get('CSRF_TRUSTED_ORIGINS', 'http://localhost:8000,https://eki-mvp.onrender.com')
CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in csrf_origins_str.split(',')]

# Configuración para producción
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
CSRF_TRUSTED_ORIGINS = os.environ.get('CSRF_TRUSTED_ORIGINS', 'http://localhost:8000').split(',')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ==========================================
# 🎨 8. CONFIGURACIÓN VISUAL JAZZMIN
# ==========================================

JAZZMIN_SETTINGS = {
    # Títulos y Marca
    "site_title": "eki",
    "site_header": "eki",
    "site_brand": "eki",
    "welcome_sign": "Bienvenido a eki",
    "copyright": "eki solutions",
    "search_model": ["core.Estudiante", "core.Campana", "agents_commercial.ProspectoB2B"],

    # Menú Superior - Acceso rápido
    "topmenu_links": [
        {"name": "Dashboard", "url": "/admin/dashboard/", "new_window": False},
        {"name": "Conversaciones", "url": "conversaciones", "new_window": False},
    ],

    # Menú Lateral
    "show_sidebar": True,
    "navigation_expanded": False,  # Colapsado por defecto

    # CSS Personalizado
    "custom_css": "admin/css/custom_menu.css",

    # Iconos — agrupados por sección visual
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user-shield",
        "auth.Group": "fas fa-users-cog",

        # Core — estudiantes, cursos, campañas, progreso
        "core": "fas fa-home",
        "core.Cliente": "fas fa-building",
        "core.Estudiante": "fas fa-user-circle",
        "core.GrupoEstudiantes": "fas fa-users",
        "core.Curso": "fas fa-book-open",
        "core.Modulo": "fas fa-layer-group",
        "core.ProgresoEstudiante": "fas fa-chart-line",
        "core.Campana": "fas fa-bullhorn",
        "core.MensajePush": "fas fa-paper-plane",
        "core.Plantilla": "fas fa-envelope-open-text",
        "core.WhatsappLog": "fas fa-comments",
        "core.TemaCampana": "fas fa-tags",
        "core.EnvioLog": "fas fa-paper-plane",
        "core.SolicitudSoporte": "fas fa-hands-helping",
        "core.Linea": "fas fa-phone-alt",
        "core.ConfiguracionGlobal": "fas fa-cog",

        # IA Comercial
        "agents_commercial": "fas fa-robot",
        "agents_commercial.ProspectoB2B": "fas fa-handshake",
        "agents_commercial.CampanaB2B": "fas fa-bullhorn",
        "agents_commercial.DocumentoRAGComercial": "fas fa-file-contract",
        "agents_commercial.MetaMetricaNati": "fas fa-bullseye",
        "agents_commercial.ContextoAgroSession": "fas fa-seedling",
        "agents_commercial.ConversacionRAGCandidata": "fas fa-lightbulb",

        # Métricas
        "analytics": "fas fa-chart-bar",
        "analytics.MetaMetricaEmpresa": "fas fa-bullseye",
        "analytics.EventoIA": "fas fa-microchip",

        # IA Educativa
        "agents_edu": "fas fa-graduation-cap",
        "agents_edu.DocumentoRAG": "fas fa-file-alt",

        # Evaluación y gamificación
        "learning": "fas fa-trophy",
        "learning.Examen": "fas fa-clipboard-check",
        "learning.PreguntaExamen": "fas fa-question-circle",
        "learning.PerfilGamificacion": "fas fa-trophy",
        "learning.Badge": "fas fa-medal",
        "learning.Recompensa": "fas fa-gift",
        "learning.CanjeRecompensa": "fas fa-shopping-cart",
        "learning.Certificado": "fas fa-certificate",
        "learning.PlantillaCertificado": "fas fa-file-pdf",
        "learning.AliadoEmpleabilidad": "fas fa-briefcase",
        "learning.MisionEmpleabilidad": "fas fa-map-marker-alt",
        "learning.AuditLog": "fas fa-lock",

        # Formulario GEI
        "formulario.FichaGEI": "fas fa-seedling",
        "formulario.ResultadoGEI": "fas fa-calculator",
        "formulario.TipoFormulario": "fas fa-wpforms",
        "formulario.SesionFormulario": "fas fa-tasks",
    },

    # Links custom (acceso rápido a vistas no-modelo)
    "custom_links": {
        "formulario": [
            {
                "name": "📊 Panel GEI",
                "url": "/admin/gei/panel/",
                "icon": "fas fa-leaf",
                "permissions": ["formulario.view_fichagei"],
            },
        ],
        "core": [
            {
                "name": "📋 Manual / Instrucciones",
                "url": "/admin/instrucciones/",
                "icon": "fas fa-book",
                "permissions": ["core.view_estudiante"],
            },
        ],
        "agents_commercial": [
            {
                "name": "🤖 Panel bot comercial",
                "url": "/admin/bot-comercial/",
                "icon": "fas fa-comments",
                "permissions": ["core.view_prospectob2b"],
            },
            {
                "name": "💡 Knowledge Studio",
                "url": "/admin/knowledge-studio/",
                "icon": "fas fa-lightbulb",
                "permissions": ["core.view_conversacionragcandidata"],
            },
        ],
        "analytics": [
            {
                "name": "📈 Dashboard métricas",
                "url": "/admin/dashboard/",
                "icon": "fas fa-tachometer-alt",
                "permissions": ["core.view_estudiante"],
            },
            {
                "name": "🔬 AI Ops (eventos IA)",
                "url": "/admin/ai-ops/eventos/",
                "icon": "fas fa-microchip",
                "permissions": ["core.view_eventoia"],
            },
        ],
        "agents_edu": [
            {
                "name": "✨ Crear curso con IA",
                "url": "/admin/crear-curso-ia/",
                "icon": "fas fa-magic",
                "permissions": ["core.view_curso"],
            },
        ],
    },

    # Ocultar modelos automáticos / de sólo-código
    "hide_models": [
        "core.ModuloCompletado",
        "learning.BadgeEstudiante",
        "learning.TransaccionPuntos",
        "core.EnvioLog",
        "learning.ResultadoExamen",
        "core.GrupoWhatsApp",
        "core.InvitacionGrupo",
        "core.PreguntaModulo",
        "core.CampanaUnica",
        "core.RespuestaCampanaUnica",
        "core.EnvioProgramado",
        "learning.PQRS",
        "learning.RespuestaAbiertaFinal",
        "learning.PreguntaAbiertaFinalCurso",
    ],

    # Orden visual del sidebar — agrupado en 6 secciones lógicas
    "order_with_respect_to": [
        "auth",
        # Core — núcleo operativo
        "core",
        "core.Cliente",
        "core.Estudiante",
        "core.GrupoEstudiantes",
        "core.Curso",
        "core.Modulo",
        "core.ProgresoEstudiante",
        "core.Campana",
        "core.Plantilla",
        "core.TemaCampana",
        "core.WhatsappLog",
        "core.SolicitudSoporte",
        "core.Linea",
        "core.ConfiguracionGlobal",
        # IA Comercial
        "agents_commercial",
        "agents_commercial.ProspectoB2B",
        "agents_commercial.CampanaB2B",
        "agents_commercial.DocumentoRAGComercial",
        "agents_commercial.ConversacionRAGCandidata",
        "agents_commercial.ContextoAgroSession",
        "agents_commercial.MetaMetricaNati",
        # Métricas
        "analytics",
        "analytics.MetaMetricaEmpresa",
        "analytics.EventoIA",
        # IA Educativa
        "agents_edu",
        "agents_edu.DocumentoRAG",
        # Evaluación y gamificación
        "learning",
        "learning.Examen",
        "learning.PreguntaExamen",
        "learning.PerfilGamificacion",
        "learning.Badge",
        "learning.Recompensa",
        "learning.CanjeRecompensa",
        "learning.Certificado",
        "learning.PlantillaCertificado",
        "learning.AliadoEmpleabilidad",
        "learning.MisionEmpleabilidad",
        "learning.AuditLog",
        # Formulario GEI
        "formulario",
        "formulario.TipoFormulario",
        "formulario.FichaGEI",
        "formulario.ResultadoGEI",
        "formulario.SesionFormulario",
    ],

    # Usar verbose names en español
    "show_ui_builder": False,

    # Desactivar related_modal para mejor rendimiento
    "related_modal_active": False,
}

JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": False,
    "footer_small_text": False,
    "body_small_text": False,
    "brand_small_text": False,
    "brand_colour": "navbar-primary",
    "accent": "accent-primary",
    "navbar": "navbar-white navbar-light",
    "no_navbar_border": False,
    "navbar_fixed": False,
    "layout_boxed": False,
    "footer_fixed": False,
    "sidebar_fixed": False,  # Cambio: Deshabilitado para permitir scroll natural
    "sidebar": "sidebar-dark-primary",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": False,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": True,
    
    # TEMA PRINCIPAL
    "theme": "flatly",
    "dark_mode_theme": None,
    "button_classes": {
        "primary": "btn-primary",
        "secondary": "btn-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success"
    }
}

# ==========================================
# 🔌 CREDENCIALES WHATSAPP CLOUD API (META)
# ==========================================
WHATSAPP_API_VERSION = os.environ.get('WHATSAPP_API_VERSION', 'v19.0')
WHATSAPP_TOKEN = os.environ.get('WHATSAPP_TOKEN', '')  # Access Token de Meta
WHATSAPP_PHONE_ID = os.environ.get('WHATSAPP_PHONE_ID', '')  # Phone Number ID
WHATSAPP_BUSINESS_ACCOUNT_ID = os.environ.get('WHATSAPP_BUSINESS_ACCOUNT_ID', '')  # WABA ID para crear templates

# ==========================================
# 📱 CREDENCIALES TWILIO
# ==========================================
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER')
TWILIO_WHATSAPP_NUMBER = os.environ.get('TWILIO_WHATSAPP_NUMBER')
WHATSAPP_VERIFY_TOKEN = os.environ.get('WHATSAPP_VERIFY_TOKEN', 'eki_webhook_verify_token')
# URL completa POST para callbacks de estado (delivered/read/failed). Ej: https://tudominio.com/webhook/whatsapp/
TWILIO_STATUS_CALLBACK_URL = os.environ.get('TWILIO_STATUS_CALLBACK_URL', '').strip()

# 📢 Templates de Twilio para envío masivo (deben estar aprobados)
TWILIO_TEMPLATE_ANUNCIO_GRUPAL = os.environ.get('TWILIO_TEMPLATE_ANUNCIO_GRUPAL', '')  # Content SID del template de anuncios
TWILIO_TEMPLATE_INVITACION_GRUPO = os.environ.get('TWILIO_TEMPLATE_INVITACION_GRUPO', '')  # Content SID del template de invitación
# Content SID (HSM) para recordatorio cuando se desbloquea un módulo con drip. Vacío = mensaje de texto en sesión.
# Requiere Celery Beat con la tarea reenganche_drip_content_diario (ver mvp_project/celery.py, 8:00).
TWILIO_TEMPLATE_DRIP_REENGANCHE = os.environ.get('TWILIO_TEMPLATE_DRIP_REENGANCHE', '')

# ==========================================
# 🤖 OPENAI API
# ==========================================
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')

# ==========================================
# 🌾 BOT COMERCIAL IA (Nodo Comercial)
# ==========================================
BOT_COMERCIAL_CLIENTE_ID = os.environ.get('BOT_COMERCIAL_CLIENTE_ID', '0')
BOT_COMERCIAL_CURSO_ID = os.environ.get('BOT_COMERCIAL_CURSO_ID', '0')
BOT_COMERCIAL_WHATSAPP_NUMBER = os.environ.get('BOT_COMERCIAL_WHATSAPP_NUMBER', '')
BOT_COMERCIAL_RAG_CANAL = os.environ.get('BOT_COMERCIAL_RAG_CANAL', 'bot_comercial')
BOT_COMERCIAL_OPENAI_MODEL = os.environ.get('BOT_COMERCIAL_OPENAI_MODEL', 'gpt-5-mini')
BOT_COMERCIAL_MODEL_TECNICO = os.environ.get('BOT_COMERCIAL_MODEL_TECNICO', 'gpt-5')
BOT_COMERCIAL_MODEL_ROUTER = os.environ.get('BOT_COMERCIAL_MODEL_ROUTER', 'gpt-5-nano')
BOT_COMERCIAL_ROUTER_USE_NANO = os.environ.get('BOT_COMERCIAL_ROUTER_USE_NANO', 'true').strip().lower() in (
    '1', 'true', 'yes', 'on',
)
try:
    BOT_COMERCIAL_RAG_MIN_SIMILARITY = float(os.environ.get('BOT_COMERCIAL_RAG_MIN_SIMILARITY', '0.52'))
except (TypeError, ValueError):
    BOT_COMERCIAL_RAG_MIN_SIMILARITY = 0.52
BOT_COMERCIAL_VISION_MODEL = os.environ.get('BOT_COMERCIAL_VISION_MODEL', 'gpt-5-mini')
# Límite de tokens de salida del chat (menor = respuesta más rápida y barata).
try:
    BOT_COMERCIAL_OPENAI_MAX_TOKENS = int(os.environ.get('BOT_COMERCIAL_OPENAI_MAX_TOKENS', '650'))
except (TypeError, ValueError):
    BOT_COMERCIAL_OPENAI_MAX_TOKENS = 650
# Cuánto texto RAG inyectar al prompt del bot comercial (menor = menos latencia).
try:
    BOT_COMERCIAL_RAG_TOP_K = int(os.environ.get('BOT_COMERCIAL_RAG_TOP_K', '9'))
except (TypeError, ValueError):
    BOT_COMERCIAL_RAG_TOP_K = 9
BOT_COMERCIAL_RAG_TOP_K = max(3, min(BOT_COMERCIAL_RAG_TOP_K, 20))
try:
    BOT_COMERCIAL_RAG_MAX_CHARS = int(os.environ.get('BOT_COMERCIAL_RAG_MAX_CHARS', '2500'))
except (TypeError, ValueError):
    BOT_COMERCIAL_RAG_MAX_CHARS = 2500
BOT_COMERCIAL_RAG_MAX_CHARS = max(400, min(BOT_COMERCIAL_RAG_MAX_CHARS, 4000))
# Fallback leyendo Excel/PDF en webhook; con t3.medium defaults más altos (bajar vía env si hace falta).
BOT_COMERCIAL_RAG_FILE_FALLBACK = os.environ.get('BOT_COMERCIAL_RAG_FILE_FALLBACK', 'true').strip().lower() in (
    '1', 'true', 'yes', 'on',
)
try:
    BOT_COMERCIAL_RAG_FALLBACK_MAX_DOCS = int(os.environ.get('BOT_COMERCIAL_RAG_FALLBACK_MAX_DOCS', '4'))
except (TypeError, ValueError):
    BOT_COMERCIAL_RAG_FALLBACK_MAX_DOCS = 4
BOT_COMERCIAL_RAG_FALLBACK_MAX_DOCS = max(1, min(BOT_COMERCIAL_RAG_FALLBACK_MAX_DOCS, 12))
try:
    BOT_COMERCIAL_RAG_FALLBACK_XLSX_ROWS = int(os.environ.get('BOT_COMERCIAL_RAG_FALLBACK_XLSX_ROWS', '2000'))
except (TypeError, ValueError):
    BOT_COMERCIAL_RAG_FALLBACK_XLSX_ROWS = 2000
BOT_COMERCIAL_RAG_FALLBACK_XLSX_ROWS = max(120, min(BOT_COMERCIAL_RAG_FALLBACK_XLSX_ROWS, 8000))
# Modelo para búsqueda web (Responses API).
BOT_COMERCIAL_WEB_SEARCH_MODEL = os.environ.get('BOT_COMERCIAL_WEB_SEARCH_MODEL', 'gpt-5-mini').strip()
BOT_COMERCIAL_FORCE_ROUTING = os.environ.get('BOT_COMERCIAL_FORCE_ROUTING', 'false').strip().lower() in ['1', 'true', 'yes', 'on']
BOT_COMERCIAL_WEB_FALLBACK_ENABLED = os.environ.get('BOT_COMERCIAL_WEB_FALLBACK_ENABLED', 'true').strip().lower() in ['1', 'true', 'yes', 'on']
try:
    BOT_COMERCIAL_WEB_FALLBACK_TIMEOUT = float(os.environ.get('BOT_COMERCIAL_WEB_FALLBACK_TIMEOUT', '6'))
except (TypeError, ValueError):
    BOT_COMERCIAL_WEB_FALLBACK_TIMEOUT = 6.0
try:
    BOT_COMERCIAL_WEB_FALLBACK_MAX_FUENTES = int(os.environ.get('BOT_COMERCIAL_WEB_FALLBACK_MAX_FUENTES', '4'))
except (TypeError, ValueError):
    BOT_COMERCIAL_WEB_FALLBACK_MAX_FUENTES = 4

# Memoria conversacional (WhatsappLog BOT_COMERCIAL): más turnos/chars = menos “amnesia”.
try:
    BOT_COMERCIAL_MEMORY_TURNOS = int(os.environ.get('BOT_COMERCIAL_MEMORY_TURNOS', '12'))
except (TypeError, ValueError):
    BOT_COMERCIAL_MEMORY_TURNOS = 12
try:
    BOT_COMERCIAL_MEMORY_MAX_CHARS = int(os.environ.get('BOT_COMERCIAL_MEMORY_MAX_CHARS', '3600'))
except (TypeError, ValueError):
    BOT_COMERCIAL_MEMORY_MAX_CHARS = 3600
# Texto extra para el system prompt (sin romper RAG-first); multilínea vía env.
BOT_COMERCIAL_SYSTEM_PROMPT_EXTRA = os.environ.get('BOT_COMERCIAL_SYSTEM_PROMPT_EXTRA', '').strip()

# ==========================================
# 📜 Certificados — URL pública del QR (landing Netlify)
# ==========================================
CERTIFICADO_VERIFICACION_BASE_URL = os.environ.get(
    'CERTIFICADO_VERIFICACION_BASE_URL',
    'https://certificadosseki.netlify.app',
).strip().rstrip('/')
# CORS: origen permitido para llamadas desde la landing al API de verificación.
CERT_VERIFICATION_ALLOWED_ORIGIN = os.environ.get(
    'CERT_VERIFICATION_ALLOWED_ORIGIN',
    CERTIFICADO_VERIFICACION_BASE_URL,
).strip().rstrip('/')

# ==========================================
# 🌱 AGRO NEXO IA (Segundo número / webhook)
# ==========================================
AGRONEXO_CLIENTE_ID = os.environ.get('AGRONEXO_CLIENTE_ID', BOT_COMERCIAL_CLIENTE_ID)
AGRONEXO_CURSO_ID = os.environ.get('AGRONEXO_CURSO_ID', BOT_COMERCIAL_CURSO_ID)
AGRONEXO_WHATSAPP_NUMBER = os.environ.get('AGRONEXO_WHATSAPP_NUMBER', BOT_COMERCIAL_WHATSAPP_NUMBER)
AGRONEXO_RAG_CANAL = os.environ.get('AGRONEXO_RAG_CANAL', 'agro_nexo')
AGRONEXO_OPENAI_MODEL = os.environ.get('AGRONEXO_OPENAI_MODEL', BOT_COMERCIAL_OPENAI_MODEL)
AGRONEXO_VISION_MODEL = os.environ.get('AGRONEXO_VISION_MODEL', BOT_COMERCIAL_VISION_MODEL)

# ==========================================
# 🔐 API INTEGRACION (ANGULAR / LXP)
# ==========================================
INTEGRACION_API_KEY = os.environ.get('INTEGRACION_API_KEY', '')
INTEGRACION_API_ALLOWED_ORIGINS = os.environ.get('INTEGRACION_API_ALLOWED_ORIGINS', '*')
try:
    INTEGRACION_API_MAX_DIAS = int(os.environ.get('INTEGRACION_API_MAX_DIAS', '31'))
except (TypeError, ValueError):
    INTEGRACION_API_MAX_DIAS = 31

# ==========================================
# 🤖 GOOGLE GEMINI API
# ==========================================
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

# ==========================================
# 🤖 COHERE AI API (100 llamadas/min gratis)
# ==========================================
COHERE_API_KEY = os.environ.get('COHERE_API_KEY')

# ==========================================
# 🎤 VOSK - TRANSCRIPCIÓN DE AUDIO (GRATIS)
# ==========================================
# Modelo de reconocimiento de voz offline completamente gratuito
# Descargar modelo: python setup_vosk.py
VOSK_MODEL_PATH = os.path.join(BASE_DIR, 'models', 'vosk-model-small-es-0.42')

# ==========================================
# 📁 ARCHIVOS MULTIMEDIA (Audios de WhatsApp)
# ==========================================
# En desarrollo local: usa carpeta media/
# En producción: usa AWS S3 para persistencia

# AUTO-DETECCION DE PRODUCCION
import sys
import logging
logger = logging.getLogger(__name__)

if os.environ.get('DJANGO_SETTINGS_MODULE', '').endswith('settings_production'):
    sys.stderr.write("[PRODUCCION DETECTADA - FORZANDO S3]\n")
    USE_S3 = True
else:
    USE_S3 = os.environ.get('USE_S3', 'False') == 'True'

sys.stderr.write(f"[USE_S3 = {USE_S3}]\n")

if USE_S3:
    # ☁️ AWS S3 Configuration
    # Usar IAM Instance Profile en lugar de credenciales hardcodeadas (más seguro)
    # Si hay credenciales en variables de entorno, las usa; sino usa el rol de EC2
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID', None)
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY', None)
    
    AWS_STORAGE_BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME')
    AWS_S3_REGION_NAME = os.environ.get('AWS_S3_REGION_NAME', 'us-east-2')
    AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com'
    
    # Configuración de archivos multimedia en S3
    DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
    MEDIA_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/media/'
    
    # Configuración de seguridad S3
    # 🎬 MULTIMEDIA PÚBLICO: Videos/imágenes deben ser accesibles por WhatsApp
    AWS_DEFAULT_ACL = 'public-read'  # Hacer archivos públicos automáticamente
    AWS_S3_OBJECT_PARAMETERS = {
        'CacheControl': 'max-age=86400',
    }
    AWS_QUERYSTRING_AUTH = False  # URLs públicas sin firma (necesario para WhatsApp)
    AWS_S3_FILE_OVERWRITE = False  # No sobreescribir archivos
    
    # Debug logging MEJORADO
    sys.stderr.write("\n" + "="*70 + "\n")
    sys.stderr.write("[S3 CONFIGURACION APLICADA]\n")
    sys.stderr.write(f"[BUCKET] {AWS_STORAGE_BUCKET_NAME}\n")
    sys.stderr.write(f"[REGION] {AWS_S3_REGION_NAME}\n")
    sys.stderr.write(f"[ACCESS_KEY] {AWS_ACCESS_KEY_ID[:10] if AWS_ACCESS_KEY_ID else 'NOT SET'}...\n")
    sys.stderr.write(f"[DEFAULT_FILE_STORAGE] {DEFAULT_FILE_STORAGE}\n")
    sys.stderr.write(f"[MEDIA_URL] {MEDIA_URL}\n")
    
    # Verificar si storages está disponible
    try:
        import storages
        sys.stderr.write(f"[DJANGO-STORAGES] Instalado correctamente v{storages.__version__}\n")
    except ImportError as e:
        sys.stderr.write(f"[ERROR] django-storages NO INSTALADO: {e}\n")
    
    # Verificar si boto3 está disponible
    try:
        import boto3
        sys.stderr.write(f"[BOTO3] Instalado correctamente v{boto3.__version__}\n")
    except ImportError as e:
        sys.stderr.write(f"[ERROR] boto3 NO INSTALADO: {e}\n")
    
    sys.stderr.write("="*70 + "\n\n")

else:
    # 📂 Desarrollo local: almacenamiento en carpeta media/
    MEDIA_ROOT = BASE_DIR / 'media'
    MEDIA_URL = '/media/'

# ========================================
# 🔒 CONFIGURACIÓN DE RATE LIMITING
# ========================================
RATE_LIMIT_ENABLED = True  # Habilitar rate limiting
RATE_LIMIT_REQUESTS = 100  # Máximo de requests por IP
RATE_LIMIT_PERIOD = 60  # Período en segundos

# WhatsApp rate limiting
WHATSAPP_RATE_LIMIT = 5  # Máximo de mensajes por teléfono
WHATSAPP_RATE_PERIOD = 60  # Período en segundos

# Paths excluidos de rate limiting
RATE_LIMIT_EXCLUDE_PATHS = [
    '/admin/',
    '/static/',
    '/media/',
    '/health/',
    '/healthz/',
]

# ==========================================
# 📧 CONFIGURACIÓN DE EMAIL - GMAIL
# ==========================================
"""
CONFIGURACIÓN GMAIL:

1. Ve a tu cuenta de Google: https://myaccount.google.com/
2. Seguridad > Verificación en 2 pasos (actívala si no está)
3. Seguridad > Contraseñas de aplicaciones
4. Genera una contraseña para "Correo" y "Otro (Django)"
5. Usa esa contraseña de 16 caracteres (sin espacios)

Variables de entorno necesarias:
- EMAIL_HOST_USER=tu_email@gmail.com
- EMAIL_HOST_PASSWORD=xxxx xxxx xxxx xxxx (contraseña de aplicación)
- DEFAULT_FROM_EMAIL=tu_email@gmail.com (o el nombre que quieras mostrar)
"""

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
            'stream': 'ext://sys.stdout',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER or 'noreply@eki.com')

# Configuración adicional de Gmail
EMAIL_USE_SSL = False  # Gmail usa TLS en puerto 587
EMAIL_TIMEOUT = 30  # Timeout de 30 segundos

# En desarrollo sin configurar, usar consola
if DEBUG and not EMAIL_HOST_USER:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# ==========================================
# CELERY - Procesamiento asíncrono
# ==========================================
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE  # Usa la misma zona horaria de Django
CELERY_TASK_TRACK_STARTED = True
# Indexación RAG / XLSX puede superar 5 min; override por env en EB si hace falta.
CELERY_TASK_TIME_LIMIT = int(os.environ.get('CELERY_TASK_TIME_LIMIT', '3600'))
CELERY_TASK_SOFT_TIME_LIMIT = int(os.environ.get('CELERY_TASK_SOFT_TIME_LIMIT', '3300'))
CELERY_WORKER_PREFETCH_MULTIPLIER = 1  # Para distribución justa de tareas
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# En desarrollo sin Redis, deshabilitar Celery (las tareas se ejecutan síncronamente)
CELERY_TASK_ALWAYS_EAGER = os.environ.get('CELERY_TASK_ALWAYS_EAGER', 'False') == 'True'
CELERY_TASK_EAGER_PROPAGATES = True

# Formulario GEI — envío automático del balance por WhatsApp al completar un módulo del curso
GEI_MODULO_NUMERO_WHATSAPP_RESULTADO = int(os.environ.get('GEI_MODULO_NUMERO_WHATSAPP_RESULTADO', '5') or '5')
GEI_RESULTADO_WHATSAPP_ENABLED = os.environ.get('GEI_RESULTADO_WHATSAPP_ENABLED', 'true').lower() in (
    '1', 'true', 'yes', 'on',
)
