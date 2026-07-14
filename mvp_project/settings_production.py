"""
Settings de Producción para eki  
Resuelve todos los warnings de seguridad de Django

IMPORTANTE: 
- Usar SOLO en producción (Railway, Heroku, VPS)
- NO usar en desarrollo local
"""

import os
import sys
from pathlib import Path

# ============================================
# 🔥 FORZAR S3 **ANTES** DE CUALQUIER IMPORT
# ============================================
## sys.stderr.write("\n" + "="*70 + "\n")
## sys.stderr.write("SETTINGS_PRODUCTION.PY - FORZANDO S3\n")
## sys.stderr.write("="*70 + "\n")

# Establecer variables de entorno ANTES de que settings.py las lea
os.environ.setdefault('USE_S3', 'True')
os.environ['AWS_ACCESS_KEY_ID'] = os.environ.get('AWS_ACCESS_KEY_ID', '')
os.environ['AWS_SECRET_ACCESS_KEY'] = os.environ.get('AWS_SECRET_ACCESS_KEY', '')
os.environ['AWS_STORAGE_BUCKET_NAME'] = os.environ.get('AWS_STORAGE_BUCKET_NAME', 'eki-produccion')
os.environ['AWS_S3_REGION_NAME'] = os.environ.get('AWS_S3_REGION_NAME', 'us-east-2')

## sys.stderr.write(f"ENV VARS configuradas:\n")
## sys.stderr.write(f"  USE_S3 = {os.environ.get('USE_S3')}\n")
## sys.stderr.write(f"  BUCKET = {os.environ.get('AWS_STORAGE_BUCKET_NAME')}\n")
## sys.stderr.write(f"  KEY = {os.environ.get('AWS_ACCESS_KEY_ID')[:15]}...\n")

# AHORA sí importar settings base (que leerá las env vars)
from .settings import *

# Siempre definir BASE_DIR aquí: si settings.py llegó vacío en un deploy, import * no lo trae.
BASE_DIR = Path(__file__).resolve().parent.parent

## sys.stderr.write(f"\nDESPUES DE IMPORTAR SETTINGS:\n")
## sys.stderr.write(f"  DEFAULT_FILE_STORAGE = {DEFAULT_FILE_STORAGE}\n")
## sys.stderr.write(f"  MEDIA_URL = {MEDIA_URL}\n")
## sys.stderr.write(f"  USE_S3 final = {USE_S3}\n")
## sys.stderr.write("="*70 + "\n\n")

# ============================================
# SEGURIDAD - Resolución de Warnings
# ============================================

# ?: (security.W018) DEBUG debe ser False en producción
DEBUG = False

# ?: (security.W009) SECRET_KEY debe ser largo y aleatorio
# Generar nueva clave con: python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-CAMBIAR-EN-PRODUCCION')

# Hosts permitidos
_EB_CNAME = os.environ.get(
    'EB_CNAME_HOST',
    'eki-prod-final.eba-32krwxas.us-east-2.elasticbeanstalk.com',
)
_explicit_hosts = os.environ.get('EKI_ALLOWED_HOSTS', '').strip()
if _explicit_hosts:
    ALLOWED_HOSTS = [h.strip() for h in _explicit_hosts.split(',') if h.strip()]
    if _EB_CNAME not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(_EB_CNAME)
else:
    ALLOWED_HOSTS = ['*']
    if 'ALLOWED_HOSTS_EXTRA' in os.environ:
        extra_hosts = [h.strip() for h in os.environ['ALLOWED_HOSTS_EXTRA'].split(',') if h.strip()]
        if ALLOWED_HOSTS == ['*']:
            ALLOWED_HOSTS = list(extra_hosts)
            if _EB_CNAME not in ALLOWED_HOSTS:
                ALLOWED_HOSTS.append(_EB_CNAME)
        else:
            ALLOWED_HOSTS.extend(extra_hosts)

_csrf_env = os.environ.get('CSRF_TRUSTED_ORIGINS', '').strip()
if _csrf_env:
    CSRF_TRUSTED_ORIGINS = [o.strip() for o in _csrf_env.split(',') if o.strip()]

# ============================================
# SSL/HTTPS - Resolución de Warnings
# ============================================

