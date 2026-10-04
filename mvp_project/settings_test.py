"""Settings de pytest/CI: PostgreSQL obligatorio. Sin fallback a SQLite."""
import os

from .settings import *  # noqa: F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "eki_test"),
        "USER": os.environ.get("POSTGRES_USER", "postgres"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "postgres"),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

# Los tests no hablan con el bucket de producción.
USE_S3 = False
DEFAULT_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

# Credenciales fijas. Ignoran el entorno para que un test no hable con Twilio, Meta u OpenAI reales.
_CREDENCIALES_FALSAS = {
    "TWILIO_ACCOUNT_SID": "ACtest00000000000000000000000000",
    "TWILIO_AUTH_TOKEN": "twilio-auth-token-de-prueba",
    "OPENAI_API_KEY": "sk-test-no-es-una-llave-real",
    "GEMINI_API_KEY": "gemini-test-no-es-una-llave-real",
    "GOOGLE_API_KEY": "google-test-no-es-una-llave-real",
    "WHATSAPP_TOKEN": "whatsapp-token-de-prueba",
    "WHATSAPP_APP_SECRET": "whatsapp-app-secret-de-prueba",
}
os.environ.update(_CREDENCIALES_FALSAS)
TWILIO_ACCOUNT_SID = _CREDENCIALES_FALSAS["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN = _CREDENCIALES_FALSAS["TWILIO_AUTH_TOKEN"]
OPENAI_API_KEY = _CREDENCIALES_FALSAS["OPENAI_API_KEY"]
GEMINI_API_KEY = _CREDENCIALES_FALSAS["GEMINI_API_KEY"]
GOOGLE_API_KEY = _CREDENCIALES_FALSAS["GOOGLE_API_KEY"]
WHATSAPP_TOKEN = _CREDENCIALES_FALSAS["WHATSAPP_TOKEN"]
WHATSAPP_APP_SECRET = _CREDENCIALES_FALSAS["WHATSAPP_APP_SECRET"]

# Base 15: conftest hace flushdb antes de cada test. No comparte la db 0 del broker.
REDIS_URL = "redis://127.0.0.1:6379/15"
CELERY_BROKER_URL = REDIS_URL
