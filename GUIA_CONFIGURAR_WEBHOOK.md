# 🔗 GUÍA COMPLETA: CONFIGURAR WEBHOOK DE WHATSAPP

## ✅ PASO 1: Tu código de webhook (YA LO TIENES)

Tu archivo `core/views.py` ya tiene la función `whatsapp_webhook` ✅
Tu archivo `mvp_project/urls.py` ya tiene la ruta configurada ✅

---

## 🚀 PASO 2: Exponer tu servidor local (ngrok)

### ¿Qué es ngrok?
Crea un túnel HTTPS para que Twilio/Meta pueda enviar mensajes a tu localhost.

### Instalación ngrok:

**Opción A: Descargar ejecutable**
```
1. Ve a: https://ngrok.com/download
2. Descarga para Windows
3. Descomprime ngrok.exe
4. Mueve a carpeta fácil: C:\ngrok\ngrok.exe
```

**Opción B: Con Chocolatey (si lo tienes)**
```powershell
choco install ngrok
```

### Uso de ngrok:

```powershell
# 1. Abre PowerShell NUEVA ventana (deja Django corriendo en otra)
# 2. Ejecuta ngrok
C:\ngrok\ngrok.exe http 8000

# O si instalaste con Chocolatey:
ngrok http 8000
```

**Salida esperada:**
```
ngrok

Session Status                online
Account                       Free
Version                       3.x.x
Region                        United States (us)
Latency                       45ms
Web Interface                 http://127.0.0.1:4040
Forwarding                    https://abc123def.ngrok.io -> http://localhost:8000

Connections                   ttl     opn     rt1     rt5     p50     p90
                              0       0       0.00    0.00    0.00    0.00
```

**COPIA LA URL HTTPS:** `https://abc123def.ngrok.io`

---

## 🔧 PASO 3: Configurar Webhook en Twilio Console

### Para Twilio WhatsApp Sandbox:

```
1. Ve a: https://console.twilio.com/us1/develop/sms/settings/whatsapp-sandbox

2. En "SANDBOX CONFIGURATION":
   
   WHEN A MESSAGE COMES IN:
   ┌──────────────────────────────────────────────┐
   │ https://abc123def.ngrok.io/webhook/whatsapp/ │  ← Tu URL de ngrok + /webhook/whatsapp/
   └──────────────────────────────────────────────┘
   
   Method: POST  ← Importante
   
3. Clic en "Save"
```

### Para Twilio WhatsApp Business (después de upgrade):

```
1. Ve a: https://console.twilio.com/us1/develop/sms/senders

2. Selecciona tu número WhatsApp

3. En "Messaging Configuration":
   
   WHEN A MESSAGE COMES IN:
   ┌──────────────────────────────────────────────┐
   │ https://abc123def.ngrok.io/webhook/whatsapp/ │
   └──────────────────────────────────────────────┘
   
   Method: POST
   
4. Clic en "Save"
```

---

## 🔧 PASO 4: Configurar Webhook en Meta WhatsApp (si usas Meta)

### En Meta Business Manager:

```
1. Ve a: https://developers.facebook.com/apps

2. Selecciona tu app → WhatsApp → Configuration

3. En "Webhook":
   
   Callback URL:
   ┌──────────────────────────────────────────────┐
   │ https://abc123def.ngrok.io/webhook/whatsapp/ │
   └──────────────────────────────────────────────┘
   
   Verify Token:
   ┌────────────────────────────────────┐
   │ eki_whatsapp_verify_token_2025     │  ← Este está en tu settings.py
   └────────────────────────────────────┘
   
4. Clic en "Verify and Save"

5. Subscribe to webhook fields:
   ☑ messages
   ☑ message_status
   
6. Save
```

---

## ✅ PASO 5: Verificar que Django esté corriendo

```powershell
# En tu terminal de Django (debe estar activo)
python manage.py runserver

# Debería mostrar:
# Starting development server at http://127.0.0.1:8000/
# Quit the server with CTRL-BREAK.
```

---

## 🧪 PASO 6: Probar la Webhook

### Test 1: Verificar que tu webhook responde

```powershell
# En PowerShell (nueva ventana)
curl http://localhost:8000/webhook/whatsapp/?hub.verify_token=eki_whatsapp_verify_token_2025&hub.challenge=test123

# Debería responder: test123
```

### Test 2: Enviar mensaje de prueba desde WhatsApp

```
1. Desde tu celular, abre WhatsApp
2. Envía mensaje al número Sandbox de Twilio
3. Escribe: "Hola"
```

### Test 3: Verificar logs en Django

```
# En la terminal de Django verás:
POST /webhook/whatsapp/ HTTP/1.1" 200
```

### Test 4: Verificar en Admin

```
1. Ve a: http://localhost:8000/admin/core/whatsapplog/
2. Deberías ver:
   - Mensaje INCOMING: "Hola"
   - Mensaje SENT: Respuesta de IA
```

---

## 🔍 PASO 7: Debugging (si algo falla)

### Ver logs detallados de ngrok:

```
1. Abre navegador
2. Ve a: http://localhost:4040
3. Verás todas las peticiones que llegan a tu webhook
```

### Ver logs de Django:

