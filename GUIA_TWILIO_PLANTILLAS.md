# 🚀 GUÍA COMPLETA: Twilio WhatsApp + Plantillas + Render
**Configuración paso a paso con Content Templates**

---

## 📋 **PARTE 1: Configurar Twilio WhatsApp**

### Paso 1: Crear cuenta en Twilio

1. Ve a: https://www.twilio.com/try-twilio
2. Regístrate (recibirás $15 USD de crédito gratis)
3. Verifica tu email y número de teléfono

### Paso 2: Obtener Credenciales

En el dashboard de Twilio:

1. Ve a: https://console.twilio.com/
2. Copia estas credenciales:
   - **Account SID**: `ACxxxxxxxxxxxxxxxx`
   - **Auth Token**: Click en "Show" para verlo

3. Agrega a tu `.env`:
```bash
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=tu_auth_token_aqui
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886  # Sandbox inicialmente
```

### Paso 3: Activar WhatsApp Sandbox (Para Pruebas)

1. Ve a: https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn
2. Verás un código como: `join happy-dog-1234`
3. En tu WhatsApp, envía ese mensaje a: **+1 (415) 523-8886**
4. Recibirás confirmación: "You are now in the Twilio Sandbox"

⚠️ **NOTA**: El sandbox es solo para pruebas. Para producción necesitas un número aprobado.

---

## 📝 **PARTE 2: Crear Plantillas (Content Templates)**

Las plantillas con video/imágenes se crean en Twilio Console.

### Paso 1: Ir a Content Templates

1. Ve a: https://console.twilio.com/us1/develop/sms/content-editor
2. Click en **"Create new Content"**

### Paso 2: Tipos de Plantillas

#### **Plantilla Básica (Texto)**
```
Tipo: WhatsApp
Nombre: bienvenida_estudiante
Idioma: Spanish (es)

Contenido:
¡Hola {{1}}! 👋

Bienvenido a Eki, tu plataforma educativa.

Estamos aquí para apoyarte en tu aprendizaje.

¿En qué podemos ayudarte hoy?
```

#### **Plantilla con Imagen**
```
Tipo: WhatsApp
Nombre: clase_matematicas
Idioma: Spanish (es)

Media: [Subir imagen o video]
URL: https://tu-servidor.com/static/videos/clase1.mp4

Texto:
📚 Nueva Clase Disponible

Hola {{1}}, tu clase de {{2}} ya está lista.

Toca el video para verla 👆
```

#### **Plantilla con Botones**
```
Tipo: WhatsApp
Nombre: menu_principal
Idioma: Spanish (es)

Texto:
Hola {{1}}, ¿qué necesitas?

Botones:
[Ver mi progreso]
[Mis tareas]
[Ayuda]
```

### Paso 3: Variables en Plantillas

- `{{1}}` = Primer parámetro (generalmente el nombre)
- `{{2}}` = Segundo parámetro
- `{{3}}` = Tercer parámetro, etc.

Ejemplo en Django:
```python
# Enviar plantilla con variables
client.messages.create(
    content_sid='HXxxxxxxxxxxx',  # SID de la plantilla
    content_variables={
        "1": "Juan",       # {{1}}
        "2": "Matemáticas" # {{2}}
    },
    from_='whatsapp:+14155238886',
    to='whatsapp:+573001234567'
)
```

### Paso 4: Aprobar Plantillas

1. Después de crear, Twilio las revisa (1-2 días)
2. Estado: **Pending** → **Approved**
3. Una vez aprobada, recibirás un **Content SID**: `HXxxxxxxxxxxx`

⚠️ **IMPORTANTE**: Solo las plantillas aprobadas pueden enviarse fuera del sandbox.

---

## 🎨 **PARTE 3: Gestionar Plantillas desde Django**

Voy a crear un sistema para que gestiones plantillas desde el admin.

### Modelo de Plantilla Mejorado

Las plantillas ahora tendrán:
- Nombre interno (para ti)
- Content SID de Twilio (HXxxx...)
- Variables que usa ({{1}}, {{2}}, etc.)
- Tipo (texto, imagen, video)
- Preview del mensaje

---

## 🔗 **PARTE 4: Configurar Webhook de Twilio**

### Diferencia entre Meta y Twilio Webhooks

**Meta WhatsApp**: JSON complejo con `entry[].changes[]`
**Twilio**: Form data simple con `Body`, `From`, `MessageSid`

### Paso 1: Actualizar Webhook

Ya tenemos el endpoint `/webhook/whatsapp/` pero necesita soportar ambos formatos.

### Paso 2: Configurar en Twilio Console

1. Ve a: https://console.twilio.com/us1/develop/sms/settings/whatsapp-sandbox
2. En **"When a message comes in"**:
   ```
   https://tu-app.onrender.com/webhook/whatsapp/
   ```
3. Método: **POST**
4. Haz clic en **"Save"**

### Paso 3: Probar localmente con ngrok

```bash
# Terminal 1: Django
python manage.py runserver

# Terminal 2: ngrok
.\ngrok.exe http 8000

# Copia la URL de ngrok y configúrala en Twilio
```

---

## 🚀 **PARTE 5: Deploy en Render**

### Configuración para Twilio

En Render, agrega estas variables de entorno:

```bash
# Twilio Configuration
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=tu_auth_token
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886

# OpenAI (para IA)
OPENAI_API_KEY=sk-proj-b84YIv...

# Django
DJANGO_DEBUG=False
SECRET_KEY=<genera uno>
ALLOWED_HOSTS=tu-app.onrender.com
CSRF_TRUSTED_ORIGINS=https://tu-app.onrender.com
```

