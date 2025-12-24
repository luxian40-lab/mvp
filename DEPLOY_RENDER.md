# ==========================================
# GUÍA DE DEPLOY EN RENDER.COM
# ==========================================

## 🚀 PASO 1: Crear cuenta en Render
1. Ve a: https://render.com
2. Sign up con GitHub (recomendado)

## 📦 PASO 2: Subir código a GitHub
1. Crea repositorio en GitHub (público o privado)
2. Sube tu carpeta eki_mvp

## 🎯 PASO 3: Crear Web Service en Render
1. Click "New +" → "Web Service"
2. Conecta tu repositorio de GitHub
3. Configuración:
   - Name: `eki-mvp` (o el nombre que quieras)
   - Environment: `Python 3`
   - Build Command: `./build.sh`
   - Start Command: `gunicorn mvp_project.wsgi`
   - Plan: `Free`

## 🔐 PASO 4: Variables de Entorno
En "Environment" → "Add Environment Variable", agrega:

```
SECRET_KEY=django-insecure-production-key-$(openssl rand -hex 32)
DJANGO_DEBUG=False
ALLOWED_HOSTS=tu-app.onrender.com
CSRF_TRUSTED_ORIGINS=https://tu-app.onrender.com

TWILIO_ACCOUNT_SID=ACdfe1762471d825240c7ac5833cf36bf9
TWILIO_AUTH_TOKEN=[BUSCAR EN TWILIO CONSOLE]
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
WHATSAPP_VERIFY_TOKEN=eki_whatsapp_verify_token_2025

OPENAI_API_KEY=[TU KEY DE OPENAI]
```

## 🗄️ PASO 5: Base de Datos PostgreSQL
1. Click "New +" → "PostgreSQL"
2. Name: `eki-mvp-db`
3. Plan: `Free`
4. Click "Create Database"
5. Copia "Internal Database URL"
6. Pégala en Environment Variables como `DATABASE_URL`

## ✅ PASO 6: Deploy
1. Click "Create Web Service"
2. Espera 5-10 minutos
3. Tu app estará en: `https://eki-mvp.onrender.com` (o tu nombre)

## 📱 PASO 7: Configurar Twilio Sandbox
1. Ve a: https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn
2. En "When a message comes in":
   ```
   URL: https://tu-app.onrender.com/webhook/whatsapp/
   Method: POST
   ```
3. Click "Save"

## 🧪 PASO 8: Probar
1. Envía a WhatsApp: +1 415 523 8886
2. Mensaje: "Hola"
3. La IA debería responder en 5 segundos

## 🔧 COMANDOS ÚTILES
- Ver logs: Render Dashboard → "Logs"
- Restart: Click "Manual Deploy" → "Clear build cache & deploy"
