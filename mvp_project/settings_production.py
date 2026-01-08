"""
Settings de Producción para EKI
Resuelve todos los warnings de seguridad de Django

IMPORTANTE: 
- Usar SOLO en producción (Railway, Heroku, VPS)
- NO usar en desarrollo local
"""

from .settings import *

# ============================================
# SEGURIDAD - Resolución de Warnings
# ============================================

# ?: (security.W018) DEBUG debe ser False en producción
DEBUG = False

# ?: (security.W009) SECRET_KEY debe ser largo y aleatorio
# Generar nueva clave con: python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-CAMBIAR-EN-PRODUCCION')

# Hosts permitidos
ALLOWED_HOSTS = [
    'eki-mvp.up.railway.app',  # Railway
    'eki-mvp.herokuapp.com',   # Heroku
    '.ngrok.io',               # Ngrok (desarrollo)
    'localhost',
    '127.0.0.1',
]

# Agregar dominios personalizados
if 'DOMAIN' in os.environ:
    ALLOWED_HOSTS.append(os.environ['DOMAIN'])

# ============================================
# SSL/HTTPS - Resolución de Warnings
# ============================================

# ?: (security.W008) Redirigir todo a HTTPS
SECURE_SSL_REDIRECT = True

# ?: (security.W004) HTTP Strict Transport Security
SECURE_HSTS_SECONDS = 31536000  # 1 año
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# ?: (security.W012) Cookies seguras de sesión
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'

# ?: (security.W016) CSRF cookies seguras
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Lax'

# Otros headers de seguridad
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'

# ============================================
# BASE DE DATOS - Producción
# ============================================

# PostgreSQL en producción (Railway, Heroku)
if 'DATABASE_URL' in os.environ:
    import dj_database_url
    DATABASES = {
        'default': dj_database_url.config(
            default=os.environ['DATABASE_URL'],
            conn_max_age=600,
            ssl_require=True
        )
    }

# ============================================
# ARCHIVOS ESTÁTICOS - Producción
# ============================================

# WhiteNoise para servir archivos estáticos
MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

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
        'file': {
            'class': 'logging.FileHandler',
            'filename': 'logs/production.log',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'core': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
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

# Cache con Redis (Railway, Heroku)
if 'REDIS_URL' in os.environ:
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': os.environ['REDIS_URL'],
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            }
        }
    }
    SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
    SESSION_CACHE_ALIAS = 'default'

# Compresión GZip
MIDDLEWARE.append('django.middleware.gzip.GZipMiddleware')

print("✅ Settings de producción cargados")
print(f"   DEBUG: {DEBUG}")
print(f"   SECURE_SSL_REDIRECT: {SECURE_SSL_REDIRECT}")
print(f"   ALLOWED_HOSTS: {ALLOWED_HOSTS[:3]}...")