# ?: (security.W008) Redirigir todo a HTTPS
# DESACTIVADO: Cloudflare termina HTTPS; el origen EB (single instance) suele ser HTTP:80
SECURE_SSL_REDIRECT = False

# ?: (security.W004) HTTP Strict Transport Security
# DESACTIVADO hasta configurar SSL
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

_behind_cloudflare = os.environ.get('EKI_BEHIND_CLOUDFLARE', 'true').lower() in ('1', 'true', 'yes')
if _behind_cloudflare:
    # Cloudflare envía X-Forwarded-Proto: https aunque el origen sea HTTP
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    USE_X_FORWARDED_HOST = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
else:
    SESSION_COOKIE_SECURE = False

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
# Compartir sesión entre studio.eki.technology y aprende.eki.technology
# (Studio = correo; Aprende = aula). Override vacío desactiva el dominio padre.
_session_domain = os.environ.get('SESSION_COOKIE_DOMAIN', '.eki.technology').strip()
if _session_domain:
    SESSION_COOKIE_DOMAIN = _session_domain
    CSRF_COOKIE_DOMAIN = os.environ.get('CSRF_COOKIE_DOMAIN', _session_domain).strip() or _session_domain

# ?: (security.W016) CSRF cookies seguras
if not _behind_cloudflare:
    CSRF_COOKIE_SECURE = False
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Lax'

# Otros headers de seguridad
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'


# ============================================
# BASE DE DATOS - Producción (FORZAR POSTGRES)
# ============================================
import os

# Opciones comunes para RDS (timeout TCP; sslmode vía env si hace falta)
_POSTGRES_CONNECT_TIMEOUT = int(os.environ.get('POSTGRES_CONNECT_TIMEOUT', '20'))

def _postgres_options():
    opts = {'connect_timeout': _POSTGRES_CONNECT_TIMEOUT}
    sslmode = os.environ.get('PGSSLMODE', '').strip()
    if sslmode:
        opts['sslmode'] = sslmode
    return opts

# Configuración de Base de Datos Robusta
DB_NAME = os.environ.get('DB_NAME')
DB_USER = os.environ.get('DB_USER')
DB_PASSWORD = os.environ.get('DB_PASSWORD')
DB_HOST = os.environ.get('DB_HOST')
DB_PORT = os.environ.get('DB_PORT', '5432')
DATABASE_URL = os.environ.get('DATABASE_URL')
_ON_ELASTIC_BEANSTALK = bool(os.environ.get('ELASTIC_BEANSTALK'))

if DB_NAME and DB_USER and DB_PASSWORD and DB_HOST:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': DB_NAME,
            'USER': DB_USER,
            'PASSWORD': DB_PASSWORD,
            'HOST': DB_HOST,
            'PORT': DB_PORT,
            'OPTIONS': _postgres_options(),
        }
    }
    print("[OK] [SETTINGS] PostgreSQL configurado via DB_* vars")
elif DATABASE_URL:
    import urllib.parse

    parsed = urllib.parse.urlparse(DATABASE_URL)

    def _database_url_to_django():
        return {
            'default': {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': parsed.path.lstrip('/'),
                'USER': parsed.username or '',
                'PASSWORD': parsed.password or '',
                'HOST': parsed.hostname or 'localhost',
                'PORT': str(parsed.port or 5432),
                'OPTIONS': _postgres_options(),
            }
        }

    # En EB siempre usar la URL de la app. En laptop: no pisar el fallback a SQLite
    # que ya aplicó mvp_project.settings si el RDS no respondió al ping inicial.
    if _ON_ELASTIC_BEANSTALK:
        DATABASES = _database_url_to_django()
        print(f"[OK] [SETTINGS] PostgreSQL via DATABASE_URL: {parsed.hostname}/{parsed.path.lstrip('/')}")
    else:
        try:
            import psycopg

            conn = psycopg.connect(
                host=parsed.hostname,
                port=parsed.port or 5432,
                user=parsed.username,
                password=parsed.password,
                dbname=parsed.path.lstrip('/'),
                connect_timeout=_POSTGRES_CONNECT_TIMEOUT,
            )
            conn.close()
            DATABASES = _database_url_to_django()
            print(f"[OK] [SETTINGS] PostgreSQL via DATABASE_URL: {parsed.hostname}/{parsed.path.lstrip('/')}")
        except Exception as conn_err:
            print(
                f"[WARN] [SETTINGS] DATABASE_URL no alcanzable desde esta máquina ({conn_err}). "
                f"Se mantiene la base definida en settings base (ENGINE={DATABASES.get('default', {}).get('ENGINE', '?')})."
            )
