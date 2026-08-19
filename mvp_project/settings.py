from pathlib import Path
import os
import sys
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

# Module Builder WA (admin módulos).
# settings.py (local): ON por defecto — aunque .env traiga DJANGO_DEBUG=False.
# settings_production.py: OFF salvo EKI_MODULE_BUILDER_BETA=1.
# Allowlist: `*` = todos los cursos (aunque beta OFF).
_EKI_MB = os.environ.get('EKI_MODULE_BUILDER_BETA', '').strip().lower()
if _EKI_MB in ('0', 'false', 'no', 'off'):
    EKI_MODULE_BUILDER_BETA = False
elif _EKI_MB in ('1', 'true', 'yes', 'on'):
    EKI_MODULE_BUILDER_BETA = True
else:
    EKI_MODULE_BUILDER_BETA = True

# Allowlist de cursos con Builder ON aunque el flag global esté OFF (piloto por curso).
# Tokens: id, subcadena de nombre, o `*` / `all` = todos.
EKI_MODULE_BUILDER_CURSOS = os.environ.get(
    'EKI_MODULE_BUILDER_CURSOS', '*'
)

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
    # YouTube embeds requieren Referer (Error 153 si same-origin/no-referrer)
    SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

# 3. APLICACIONES INSTALADAS
INSTALLED_APPS = [
    'unfold',                   # Debe ir antes de django.contrib.admin
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
    'portal',                   # Portal web para clientes B2B
    'aprende',                  # Aula web estudiantes / profesores
    'studio',                   # Catálogo / creadores (separado del aula)
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Para servir archivos estáticos en producción
    'core.middleware.RequestContextMiddleware',  # request_id y latencia básica
    'core.host_isolation.HostIsolationMiddleware',  # admin/portal/studio/aprende por host
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'portal.middleware.SuscripcionMiddleware',
    'aprende.middleware.AprendeEstudianteMiddleware',
    'studio.middleware.StudioCuentaMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'core.middleware.RateLimitMiddleware',  # 🔒 Rate limiting
    'core.middleware.CertificadoAccessMiddleware',  # 🔐 Auditoría de acceso a certificados
]

# Wompi (Studio — pagos cursos)
WOMPI_PUBLIC_KEY = os.environ.get('WOMPI_PUBLIC_KEY', '')
WOMPI_PRIVATE_KEY = os.environ.get('WOMPI_PRIVATE_KEY', '')
WOMPI_INTEGRITY_SECRET = os.environ.get('WOMPI_INTEGRITY_SECRET', '')
# Pruebas Studio: permite «Simular pago» aunque haya llaves Wompi (solo si lo activas en EB).
STUDIO_ALLOW_PAYMENT_SIMULATION = os.environ.get(
    'STUDIO_ALLOW_PAYMENT_SIMULATION', ''
).strip().lower() in ('1', 'true', 'yes', 'on')

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
                'portal.context_processors.pqrs_pendientes',
                'portal.context_processors.portal_organizacion',
                'aprende.context_processors.aprende_social',
            ],
        },
    },
]

WSGI_APPLICATION = 'mvp_project.wsgi.application'

# 4. BASE DE DATOS
import os

# Prioridad: variables individuales DB_* → DATABASE_URL → SQLite
_ON_EB = bool(
    os.environ.get('ELASTIC_BEANSTALK')
    or os.environ.get('AWS_EXECUTION_ENV')
    or os.environ.get('AWS_EB_ENVIRONMENT_NAME')
)
_USE_REMOTE_DB = _ON_EB or os.environ.get('EKI_USE_REMOTE_DB', '').strip().lower() in (
    '1', 'true', 'yes', 'on',
)

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
elif os.environ.get('DATABASE_URL') and _USE_REMOTE_DB:
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
        # Verificar conexion real; si falla (ej. local sin acceso a RDS), usar SQLite.
        # En `manage.py test` no sondear RDS: ahorra ~3s por arranque y evita ruido.
        if not _ON_EB:
            running_tests = (
                'test' in sys.argv
                or os.environ.get('DJANGO_TEST') == '1'
            )
            if running_tests:
                print('[OK] Tests: usando SQLite (sin sondear RDS).')
                DATABASES = {
                    'default': {
                        'ENGINE': 'django.db.backends.sqlite3',
                        'NAME': BASE_DIR / 'db.sqlite3',
                    }
                }
            else:
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
elif os.environ.get('DATABASE_URL') and not _USE_REMOTE_DB:
    print('[OK] Local: SQLite (DATABASE_URL del .env ignorada; EKI_USE_REMOTE_DB=1 para RDS).')
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
# 8. CONFIGURACIÓN VISUAL — django-unfold
# ==========================================
# Jazzmin retirado. Config: mvp_project/unfold_admin.py
from mvp_project.unfold_admin import UNFOLD  # noqa: E402

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

