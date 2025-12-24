# 🔗 CONFIGURACIÓN META WHATSAPP + EKI

## 📋 GUÍA PASO A PASO

---

## 🎯 VENTAJA: SISTEMA DUAL

Tendrás **dos opciones** funcionando simultáneamente:

```
┌─────────────────────────────────────────┐
│          EKI SISTEMA DUAL               │
├─────────────────────────────────────────┤
│                                         │
│  📱 TWILIO WHATSAPP                     │
│  └─ Producción principal                │
│  └─ Content Templates con video         │
│  └─ $20-25/mes                          │
│                                         │
│  📱 META WHATSAPP BUSINESS API          │
│  └─ Backup/alternativa                  │
│  └─ Gratis hasta 1000 conversaciones    │
│  └─ $0/mes                              │
│                                         │
│  🤖 AGENTE IA (Function Calling)        │
│  └─ Funciona con ambos                  │
│  └─ Respuestas inteligentes             │
│                                         │
└─────────────────────────────────────────┘
```

---

## 📝 PASO 1: CONFIGURAR META BUSINESS

### 1.1 Crear Facebook Business Manager

🔗 https://business.facebook.com/

1. Clic en **"Crear cuenta"**
2. Nombre del negocio: **"Eki Educación"** (o el que prefieras)
3. Completa datos de la empresa

### 1.2 Agregar WhatsApp Business

1. En Business Manager → **Settings** (⚙️)
2. **Accounts** → **WhatsApp Accounts**
3. Clic en **"Add"** → **"Create a new WhatsApp Business Account"**
4. Nombre: **"Eki"**
5. Categoría: **Education**
6. Descripción: **"Asistente educativo inteligente"**

### 1.3 Configurar número de teléfono

**Opción A: Usar número existente**
- Debe ser número que NO esté en WhatsApp personal
- Recibirás código de verificación por SMS

**Opción B: Solicitar número nuevo**
- Meta puede proporcionar número virtual
- Proceso tarda 1-2 días

### 1.4 Crear App de Facebook

1. Ve a: https://developers.facebook.com/apps
2. **"Create App"** → **"Business"**
3. Nombre: **"Eki Assistant"**
4. Email de contacto: tu email

### 1.5 Agregar producto WhatsApp

1. En tu app → **"Add Product"**
2. Busca **"WhatsApp"** → **"Set Up"**
3. **Link** tu WhatsApp Business Account que creaste

---

## 🔑 PASO 2: OBTENER CREDENCIALES

### 2.1 Token de Acceso (Access Token)

1. En tu App → **WhatsApp** → **Getting Started**
2. Copia el **"Temporary access token"** (válido 24h)
3. Para producción, necesitas token permanente:
   - **Settings** → **Basic**
   - Genera **System User Access Token**

```
Token temporal (pruebas):
EAAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx (válido 24h)

Token permanente (producción):
EAAyyyyyyyyyyyyyyyyyyyyyyyyyyyy (nunca expira)
```

### 2.2 Phone Number ID

En la sección **"API Setup"**:

```
Phone Number ID: 123456789012345
WhatsApp Business Account ID: 987654321098765
```

### 2.3 Verify Token (para webhook)

**Crear uno tú mismo** (cualquier string aleatorio):

```
Ejemplo: eki_webhook_verify_token_2024_secret
```

---

## ⚙️ PASO 3: CONFIGURAR EN EKI

### 3.1 Actualizar archivo .env

```bash
# ============================================
# TWILIO (ya configurado)
# ============================================
TWILIO_ACCOUNT_SID=ACdfe1762471d825240c7ac5833cf36bf9
TWILIO_AUTH_TOKEN=tu_token_actual
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886

# ============================================
# META WHATSAPP (NUEVO)
# ============================================
META_WHATSAPP_TOKEN=EAAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
META_PHONE_NUMBER_ID=123456789012345
META_VERIFY_TOKEN=eki_webhook_verify_token_2024_secret
META_BUSINESS_ACCOUNT_ID=987654321098765

# ============================================
# CONFIGURACIÓN GENERAL
# ============================================
WHATSAPP_PROVIDER=dual  # dual, twilio, meta
```

### 3.2 Sistema detecta automáticamente

El webhook que ya tienes en `views.py` **ya soporta Meta**.

Solo necesitas actualizar el `.env` y el sistema detectará mensajes de ambos proveedores automáticamente.

---

## 🔧 PASO 4: CONFIGURAR WEBHOOK EN META

### 4.1 Exponer tu servidor

```bash
# Opción 1: ngrok (desarrollo)
ngrok http 8000

# Te dará una URL como:
https://abc123.ngrok.io
```

### 4.2 Configurar en Meta

1. En tu App → **WhatsApp** → **Configuration**
2. **Webhook** → **Edit**

```
Callback URL: https://abc123.ngrok.io/webhook/whatsapp/
Verify Token: eki_webhook_verify_token_2024_secret
```

3. **Verify and Save**

### 4.3 Suscribirse a eventos

Marca estas casillas:
- ✅ messages
- ✅ message_status
- ✅ messaging_postbacks (opcional)

---

## 🧪 PASO 5: PROBAR

### 5.1 Enviar mensaje de prueba desde Meta

1. En **API Setup** hay una sección de pruebas
2. Selecciona tu número
3. Clic en **"Send Message"**
4. Mensaje: "Hola desde Meta"

### 5.2 Verificar logs