else:
    missing_vars = [v for v in ['DB_NAME', 'DB_USER', 'DB_PASSWORD', 'DB_HOST'] if not os.environ.get(v)]
    raise Exception(f"[ERROR] Faltan variables de entorno para PostgreSQL: {', '.join(missing_vars)}. Configura DB_* o DATABASE_URL.")

# Reusar conexiones en producción para menor latencia y menor churn de conexiones.
if DATABASES.get('default', {}).get('ENGINE') == 'django.db.backends.postgresql':
    DATABASES['default']['CONN_MAX_AGE'] = int(os.environ.get('DB_CONN_MAX_AGE', '60') or '60')

# ============================================
# ARCHIVOS ESTÁTICOS - Producción
# ============================================

# Directorio donde collectstatic guarda los archivos
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATIC_URL = '/static/'

# WhiteNoise para servir archivos estáticos con compresión
MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Configuración de WhiteNoise optimizada
WHITENOISE_MAX_AGE = 31536000  # 1 año de cache
WHITENOISE_ALLOW_ALL_ORIGINS = False
WHITENOISE_SKIP_COMPRESS_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'zip', 'gz', 'tgz', 'bz2', 'tbz', 'xz', 'br', 'swf', 'flv', 'woff', 'woff2']

# ============================================
# LOGGING - Producción
# ============================================

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{levelname}] {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',  # Reducir verbosidad
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'core': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'models_extras': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}

# ============================================
# EMAIL - Producción (SendGrid recomendado)
# ============================================

if 'SENDGRID_API_KEY' in os.environ:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = 'smtp.sendgrid.net'
    EMAIL_PORT = 587
    EMAIL_USE_TLS = True
    EMAIL_HOST_USER = 'apikey'
    EMAIL_HOST_PASSWORD = os.environ['SENDGRID_API_KEY']
    DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@eki.com')

# ============================================
# PERFORMANCE - Producción
# ============================================

# Cache en memoria local (sin Redis)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
        'OPTIONS': {
            'MAX_ENTRIES': 1000,
        }
    }
}

# Templates en caché
for template_engine in TEMPLATES:
    if template_engine['BACKEND'] == 'django.template.backends.django.DjangoTemplates':
        # Desactivar APP_DIRS cuando se usan loaders personalizados
        template_engine['APP_DIRS'] = False
        template_engine['OPTIONS']['loaders'] = [
            ('django.template.loaders.cached.Loader', [
                'django.template.loaders.filesystem.Loader',
                'django.template.loaders.app_directories.Loader',
            ]),
        ]

# Optimizaciones adicionales
DATA_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB

# Sesiones en base de datos (más estable que cache para login)
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_AGE = 1209600  # 2 semanas
SESSION_SAVE_EVERY_REQUEST = False

# Compresión GZip
MIDDLEWARE.append('django.middleware.gzip.GZipMiddleware')

# Deployment note: ensure SESSION_ENGINE is not indented in deployed copy
# This comment forces a clean commit to push the validated local file to EB

# ============================================
# CHROMA DB — persistir fuera de /var/app/current (sobrevive deploys EB)
# ============================================
CHROMA_DB_DIR = os.environ.get('CHROMA_DB_DIR', '/var/app/chroma_data')

# ============================================
# CELERY + REDIS (Elastic Beanstalk)
# ============================================
# Worker y beat del Procfile usan Redis en localhost (.ebextensions/03_redis.config).
# CELERY_TASK_ALWAYS_EAGER=True (env EB): .delay() en el proceso web corre en línea;
# beat sigue necesitando Redis para campañas programadas y reenganche drip (8:00).
if _ON_ELASTIC_BEANSTALK and not os.environ.get('CELERY_BROKER_URL'):
    _REDIS_LOCAL = 'redis://127.0.0.1:6379/0'
    CELERY_BROKER_URL = _REDIS_LOCAL
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND') or _REDIS_LOCAL

# ============================================
# FORZAR BACKEND DE ARCHIVOS S3 EN PRODUCCIÓN
# ============================================
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