# Firma Twilio (HMAC) en webhooks. Env explícito gana; si no: True en prod, False en DEBUG/tests.
_twilio_validate_sig = os.environ.get('TWILIO_VALIDATE_SIGNATURE', '').strip().lower()
_is_testing_runtime = (
    'test' in sys.argv
    or 'pytest' in ' '.join(sys.argv).lower()
    or os.environ.get('DJANGO_TEST') == '1'
)
if _twilio_validate_sig in ('1', 'true', 'yes', 'on'):
    TWILIO_VALIDATE_SIGNATURE = True
elif _twilio_validate_sig in ('0', 'false', 'no', 'off'):
    TWILIO_VALIDATE_SIGNATURE = False
else:
    TWILIO_VALIDATE_SIGNATURE = (not DEBUG) and (not _is_testing_runtime)
# Base pública (https://host) si el ALB/proxy firma una URL distinta a build_absolute_uri()
TWILIO_WEBHOOK_PUBLIC_URL = os.environ.get('TWILIO_WEBHOOK_PUBLIC_URL', '').strip()

# Slack ops (alertas módulos borrador, campañas). Vacío = desactivado.
EKI_SLACK_OPS_WEBHOOK = os.environ.get('EKI_SLACK_OPS_WEBHOOK', '').strip()

# 📢 Templates de Twilio para envío masivo (deben estar aprobados)
TWILIO_TEMPLATE_ANUNCIO_GRUPAL = os.environ.get('TWILIO_TEMPLATE_ANUNCIO_GRUPAL', '')  # Content SID del template de anuncios
TWILIO_TEMPLATE_INVITACION_GRUPO = os.environ.get('TWILIO_TEMPLATE_INVITACION_GRUPO', '')  # Content SID del template de invitación
# Content SID (HSM) para recordatorio cuando se desbloquea un módulo con drip. Vacío = mensaje de texto en sesión.
# Requiere Celery Beat con la tarea reenganche_drip_content_diario (ver mvp_project/celery.py, 8:00).
TWILIO_TEMPLATE_DRIP_REENGANCHE = os.environ.get('TWILIO_TEMPLATE_DRIP_REENGANCHE', '')
# Centro de Éxito: días sin WhatsApp entrante para reenganche automático
try:
    DIAS_INACTIVIDAD_REENGANCHE = int(os.environ.get('DIAS_INACTIVIDAD_REENGANCHE', '7') or 7)
except (TypeError, ValueError):
    DIAS_INACTIVIDAD_REENGANCHE = 7
try:
    REENGANCHE_INACTIVOS_LIMITE = int(os.environ.get('REENGANCHE_INACTIVOS_LIMITE', '40') or 40)
except (TypeError, ValueError):
    REENGANCHE_INACTIVOS_LIMITE = 40
try:
    REENGANCHE_INACTIVOS_COOLDOWN_DIAS = int(
        os.environ.get('REENGANCHE_INACTIVOS_COOLDOWN_DIAS', '5') or 5
    )
except (TypeError, ValueError):
    REENGANCHE_INACTIVOS_COOLDOWN_DIAS = 5

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
# Si true, no inyecta al prompt chunks por debajo del umbral (reduce alucinación por contexto basura)
BOT_COMERCIAL_RAG_FILTER_CHUNKS = os.environ.get('BOT_COMERCIAL_RAG_FILTER_CHUNKS', 'true').strip().lower() in (
    '1', 'true', 'yes', 'on',
)
BOT_COMERCIAL_VISION_MODEL = os.environ.get('BOT_COMERCIAL_VISION_MODEL', 'gpt-5-mini')
# Extracción PDF para RAG (PyMuPDF + OCR Tesseract en servidores con tesseract instalado)
RAG_PDF_OCR_ENABLED = os.environ.get('RAG_PDF_OCR_ENABLED', 'True').strip().lower() in ('1', 'true', 'yes', 'on')
RAG_PDF_OCR_LANG = os.environ.get('RAG_PDF_OCR_LANG', 'spa+eng')
try:
    RAG_PDF_OCR_MAX_PAGES = int(os.environ.get('RAG_PDF_OCR_MAX_PAGES', '8'))
