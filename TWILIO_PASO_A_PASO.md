# 📱 GUÍA VISUAL: CONFIGURAR WEBHOOK EN TWILIO (Paso a Paso)

## 🎯 OPCIÓN 1: WhatsApp Sandbox (Para pruebas - MÁS FÁCIL)

### PASO 1: Ir a WhatsApp Sandbox

```
1. Estás en Twilio Console (console.twilio.com)

2. En el menú lateral izquierdo, busca:
   
   Messaging (con ícono de mensaje 💬)
   └─ Try it out
      └─ Send a WhatsApp message
   
   O ve directo a esta URL:
   https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn
```

### PASO 2: Verás esta pantalla

```
┌─────────────────────────────────────────────────────────┐
│  Send a WhatsApp message                                │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  1. Join your Sandbox                                   │
│     Send "join [código]" to:                            │
│     +1 415 523 8886                                     │
│                                                         │
│  2. Send messages from your sandbox                     │
│     [Aquí hay una tabla con tu número]                  │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### PASO 3: Ir a Configuración del Sandbox

```
En esa misma pantalla, arriba a la derecha verás:

┌──────────────────────────────────┐
│  Sandbox Settings  [botón gris]  │
└──────────────────────────────────┘

¡HAZ CLIC AHÍ! ←
```

### PASO 4: Configurar la Webhook

Ahora verás esta sección:

```
┌─────────────────────────────────────────────────────────┐
│  SANDBOX CONFIGURATION                                  │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  WHEN A MESSAGE COMES IN                                │
│  ┌───────────────────────────────────────────────────┐ │
│  │ https://                                          │ │  ← Pega tu URL aquí
│  └───────────────────────────────────────────────────┘ │
│                                                         │
│  [HTTP POST ▼]  ← Asegúrate que diga POST              │
│                                                         │
│  STATUS CALLBACK URL (opcional - déjalo vacío)         │
│  ┌───────────────────────────────────────────────────┐ │
│  │                                                   │ │
│  └───────────────────────────────────────────────────┘ │
│                                                         │
│  [ Save ]  ← Clic aquí al final                        │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### PASO 5: ¿Qué URL poner?

**PRIMERO necesitas tu URL de ngrok:**

```powershell
# En PowerShell (nueva ventana):
cd C:/Users/luxia/OneDrive/Escritorio/eki_mvp

# Si tienes ngrok instalado:
C:\ngrok\ngrok.exe http 8000

# Verás algo así:
Forwarding: https://1a2b-3c4d-5e6f.ngrok.io -> http://localhost:8000
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
            COPIA ESTA PARTE
```

**LUEGO pega en Twilio:**

```
En el campo "WHEN A MESSAGE COMES IN":

https://1a2b-3c4d-5e6f.ngrok.io/webhook/whatsapp/
                                ^^^^^^^^^^^^^^^^^^
                                NO OLVIDES ESTA PARTE
```

**Ejemplo completo:**
```
https://abc123def456.ngrok.io/webhook/whatsapp/
```

### PASO 6: Verificar configuración

```
✅ URL debe terminar en: /webhook/whatsapp/
✅ Método debe ser: HTTP POST
✅ Clic en "Save"
```

---

## 🎯 OPCIÓN 2: WhatsApp Business (Después de upgrade)

### PASO 1: Ir a tus números

```
1. Menú lateral izquierdo:
   
   Phone Numbers (ícono 📞)
   └─ Manage
      └─ Active numbers

   O directo:
   https://console.twilio.com/us1/develop/phone-numbers/manage/active
```

### PASO 2: Seleccionar tu número WhatsApp

```
Verás una tabla con tus números:

┌────────────────────────────────────────────────────────┐
│  FRIENDLY NAME    │  NUMBER          │  CAPABILITIES   │
├────────────────────────────────────────────────────────┤
│  My WhatsApp      │ +1 415 XXX XXXX  │ SMS Voice MMS   │ ← Clic aquí
└────────────────────────────────────────────────────────┘
```

### PASO 3: Configurar Messaging

Scroll hacia abajo hasta ver:

