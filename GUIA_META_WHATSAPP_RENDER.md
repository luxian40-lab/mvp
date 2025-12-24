# 🚀 GUÍA COMPLETA: Meta WhatsApp Business + Render + OpenAI
**Configuración paso a paso para producción**

---

## 📋 **PARTE 1: Configurar Meta WhatsApp Business API**

### Paso 1: Crear App en Meta for Developers

1. Ve a: https://developers.facebook.com/
2. Haz clic en **"My Apps"** → **"Create App"**
3. Selecciona tipo: **"Business"**
4. Nombre de la app: **"Eki WhatsApp Bot"**
5. Email de contacto: tu email
6. Haz clic en **"Create App"**

### Paso 2: Agregar WhatsApp al App

1. En el dashboard del app, busca **"WhatsApp"**
2. Haz clic en **"Set up"**
3. Selecciona o crea una **Business Account**

### Paso 3: Obtener Credenciales

Después de configurar WhatsApp, verás un panel con:

#### A) **Temporary Access Token** (Token temporal)
```
EAABsbCS1iHgBO7YF0BSL3ZC... (muy largo)
```
- ⚠️ Este token expira en 24 horas
- Lo usaremos para pruebas, luego generaremos uno permanente

#### B) **Phone Number ID**
```
123456789012345
```
- Es el ID del número de prueba de Meta

#### C) **WhatsApp Business Account ID**
```
987654321098765
```

### Paso 4: Guardar Credenciales en .env

Edita tu archivo `.env`:

```bash
# Meta WhatsApp Cloud API
WHATSAPP_TOKEN=EAABsbCS1iHgBO7YF0BSL3ZC...  # Tu token aquí
WHATSAPP_PHONE_ID=123456789012345  # Tu Phone Number ID
WHATSAPP_VERIFY_TOKEN=eki_whatsapp_verify_token_2025  # Déjalo así
WHATSAPP_API_VERSION=v19.0

# OpenAI
OPENAI_API_KEY=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
```

### Paso 5: Probar localmente

```bash
# Terminal 1: Iniciar servidor
python manage.py runserver

# Terminal 2: Probar webhook
python test_webhook_meta.py
```

Si ves "✅ Verificación GET exitosa!" estás listo para el siguiente paso.

---

## 🌐 **PARTE 2: Deploy en Render.com**

### Paso 1: Crear cuenta en Render

1. Ve a: https://render.com/
2. Haz clic en **"Get Started"**
3. Conéctate con **GitHub**

### Paso 2: Subir código a GitHub

```bash
# En tu carpeta del proyecto
git init
git add .
git commit -m "Initial commit - Eki MVP con IA"
git branch -M main

# Crea un repo en GitHub y luego:
git remote add origin https://github.com/TU_USUARIO/eki-mvp.git
git push -u origin main
```

### Paso 3: Crear servicio Web en Render

1. En Render dashboard, haz clic en **"New +"** → **"Web Service"**
2. Conecta tu repositorio de GitHub: **eki-mvp**
3. Configura así:

```
Name: eki-whatsapp-bot
Runtime: Python 3
Region: Oregon (US West)
Branch: main
Build Command: ./build.sh
Start Command: gunicorn mvp_project.wsgi:application
Instance Type: Free
```

### Paso 4: Configurar Variables de Entorno

En Render, ve a **"Environment"** y agrega:

```bash
DJANGO_DEBUG=False
SECRET_KEY=<genera uno nuevo>
ALLOWED_HOSTS=eki-whatsapp-bot.onrender.com,localhost

# Meta WhatsApp
WHATSAPP_TOKEN=EAABsbCS...  # Tu token de Meta
WHATSAPP_PHONE_ID=123456789012345
WHATSAPP_VERIFY_TOKEN=eki_whatsapp_verify_token_2025
WHATSAPP_API_VERSION=v19.0

# OpenAI
OPENAI_API_KEY=sk-proj-b84Y...

# CSRF
CSRF_TRUSTED_ORIGINS=https://eki-whatsapp-bot.onrender.com
```

**Para generar SECRET_KEY:**
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### Paso 5: Crear Base de Datos PostgreSQL

1. En Render, haz clic en **"New +"** → **"PostgreSQL"**
2. Nombre: **eki-db**
3. Region: **Oregon (US West)**
4. Plan: **Free**
5. Haz clic en **"Create Database"**

### Paso 6: Conectar DB al Web Service

1. Ve a tu Web Service en Render
2. En **"Environment"**, agrega:
   - Variable: `DATABASE_URL`
   - Valor: Copia el **"Internal Database URL"** de tu PostgreSQL

### Paso 7: Deploy

1. Haz clic en **"Manual Deploy"** → **"Deploy latest commit"**
2. Espera 5-10 minutos (primera vez)
3. Cuando veas "Live", tu app está en línea! 🎉

Tu URL será: `https://eki-whatsapp-bot.onrender.com`

---

## 🔗 **PARTE 3: Configurar Webhook en Meta**

### Paso 1: Copiar URL del Webhook

Tu webhook URL es:
```
https://eki-whatsapp-bot.onrender.com/webhook/whatsapp/
```

### Paso 2: Configurar en Meta