except (TypeError, ValueError):
    RAG_PDF_OCR_MAX_PAGES = 8
try:
    RAG_INDEX_TASK_STAGGER_SECONDS = int(os.environ.get('RAG_INDEX_TASK_STAGGER_SECONDS', '12'))
except (TypeError, ValueError):
    RAG_INDEX_TASK_STAGGER_SECONDS = 12
# Límite de tokens de salida del chat (menor = respuesta WhatsApp más corta y barata).
try:
    BOT_COMERCIAL_OPENAI_MAX_TOKENS = int(os.environ.get('BOT_COMERCIAL_OPENAI_MAX_TOKENS', '420'))
except (TypeError, ValueError):
    BOT_COMERCIAL_OPENAI_MAX_TOKENS = 420
# Agrosavia live (repo público) — P0: enriquecer cuando RAG es corto o consulta agro.
BOT_COMERCIAL_AGROSAVIA_ENABLED = os.environ.get(
    'BOT_COMERCIAL_AGROSAVIA_ENABLED', 'true'
).strip().lower() in ('1', 'true', 'yes', 'on')
try:
    BOT_COMERCIAL_AGROSAVIA_MIN_RAG_CHARS = int(
        os.environ.get('BOT_COMERCIAL_AGROSAVIA_MIN_RAG_CHARS', '1400')
    )
except (TypeError, ValueError):
    BOT_COMERCIAL_AGROSAVIA_MIN_RAG_CHARS = 1400
try:
    BOT_COMERCIAL_AGROSAVIA_SIZE = int(os.environ.get('BOT_COMERCIAL_AGROSAVIA_SIZE', '3'))
except (TypeError, ValueError):
    BOT_COMERCIAL_AGROSAVIA_SIZE = 3
try:
    BOT_COMERCIAL_AGROSAVIA_MAX_CHARS = int(
        os.environ.get('BOT_COMERCIAL_AGROSAVIA_MAX_CHARS', '2200')
    )
except (TypeError, ValueError):
    BOT_COMERCIAL_AGROSAVIA_MAX_CHARS = 2200
# Nat + Open-Meteo: probabilidad climática por municipio (WhatsApp)
NAT_OPEN_METEO_ENABLED = os.environ.get('NAT_OPEN_METEO_ENABLED', 'true').strip().lower() in (
    '1', 'true', 'yes', 'on',
)
try:
    NAT_OPEN_METEO_TIMEOUT = float(os.environ.get('NAT_OPEN_METEO_TIMEOUT', '4'))
except (TypeError, ValueError):
    NAT_OPEN_METEO_TIMEOUT = 4.0
try:
    NAT_OPEN_METEO_CACHE_SECONDS = int(os.environ.get('NAT_OPEN_METEO_CACHE_SECONDS', '3600'))
except (TypeError, ValueError):
    NAT_OPEN_METEO_CACHE_SECONDS = 3600
# Cuánto texto RAG inyectar al prompt del bot comercial (menor = menos latencia).
try:
    BOT_COMERCIAL_RAG_TOP_K = int(os.environ.get('BOT_COMERCIAL_RAG_TOP_K', '4'))
except (TypeError, ValueError):
    BOT_COMERCIAL_RAG_TOP_K = 4
BOT_COMERCIAL_RAG_TOP_K = max(2, min(BOT_COMERCIAL_RAG_TOP_K, 12))
try:
    BOT_COMERCIAL_RAG_MAX_CHARS = int(os.environ.get('BOT_COMERCIAL_RAG_MAX_CHARS', '1200'))
except (TypeError, ValueError):
    BOT_COMERCIAL_RAG_MAX_CHARS = 1200