```
┌─────────────────────────────────────────────────────────┐
│  Messaging Configuration                                │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  CONFIGURE WITH                                         │
│  ○ Webhooks, TwiML Bins, Functions...                   │  ← Selecciona este
│  ○ Messaging Service                                    │
│                                                         │
│  A MESSAGE COMES IN                                     │
│  ┌───────────────────────────────────────────────────┐ │
│  │ https://                                          │ │  ← Tu URL aquí
│  └───────────────────────────────────────────────────┘ │
│                                                         │
│  [HTTP POST ▼]                                          │
│                                                         │
│  [ Save ]                                               │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 🚨 SI NO VES ESTAS OPCIONES

### Problema 1: "No encuentro Sandbox Settings"

**Solución:**
```
1. Ve directamente a:
   https://console.twilio.com/us1/develop/sms/settings/whatsapp-sandbox

2. O en menú lateral:
   Messaging → Settings → WhatsApp sandbox settings
```

### Problema 2: "No tengo números WhatsApp"

**Solución:**
```
Usa el Sandbox primero (Opción 1)
El Sandbox es gratis y funciona igual para pruebas
```

### Problema 3: "¿Qué poner en URL?"

**Solución:**
```
FORMATO: https://[TU-NGROK-URL]/webhook/whatsapp/

Ejemplos correctos:
✅ https://abc123.ngrok.io/webhook/whatsapp/
✅ https://1a2b3c4d.ngrok-free.app/webhook/whatsapp/

Ejemplos INCORRECTOS:
❌ https://abc123.ngrok.io (falta /webhook/whatsapp/)
❌ http://abc123.ngrok.io/webhook/whatsapp/ (debe ser HTTPS)
❌ https://abc123.ngrok.io/whatsapp (falta /webhook/)
```

---

## 📋 CHECKLIST ANTES DE GUARDAR

Antes de hacer clic en "Save", verifica:

```
✅ URL empieza con https:// (con S)
✅ URL termina con /webhook/whatsapp/
✅ Método es HTTP POST (no GET)
✅ Django está corriendo (python manage.py runserver)
✅ ngrok está corriendo (ngrok http 8000)
```

---

## 🧪 PROBAR QUE FUNCIONA

### Después de guardar:

**1. Unirse al Sandbox (primera vez)**
```
Desde tu WhatsApp, envía a +1 415 523 8886:
join [código que te muestra Twilio]

Ejemplo: join happy-lion
```

**2. Enviar mensaje de prueba**
```
Envía: Hola

Deberías recibir respuesta automática en 5-10 segundos
```

**3. Verificar en Django**
```
En la terminal de Django verás:
"POST /webhook/whatsapp/ HTTP/1.1" 200

En admin:
http://localhost:8000/admin/core/whatsapplog/
```

---

## 🎯 RESUMEN ULTRA-RÁPIDO

**Si estás en Twilio AHORA:**

```
1. Busca en menú: Messaging → Try it out → Send a WhatsApp message
2. Clic en "Sandbox Settings" (arriba derecha)
3. En "WHEN A MESSAGE COMES IN":
   - Pega tu URL: https://[ngrok]/webhook/whatsapp/
   - Método: POST
4. Save
5. Unirse al sandbox: Envía "join [código]" desde WhatsApp
6. Probar: Envía "Hola"
7. ¡Listo! Deberías recibir respuesta
```

---

## 💡 SI NECESITAS ngrok PRIMERO

**Antes de configurar en Twilio:**

```powershell
# Terminal 1: Inicia Django
cd C:/Users/luxia/OneDrive/Escritorio/eki_mvp
.venv/Scripts/Activate.ps1
python manage.py runserver

# Terminal 2: Inicia ngrok
# Descarga ngrok de: https://ngrok.com/download
# Luego ejecuta:
ngrok http 8000

# COPIA LA URL QUE APARECE
# Ejemplo: https://abc123.ngrok.io
```

**LUEGO vuelve a Twilio y pega:**
```
https://abc123.ngrok.io/webhook/whatsapp/
```

---

## 📞 ¿DÓNDE ESTÁS AHORA?

Dime qué pantalla ves en Twilio y te digo exactamente qué hacer:

**A)** ¿Ves "Send a WhatsApp message" con un número +1 415?
**B)** ¿Ves una lista de tus números de teléfono?
**C)** ¿Ves otra cosa?

¡Dime qué ves y te guío paso a paso! 👇