Mismo proceso que antes:
1. Código a GitHub
2. Crear Web Service en Render
3. PostgreSQL
4. Deploy

---

## 📱 **PARTE 6: Número de Producción (Post-Sandbox)**

### Opción 1: Comprar Número de Twilio

1. Ve a: https://console.twilio.com/us1/develop/phone-numbers/buy
2. Filtra por: **WhatsApp Enabled**
3. Selecciona país (Colombia: +57)
4. Costo: ~$1-2 USD/mes

### Opción 2: Usar tu número existente

1. Ve a: https://console.twilio.com/us1/develop/sms/settings/whatsapp-sender
2. Click **"Add new sender"**
3. Sigue el proceso de verificación
4. Twilio revisará (2-5 días)

⚠️ **Requisitos para aprobación**:
- Negocio registrado
- Plantillas aprobadas
- Caso de uso claro (educación)
- Política de privacidad

---

## 📋 **PLANTILLAS RECOMENDADAS PARA EKI**

### 1. Bienvenida
```
Nombre: eki_bienvenida
Variables: {{1}} = nombre

¡Hola {{1}}! 👋

Bienvenido a Eki, tu asistente educativo.

Puedo ayudarte con:
📊 Tu progreso
📝 Tareas pendientes
💬 Dudas de estudio

Escríbeme lo que necesites.
```

### 2. Notificación de Clase con Video
```
Nombre: eki_clase_disponible
Media: Video URL
Variables: {{1}} = nombre, {{2}} = materia

📚 ¡Nueva Clase!

Hola {{1}}, tu clase de {{2}} ya está lista.

👆 Toca el video para verla.

¿Tienes dudas? Escríbeme.
```

### 3. Recordatorio de Tarea
```
Nombre: eki_recordatorio_tarea
Variables: {{1}} = nombre, {{2}} = tarea, {{3}} = fecha

⏰ Recordatorio

{{1}}, tienes pendiente:

📝 {{2}}
🗓️ Vence: {{3}}

¡No lo olvides!
```

### 4. Progreso Semanal con Imagen
```
Nombre: eki_progreso_semanal
Media: Gráfico de progreso
Variables: {{1}} = nombre, {{2}} = porcentaje

🎯 Tu Progreso Semanal

{{1}}, has completado el {{2}}% de tus actividades.

¡Vas muy bien! Sigue así 💪
```

---

## 🎥 **PARTE 7: Subir Videos/Imágenes**

### Opción 1: Usar Twilio Media Storage

```python
# Subir media a Twilio
from twilio.rest import Client

client = Client(account_sid, auth_token)

# Upload
media = client.messages.media.create(
    media_url='https://ejemplo.com/video.mp4'
)

print(media.sid)  # MExxxxxxxxx
```

### Opción 2: Usar tu propio servidor

1. Sube videos/imágenes a `/static/media/`
2. En producción: AWS S3, Cloudinary, o similar
3. Usa la URL pública en las plantillas

### Opción 3: YouTube/Vimeo

Para videos largos, usa enlaces de YouTube:
```
Hola {{1}}, aquí está tu clase:

https://youtube.com/watch?v=ABC123

¿Dudas? Escríbeme.
```

---

## 🧪 **SCRIPTS DE PRUEBA**

Ya tienes configurado para probar con Twilio. Voy a crear nuevos scripts específicos.

---

## 📊 **COSTOS ESTIMADOS**

### Twilio
- **Sandbox**: Gratis (solo pruebas)
- **Número WhatsApp**: $1-2/mes
- **Mensajes entrantes**: Gratis
- **Mensajes salientes**: 
  - Template messages: $0.005 USD c/u
  - Session messages: $0.005 USD c/u
  - Conversación 24h: $0.01-0.02 USD

### OpenAI
- **GPT-4o-mini**: $0.15 por 1M tokens
- **Estimado**: $5-10/mes

### Render
- **Free Tier**: Gratis (750h/mes)
- **PostgreSQL**: Gratis

**Total estimado**: $15-30 USD/mes para empezar

---

## 🎯 **CHECKLIST DE CONFIGURACIÓN**

### Fase 1: Sandbox (Pruebas)
- [ ] Cuenta Twilio creada
- [ ] Credenciales obtenidas
- [ ] Sandbox activado (join message)
- [ ] Variables en .env
- [ ] Webhook probado localmente
- [ ] Prueba de envío exitosa

### Fase 2: Plantillas
- [ ] 3-5 plantillas creadas en Twilio
- [ ] Plantillas enviadas para aprobación
- [ ] Content SIDs obtenidos
- [ ] Plantillas probadas en sandbox

### Fase 3: Producción
- [ ] Código en GitHub
- [ ] Deploy en Render
- [ ] PostgreSQL conectado
- [ ] Webhook configurado en Twilio
- [ ] Número de producción (post-sandbox)
- [ ] Plantillas aprobadas
- [ ] Prueba end-to-end exitosa

---

## 🆘 **SOPORTE**

- **Twilio Console**: https://console.twilio.com/
- **Twilio Docs**: https://www.twilio.com/docs/whatsapp
- **Content Templates**: https://www.twilio.com/docs/content
- **Pricing**: https://www.twilio.com/whatsapp/pricing

---

¡Listo para empezar con Twilio! 🚀