BOT_COMERCIAL_RAG_MAX_CHARS = max(400, min(BOT_COMERCIAL_RAG_MAX_CHARS, 2500))
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
# gpt-5*: minimal|low|medium|high — low evita gastar todo el cupo en reasoning vacío
BOT_COMERCIAL_REASONING_EFFORT = os.environ.get('BOT_COMERCIAL_REASONING_EFFORT', 'low').strip().lower() or 'low'

# ==========================================
# Certificados — URL pública del QR (página eki)
# ==========================================
# Público (QR). No usar admin.* — subdominio dedicado + CNAME en Cloudflare.
CERTIFICADO_VERIFICACION_BASE_URL = os.environ.get(
    'CERTIFICADO_VERIFICACION_BASE_URL',
    'https://certificados.eki.technology',
).strip().rstrip('/')
# CORS: origen permitido para llamadas al API de verificación.
CERT_VERIFICATION_ALLOWED_ORIGIN = os.environ.get(
    'CERT_VERIFICATION_ALLOWED_ORIGIN',
    '*',
).strip().rstrip('/')

# ==========================================
# 🌱 AGRONEXO — alias legacy de BOT_COMERCIAL (canal unificado bot_comercial)
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
# API key obligatoria en prod: si la key está vacía no abrir la puerta.
_integracion_require = os.environ.get('INTEGRACION_API_REQUIRE_KEY', '').strip().lower()
if _integracion_require in ('1', 'true', 'yes', 'on'):
    INTEGRACION_API_REQUIRE_KEY = True
elif _integracion_require in ('0', 'false', 'no', 'off'):
    INTEGRACION_API_REQUIRE_KEY = False
else:
    INTEGRACION_API_REQUIRE_KEY = (not DEBUG) and (not _is_testing_runtime)
try:
    INTEGRACION_API_RATE_LIMIT = int(os.environ.get('INTEGRACION_API_RATE_LIMIT', '120') or 120)
except (TypeError, ValueError):
    INTEGRACION_API_RATE_LIMIT = 120
try:
    INTEGRACION_API_RATE_PERIOD = int(os.environ.get('INTEGRACION_API_RATE_PERIOD', '60') or 60)
except (TypeError, ValueError):
    INTEGRACION_API_RATE_PERIOD = 60

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

# AUTO-DETECCION DE PRODUCCION / S3
import logging
logger = logging.getLogger(__name__)

_settings_mod = os.environ.get('DJANGO_SETTINGS_MODULE', '')
_force_s3_local = os.environ.get('EKI_USE_S3_LOCAL', '').strip().lower() in (
    '1', 'true', 'yes', 'on',
)
if _settings_mod.endswith('settings_production') or _ON_EB:
    sys.stderr.write("[PRODUCCION DETECTADA - FORZANDO S3]\n")
    USE_S3 = True
elif _force_s3_local:
    # Opt-in: probar S3 desde laptop sin settings_production
    USE_S3 = True
else:
    # Ignora USE_S3=True del .env de prod en desarrollo local (menos fricción).
    USE_S3 = False

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
    STORAGES = {
        **globals().get('STORAGES', {}),
        'default': {
            'BACKEND': 'storages.backends.s3boto3.S3Boto3Storage',
        },
        'staticfiles': {
            'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
        },
    }
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

# Tests: sin manifest hashed ni S3 (evita Missing staticfiles manifest entry).
_running_tests = (
    'test' in sys.argv
    or os.environ.get('DJANGO_TEST') == '1'
)
if _running_tests:
    STORAGES = {
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    }
    STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'

# ========================================
# 🔒 CONFIGURACIÓN DE RATE LIMITING
# ========================================
RATE_LIMIT_ENABLED = True  # Habilitar rate limiting
RATE_LIMIT_REQUESTS = 100  # Máximo de requests por IP
RATE_LIMIT_PERIOD = 60  # Período en segundos

# WhatsApp rate limiting
# Soporte eki desde el portal B2B (botón flotante WhatsApp)
PORTAL_WHATSAPP_SOPORTE = os.environ.get('PORTAL_WHATSAPP_SOPORTE', '573103844274')

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

