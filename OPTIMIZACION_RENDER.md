# OPTIMIZACIONES PARA RENDER STANDARD (512MB)

## Problema Actual
- Render Standard: 512 MB RAM
- Tu app consume: ~800MB+ (se queda sin memoria)
- Resultado: Crashes, timeouts, no funciona

## Soluciones Implementadas

### 1. Dockerfile Ultra-Optimizado
**Archivo:** `Dockerfile.render`

**Cambios:**
- ❌ Multi-stage build (usa mas RAM al construir)
- ✅ Single stage minimo
- ✅ Sin cache de pip
- ✅ Limpieza agresiva de __pycache__
- ✅ Solo 1 worker de Gunicorn (era 3)
- ✅ worker-tmp-dir en /dev/shm (RAM, mas rapido)

**Ahorro:** ~200MB

### 2. Requirements Minimos
**Archivo:** `requirements.render.txt`

**Removidos:**
- boto3, django-storages (si no usas S3)
- google-generativeai, cohere (si solo usas OpenAI)
- pandas (muy pesado - 100MB)
- reportlab, PyPDF2 (si no usas PDFs)
- openpyxl (si no usas Excel)
- pydub (si no procesas audio)

**Mantuve solo:**
- Django + gunicorn
- psycopg2 (PostgreSQL)
- twilio (WhatsApp)
- openai (AI)
- pillow, requests, python-docx (basicos)

**Ahorro:** ~150MB

### 3. Configuracion Gunicorn Optimizada

**Antes:**
```
--workers 3     # 3 procesos x 250MB = 750MB
--threads 2
--timeout 60
```

**Ahora:**
```
--workers 1              # 1 proceso = ~300MB
--threads 2              # 2 threads (suficiente)
--timeout 120            # Mas tiempo para AI calls
--max-requests 1000      # Reinicia worker periodicamente
--worker-tmp-dir /dev/shm # Usa RAM en vez de disco
```

**Ahorro:** ~400MB

### 4. Settings Django Optimizados

Necesitas agregar en `settings_production.py`:

```python
# Desactivar debug
DEBUG = False

# Logging minimo
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',  # Solo warnings y errors
    },
}

# Cache en memoria (no en DB)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
        'OPTIONS': {
            'MAX_ENTRIES': 100,  # Limite para no usar mucha RAM
        }
    }
}

# Desactivar middleware pesado si no lo necesitas
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    # Comentar si no necesitas:
    # 'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
```

### 5. render.yaml Configuracion

**Archivo:** `render.yaml`

Configuracion automatica para Render:
- 1 worker
- Database starter (gratis)
- Variables de entorno
- Build command optimizado

## Uso Total de RAM Estimado

### Antes:
```
Gunicorn (3 workers):   750MB
Django + libs:          150MB
PostgreSQL conns:       50MB
Sistema:                50MB
--------------------------------
TOTAL:                  1000MB ❌ Crash en 512MB
```

### Ahora:
```
Gunicorn (1 worker):    250MB
Django + libs:          100MB (deps reducidas)
PostgreSQL conns:       30MB
Sistema:                50MB
Buffer:                 82MB
--------------------------------
TOTAL:                  512MB ✅ Cabe justo
```

## Como Deployar en Render

### Opcion A: Usar render.yaml (Automatico)

1. Push a GitHub:
```bash
git add .
git commit -m "Optimizado para Render Standard"
git push origin main
```

2. En Render Dashboard:
   - New → Blueprint
   - Connect GitHub repo
   - Render detecta `render.yaml`
   - Deploy automatico

### Opcion B: Manual

1. En Render Dashboard:
   - New Web Service
   - Connect repo
   - **Build Command:** 
     ```
     pip install -r requirements.render.txt
     ```
   - **Start Command:**
     ```
     gunicorn mvp_project.wsgi:application --bind 0.0.0.0:$PORT --workers 1 --threads 2 --timeout 120 --max-requests 1000 --worker-tmp-dir /dev/shm
     ```
   - Environment: `DJANGO_SETTINGS_MODULE=mvp_project.settings_production`

2. Add PostgreSQL Database (Starter - $7/mes)

3. Configurar Variables:
   - SECRET_KEY
   - DATABASE_URL (auto desde PostgreSQL)
   - TWILIO_ACCOUNT_SID
   - TWILIO_AUTH_TOKEN
   - OPENAI_API_KEY

## Si Aun Asi No Funciona

### Opcion 1: Upgrade a Render Pro ($25/mes)
- 2 GB RAM
- 2 workers posibles
- Mas estable

### Opcion 2: Railway ($20/mes)
- 8 GB RAM incluidos
- PostgreSQL incluido
- Mas generoso con recursos

### Opcion 3: AWS EB Single Instance con Reserved ($51/mes)
- 4 GB RAM
- Mas control
- Escalable

## Monitoreo en Render

Para ver si funciona:
1. Render Dashboard → Logs
2. Ver si hay errores de memoria
3. Comandos utiles en logs:
   ```
   MemoryError
   OOMKilled
   worker timeout
   ```

## Optimizaciones Adicionales

### Si necesitas mas espacio:

1. **Desactivar AI temporalmente**
   ```python
   # En settings_production.py
   USE_OPENAI = False  # Para testing
   ```

2. **Usar API calls asincronas**
   ```python
   # En vez de procesar en request
   # Usa Celery + Redis (pero necesita mas RAM)
   ```

3. **Reducir session storage**
   ```python
   SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
   ```

4. **Lazy loading de modulos**
   ```python
   # No importar AI libs en settings.py
   # Importar solo cuando se usan
   ```

## Archivos Creados

1. `Dockerfile.render` - Dockerfile optimizado
2. `requirements.render.txt` - Dependencias minimas
3. `render.yaml` - Configuracion automatica
4. Este archivo - Documentacion

## Comandos Git

```bash
# Push optimizaciones
git add Dockerfile.render requirements.render.txt render.yaml
git commit -m "Optimizado para Render Standard 512MB"
git push origin main

# Luego en Render: redeploy
```

## Resultado Esperado

Con estas optimizaciones:
- ✅ Cabe en 512MB
- ✅ 1 worker suficiente para 10-20 usuarios concurrentes
- ✅ Respuestas en 2-5 segundos
- ✅ Costo: $7/mes (Standard) + $7/mes (DB) = $14/mes total

## Si Sigue sin Funcionar

Dame acceso y verifico:
1. Logs de Render
2. Uso real de RAM
3. Que endpoint consume mas memoria
4. Optimizaciones especificas a tu codigo

**Prueba esto primero y me dices como va!**