```
# En la terminal de Django verás cada petición:
[23/Dec/2025 10:30:15] "POST /webhook/whatsapp/ HTTP/1.1" 200 15
```

### Errores comunes:

**Error 1: "403 Forbidden"**
```
Causa: Token de verificación incorrecto
Solución: Verifica que el verify_token en Meta/Twilio sea: eki_whatsapp_verify_token_2025
```

**Error 2: "Connection refused"**
```
Causa: Django no está corriendo o ngrok apunta mal
Solución: 
  1. Verifica que Django esté en http://localhost:8000
  2. Verifica que ngrok esté corriendo
```

**Error 3: "CSRF verification failed"**
```
Causa: Tu webhook tiene @csrf_exempt decorador faltante
Solución: Ya está en tu código (whatsapp_webhook tiene @csrf_exempt)
```

**Error 4: No llegan mensajes**
```
Causa: Webhook no configurado correctamente
Solución:
  1. Verifica URL en Twilio/Meta: https://tu-ngrok.io/webhook/whatsapp/
  2. Verifica que sea POST (no GET)
  3. Verifica que ngrok esté corriendo
```

---

## 📋 CHECKLIST COMPLETO

Antes de probar, verifica:

```
✅ Django corriendo: python manage.py runserver
✅ ngrok corriendo: ngrok http 8000
✅ URL de ngrok copiada (https://xxx.ngrok.io)
✅ Webhook configurado en Twilio/Meta con tu URL de ngrok
✅ URL incluye /webhook/whatsapp/ al final
✅ Método configurado como POST
✅ Verify token: eki_whatsapp_verify_token_2025 (para Meta)
```

---

## 🎯 COMANDOS COMPLETOS PARA EJECUTAR AHORA

### Terminal 1: Django

```powershell
# Activar entorno
C:/Users/luxia/OneDrive/Escritorio/eki_mvp/.venv/Scripts/Activate.ps1

# Ir a carpeta del proyecto
cd C:/Users/luxia/OneDrive/Escritorio/eki_mvp

# Ejecutar servidor
python manage.py runserver
```

### Terminal 2: ngrok

```powershell
# Ejecutar ngrok (ajusta la ruta si instalaste en otro lugar)
C:\ngrok\ngrok.exe http 8000

# COPIA LA URL QUE APARECE: https://xxxxx.ngrok.io
```

### Terminal 3: Tests

```powershell
# Activar entorno
C:/Users/luxia/OneDrive/Escritorio/eki_mvp/.venv/Scripts/Activate.ps1

# Test de verificación
curl http://localhost:8000/webhook/whatsapp/?hub.verify_token=eki_whatsapp_verify_token_2025&hub.challenge=test123

# Debería responder: test123
```

---

## 🚀 FLUJO COMPLETO DESPUÉS DE CONFIGURAR

```
1. Usuario envía mensaje por WhatsApp
   ↓
2. Twilio/Meta recibe mensaje
   ↓
3. Twilio/Meta envía a tu webhook: https://tu-ngrok.io/webhook/whatsapp/
   ↓
4. ngrok reenvía a: http://localhost:8000/webhook/whatsapp/
   ↓
5. Django recibe en views.py → whatsapp_webhook()
   ↓
6. Guarda en WhatsappLog (INCOMING)
   ↓
7. IA procesa con OpenAI
   ↓
8. Envía respuesta a Twilio/Meta
   ↓
9. Usuario recibe respuesta en WhatsApp
   ↓
10. Guarda en WhatsappLog (SENT)
```

---

## 💡 TIPS IMPORTANTES

### 1. ngrok es temporal
- La URL cambia cada vez que reinicias ngrok
- Debes actualizar la webhook en Twilio/Meta cada vez
- Solución: Upgrade a ngrok Pro ($10/mes) para URL fija
- O usa un servidor real (Render, Heroku, etc.)

### 2. Para producción
- No uses ngrok
- Despliega en Render.com / Heroku / AWS
- Usa tu dominio real: https://eki.com/webhook/whatsapp/

### 3. Seguridad
- El verify token previene acceso no autorizado
- CSRF exempt solo para webhooks
- En producción, valida que peticiones vengan de Twilio/Meta

---

## 🔥 ALTERNATIVA: Sin ngrok (solo para testing local)

Si no quieres usar ngrok, puedes usar otros servicios similares:

**Opción A: LocalTunnel**
```powershell
npm install -g localtunnel
lt --port 8000
```

**Opción B: Serveo**
```powershell
ssh -R 80:localhost:8000 serveo.net
```

**Opción C: Pagekite**
```powershell
pagekite.py 8000 yourname.pagekite.me
```

Pero **ngrok es el más recomendado** por su estabilidad.

---

## ✅ SIGUIENTE PASO

Una vez configurado todo:

1. **Envía mensaje de prueba desde WhatsApp**
2. **Verifica que llegue a tu webhook** (logs de Django)
3. **Verifica que la IA responda** (recibes respuesta en WhatsApp)
4. **Verifica logs en admin** (http://localhost:8000/admin/core/whatsapplog/)

Si todo funciona, ¡webhook configurada! 🎉

Entonces puedes proceder a:
- Enviar mensajes proactivos con `test_sistema_completo.py`
- Crear estudiantes y que reciban bienvenida automática
- Programar recordatorios