# Aprende OTP / código *aula* (login web)
APRENDE_ACCESO_WA_TTL = int(os.environ.get('APRENDE_ACCESO_WA_TTL', '600') or 600)
APRENDE_OTP_MAX_ATTEMPTS = int(os.environ.get('APRENDE_OTP_MAX_ATTEMPTS', '5') or 5)
APRENDE_OTP_LOCKOUT_SECONDS = int(os.environ.get('APRENDE_OTP_LOCKOUT_SECONDS', '900') or 900)
APRENDE_OTP_IP_MAX_ATTEMPTS = int(os.environ.get('APRENDE_OTP_IP_MAX_ATTEMPTS', '20') or 20)
APRENDE_OTP_IP_WINDOW = int(os.environ.get('APRENDE_OTP_IP_WINDOW', '600') or 600)
APRENDE_OTP_EMIT_MAX = int(os.environ.get('APRENDE_OTP_EMIT_MAX', '8') or 8)
APRENDE_OTP_EMIT_WINDOW = int(os.environ.get('APRENDE_OTP_EMIT_WINDOW', '3600') or 3600)

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
# REDIS_URL: alias opcional (ElastiCache). Si existe y no hay CELERY_BROKER_URL, se usa.
_redis_url = (os.environ.get('REDIS_URL') or '').strip()
_celery_broker = (os.environ.get('CELERY_BROKER_URL') or '').strip() or _redis_url or 'redis://localhost:6379/0'
_celery_backend = (os.environ.get('CELERY_RESULT_BACKEND') or '').strip() or _celery_broker

CELERY_BROKER_URL = _celery_broker
CELERY_RESULT_BACKEND = _celery_backend
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

# ElastiCache con TLS (rediss://…)
if CELERY_BROKER_URL.startswith('rediss://'):
    import ssl as _ssl

    _ssl_opts = {'ssl_cert_reqs': _ssl.CERT_REQUIRED}
    if os.environ.get('CELERY_BROKER_SSL_CERT_REQS', '').strip().lower() in ('none', 'optional'):
        _ssl_opts = {'ssl_cert_reqs': _ssl.CERT_NONE}
    CELERY_BROKER_USE_SSL = _ssl_opts
    CELERY_REDIS_BACKEND_USE_SSL = dict(_ssl_opts)

# Chroma local (dev). En prod: settings_production.CHROMA_DB_DIR / env.
CHROMA_DB_DIR = os.environ.get('CHROMA_DB_DIR') or str(BASE_DIR / 'chroma_db')

# Cola dedicada para indexación PDF/RAG (worker_rag en Procfile EB).
# Las tareas pesadas no bloquean campañas, emails ni webhooks.
CELERY_TASK_QUEUES = {
    'celery': {'exchange': 'celery', 'routing_key': 'celery'},
    'rag_index': {'exchange': 'rag_index', 'routing_key': 'rag_index'},
}
CELERY_TASK_ROUTES = {
    'core.tasks.indexar_biblioteca_nat_por_id': {'queue': 'rag_index'},
    'core.tasks.indexar_documento_rag_por_id': {'queue': 'rag_index'},
    'core.tasks.procesar_zip_rag_comercial': {'queue': 'rag_index'},
}
try:
    RAG_WORKER_CONCURRENCY = int(os.environ.get('RAG_WORKER_CONCURRENCY', '1'))
except (TypeError, ValueError):
    RAG_WORKER_CONCURRENCY = 1

# En desarrollo sin Redis, deshabilitar Celery (las tareas se ejecutan síncronamente)
CELERY_TASK_ALWAYS_EAGER = os.environ.get('CELERY_TASK_ALWAYS_EAGER', 'False') == 'True'
CELERY_TASK_EAGER_PROPAGATES = True

# Webhook WhatsApp educativo en Celery (libera Gunicorn). Desactivado por defecto.
WEBHOOK_CELERY_ASYNC = os.environ.get('WEBHOOK_CELERY_ASYNC', 'False') == 'True'

# Formulario GEI — envío automático del balance por WhatsApp al completar un módulo del curso
GEI_MODULO_NUMERO_WHATSAPP_RESULTADO = int(os.environ.get('GEI_MODULO_NUMERO_WHATSAPP_RESULTADO', '5') or '5')
GEI_RESULTADO_WHATSAPP_ENABLED = os.environ.get('GEI_RESULTADO_WHATSAPP_ENABLED', 'true').lower() in (
    '1', 'true', 'yes', 'on',
)