```bash
# Ver logs en Django
python manage.py runserver

# O ver en admin
http://localhost:8000/admin/core/whatsapplog/
```

---

## 📊 COMPARACIÓN: TWILIO VS META

| Feature | Twilio | Meta (Gratis) |
|---------|--------|---------------|
| **Setup** | $20 | $0 |
| **Mensual** | $15-25 | $0 |
| **Mensajes gratis** | 0 | 1000 conv/mes |
| **Templates** | Content Templates | Message Templates |
| **Media** | Video/imagen | Video/imagen |
| **Botones** | ✅ | ✅ |
| **Aprobación** | 1-2 días | 1-2 días |
| **Límites** | Sin límite | 1000 conv/mes |

---

## 💰 COSTOS META WHATSAPP

### Tier Gratuito (Primeros 1000)
```
Conversaciones 1-1000/mes:  $0 (GRATIS!)
```

### Después de 1000 conversaciones
```
Service conversations:   $0.0525 c/u
Utility conversations:   $0.0105 c/u
Authentication:          $0.042 c/u
Marketing:               $0.084 c/u
```

**Ejemplo:** 5000 conversaciones/mes = ~$250-400/mes

**Recomendación:** Usa Meta para los primeros 1000, luego Twilio.

---

## 🎯 ESTRATEGIA RECOMENDADA

### Fase 1: Desarrollo/Pruebas
```
✅ Meta WhatsApp (gratis)
✅ Probar con 10-50 usuarios
✅ Ajustar sistema
```

### Fase 2: MVP (1-100 usuarios)
```
✅ Meta WhatsApp (gratis hasta 1000)
✅ Monitoring de conversaciones
```

### Fase 3: Escalamiento (100-1000 usuarios)
```
✅ Mantener Meta mientras sea gratis
✅ Preparar Twilio como backup
```

### Fase 4: Producción (1000+ usuarios)
```
✅ Migrar a Twilio ($20-25/mes fijo)
✅ Mantener Meta como alternativa
✅ Load balancing entre ambos
```

---

## 🔄 MIGRACIÓN AUTOMÁTICA

El sistema puede usar ambos automáticamente:

```python
# En settings.py o .env
WHATSAPP_PROVIDER = "dual"  # Usa el mejor según contexto

# O específico:
WHATSAPP_PROVIDER = "meta"    # Solo Meta
WHATSAPP_PROVIDER = "twilio"  # Solo Twilio
```

El webhook detecta de dónde viene el mensaje y responde por el mismo canal.

---

## 📋 CHECKLIST CONFIGURACIÓN META

### Requerimientos
- [ ] Facebook Business Manager creado
- [ ] WhatsApp Business Account creado
- [ ] Número de teléfono verificado
- [ ] Facebook App creada
- [ ] Producto WhatsApp agregado
- [ ] Token de acceso obtenido
- [ ] Phone Number ID copiado
- [ ] Verify Token creado

### Configuración Django
- [ ] .env actualizado con credenciales Meta
- [ ] Webhook configurado en Meta
- [ ] Suscripciones activadas
- [ ] Primer mensaje de prueba enviado
- [ ] Log verificado en admin

### Testing
- [ ] Mensaje desde Meta API Setup funciona
- [ ] Respuesta automática funciona
- [ ] Function Calling funciona
- [ ] Logs se guardan correctamente

---

## 🚨 TROUBLESHOOTING

### Error: "Webhook verification failed"
**Solución:** 
- Verifica que VERIFY_TOKEN en .env coincida exactamente
- Asegúrate que ngrok esté corriendo
- URL debe ser HTTPS

### Error: "Invalid access token"
**Solución:**
- Token temporal expira en 24h
- Genera System User Token permanente
- Verifica que copiaste completo

### Error: "Phone number not verified"
**Solución:**
- Completa verificación de número en Meta
- Puede tardar hasta 24h
- Usa número que NO esté en WhatsApp personal

### Mensajes no llegan
**Solución:**
- Verifica suscripciones en webhook
- Revisa logs de Django
- Confirma que el webhook está activo

---

## 📞 SOPORTE

### Meta Developer Support
- https://developers.facebook.com/support/
- Community: https://developers.facebook.com/community/

### Documentación
- WhatsApp Business API: https://developers.facebook.com/docs/whatsapp
- Cloud API: https://developers.facebook.com/docs/whatsapp/cloud-api
- Templates: https://developers.facebook.com/docs/whatsapp/message-templates

---

## ✅ PRÓXIMO PASO

**AHORA:**
1. Completa setup en Meta (pasos 1-2)
2. Copia credenciales
3. Actualiza .env
4. ¡Prueba primer mensaje!

**DESPUÉS:**
Cuando funcione Meta, tendrás:
```
✅ Sistema dual (Meta + Twilio)
✅ 1000 conversaciones gratis/mes (Meta)
✅ Backup con Twilio si excedes límite
✅ Agente IA funcionando en ambos
✅ Costo total: $0-25/mes según uso
```

---

## 💡 TIP FINAL

**Usa Meta para primeros 1000 usuarios → GRATIS!**

Después decide:
- ¿Más de 1000 conversaciones/mes? → Twilio ($20-25 fijo)
- ¿Menos de 1000? → Mantén Meta (gratis)
- ¿Necesitas ambos? → Sistema dual (mejor opción)

¡Meta te ahorra $20-25/mes en las primeras 1000 conversaciones! 💰