1. Ve a tu app en Meta for Developers
2. WhatsApp → **Configuration**
3. En **"Webhooks"**, haz clic en **"Edit"**
4. **Callback URL**: `https://eki-whatsapp-bot.onrender.com/webhook/whatsapp/`
5. **Verify Token**: `eki_whatsapp_verify_token_2025`
6. Haz clic en **"Verify and Save"**

### Paso 3: Suscribirse a Eventos

En la misma página de Webhooks:

1. Busca **"Webhook fields"**
2. Marca estos eventos:
   - ✅ **messages** (mensajes entrantes)
   - ✅ **message_status** (estados de mensaje)
3. Haz clic en **"Save"**

---

## ✅ **PARTE 4: Probar Todo**

### Paso 1: Enviar mensaje de prueba

En Meta for Developers:

1. Ve a **"API Setup"**
2. Encuentra **"Send and receive messages"**
3. Pon tu número de teléfono (con código de país, ej: +573001234567)
4. Haz clic en **"Send message"**
5. Recibirás un mensaje de prueba en WhatsApp

### Paso 2: Responder al mensaje

1. Abre WhatsApp en tu celular
2. Responde al mensaje que recibiste
3. Deberías recibir una respuesta generada por IA 🤖

### Paso 3: Verificar en el Admin

1. Ve a: `https://eki-whatsapp-bot.onrender.com/admin/`
2. Login con tu superuser
3. Ve a **"Whatsapp logs"** para ver la conversación

---

## 🔧 **COMANDOS ÚTILES**

### Crear superuser en Render

1. Ve a tu Web Service en Render
2. Click en **"Shell"** (terminal)
3. Ejecuta:
```bash
python manage.py createsuperuser
```

### Ver logs en vivo

En Render:
1. Ve a tu Web Service
2. Click en **"Logs"**
3. Verás en tiempo real lo que pasa

### Reiniciar servicio

1. Click en **"Manual Deploy"**
2. Selecciona **"Clear build cache & deploy"**

---

## 📱 **PARTE 5: Migrar a Número Propio**

### Opción 1: Agregar número existente

1. En Meta for Developers → WhatsApp → **"API Setup"**
2. Click en **"Add phone number"**
3. Sigue el proceso de verificación (OTP)
4. Una vez verificado, actualiza `WHATSAPP_PHONE_ID` en Render

### Opción 2: Comprar número nuevo

1. Usa Twilio, Vonage o similar para comprar un número
2. Configúralo en WhatsApp Business API
3. Actualiza las credenciales

---

## 🐛 **Solución de Problemas**

### Webhook no verifica

- ✅ Verifica que `WHATSAPP_VERIFY_TOKEN` sea exactamente el mismo en .env y Meta
- ✅ Asegúrate de que la URL sea HTTPS (no HTTP)
- ✅ Prueba el endpoint: `https://tu-app.onrender.com/webhook/whatsapp/?hub.verify_token=eki_whatsapp_verify_token_2025&hub.challenge=test&hub.mode=subscribe`

### No recibo respuestas

- ✅ Verifica que OPENAI_API_KEY esté configurado
- ✅ Revisa los logs en Render
- ✅ Verifica que los eventos estén suscritos en Meta

### Error 500 en producción

- ✅ Revisa logs en Render
- ✅ Asegúrate de que `DEBUG=False`
- ✅ Verifica que todas las variables de entorno estén configuradas
- ✅ Ejecuta `python manage.py migrate` en Render Shell

### Token expiró

El token temporal expira en 24h. Para token permanente:

1. Meta for Developers → **Settings** → **Advanced**
2. **"System User Token"** → Generate
3. Permisos: `whatsapp_business_messaging`, `whatsapp_business_management`
4. Reemplaza en Render

---

## 📊 **Monitoreo**

### Costos

- **Render Free Tier**: 
  - 750 horas/mes gratis (suficiente para 24/7)
  - Se duerme después de 15 min sin actividad
  - Despierta en ~30 segundos

- **OpenAI**:
  - GPT-4o-mini: ~$0.15 por 1M tokens
  - Estimado: $5-10/mes con uso moderado

- **Meta WhatsApp**:
  - 1,000 conversaciones gratis/mes
  - Después: $0.005-0.009 por conversación

### Dashboard de Uso

- **OpenAI**: https://platform.openai.com/usage
- **Meta**: https://business.facebook.com/billing_hub/
- **Render**: https://dashboard.render.com/usage

---

## 🎯 **Checklist de Configuración**

- [ ] App creada en Meta for Developers
- [ ] Credenciales obtenidas (Token, Phone ID)
- [ ] Variables agregadas al .env local
- [ ] Webhook probado localmente (`test_webhook_meta.py`)
- [ ] Código subido a GitHub
- [ ] Web Service creado en Render
- [ ] PostgreSQL creado y conectado
- [ ] Variables de entorno configuradas en Render
- [ ] Deploy exitoso (status: Live)
- [ ] Webhook configurado en Meta
- [ ] Eventos suscritos (messages, message_status)
- [ ] Mensaje de prueba enviado y recibido
- [ ] Respuesta con IA funcionando
- [ ] Superuser creado en Render
- [ ] Admin accesible

---

¡Listo! Tu bot de WhatsApp con IA está en producción 🚀
