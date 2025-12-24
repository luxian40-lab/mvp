# 🎯 GUÍA: UPGRADE TWILIO + WHATSAPP BUSINESS

## 📝 PASO A PASO PARA HOY

---

## 🔥 FASE 1: UPGRADE TWILIO (20-30 minutos)

### 1. Comprar número de WhatsApp Business

#### 🔗 Ir a Twilio Console
https://console.twilio.com/us1/develop/phone-numbers/manage/search

#### 💳 Pasos:
1. **Buy a Number** → WhatsApp Enabled
2. **Selecciona país:** Colombia (recomendado para tus estudiantes)
3. **Costo:**
   - Setup: $20 USD (una sola vez)
   - Mensual: ~$15 USD/mes
   - Mensajes: ~$0.005 - $0.01 c/u

4. **Comprar y guardar el número:**
   ```
   Ejemplo: +57XXXXXXXXX
   ```

#### ⚙️ Configurar número para WhatsApp
1. Ve a: https://console.twilio.com/us1/develop/sms/settings/whatsapp-senders
2. Clic en tu número nuevo
3. **Enable WhatsApp** → Seguir pasos de verificación
4. Facebook Business Manager (si te pide)

**⏰ Tiempo de aprobación:** 1-2 días hábiles

---

## 📋 FASE 2: CREAR PLANTILLAS (15 minutos crear, 1-2 días aprobar)

Mientras esperas el número, puedes crear plantillas que se aprobarán después.

### 🔗 Ir a Content Templates
https://console.twilio.com/us1/develop/sms/content-editor

### 📝 Plantilla 1: BIENVENIDA (Esencial)

**Clic en "Create New Content"**

```
Name: bienvenida_eki
Language: Spanish (es)
Template Type: Marketing (o Utility)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BODY (Texto):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

¡Hola {{1}}! 👋 Bienvenido a Eki

Soy tu asistente educativo inteligente. Puedo ayudarte con:

📊 Consultar tu progreso
📝 Ver tus tareas pendientes  
💡 Responder dudas de estudio
🎯 Recomendaciones personalizadas

¿En qué puedo ayudarte hoy?

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Variables:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{{1}} = nombre del estudiante

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OPCIONAL - Agregar media:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Header Type: Image o Video
Media URL: https://tu-imagen-o-video.com/bienvenida.mp4

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OPCIONAL - Botones:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Button 1: Ver mi progreso
Button 2: Ayuda
```

**Submit for Approval** ✅

---

### 📝 Plantilla 2: NUEVA CLASE (Recomendada)

```
Name: nueva_clase
Language: Spanish (es)
Template Type: Marketing

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BODY:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📚 ¡Nueva clase disponible, {{1}}!

Tema: {{2}}
Duración: {{3}}

👉 Responde aquí cuando estés listo para empezar

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Variables:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{{1}} = nombre
{{2}} = tema de la clase
{{3}} = duración

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Header (Video recomendado):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
URL del preview de la clase
```

**Submit for Approval** ✅

---

### 📝 Plantilla 3: RECORDATORIO (Útil)

```
Name: recordatorio_tarea
Language: Spanish (es)
Template Type: Utility

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BODY:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⏰ Recordatorio, {{1}}

Tienes pendiente: {{2}}
Fecha de vencimiento: {{3}}

💬 Responde si necesitas ayuda

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Variables:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{{1}} = nombre
{{2}} = descripción de la tarea
{{3}} = fecha de vencimiento
```

**Submit for Approval** ✅

---

## ⏰ TIEMPO DE APROBACIÓN

- **Plantillas simples (texto):** 24-48 horas
- **Plantillas con multimedia:** 2-3 días
- **Primera plantilla:** Puede tardar hasta 5 días

**💡 TIP:** Empieza con plantillas simples de texto, luego agrega multimedia.

---

## 📸 GUARDAR CONTENT SIDs

Después de crear cada plantilla, **COPIA** el Content SID:

```
bienvenida_eki → HXxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
nueva_clase → HXyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
recordatorio_tarea → HXzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz
```

**Guárdalos en un archivo temporal** para después agregarlos en Django Admin.

---

## 🔧 FASE 3: CONFIGURAR EN DJANGO (5 minutos)

### Actualizar .env con nuevo número

```bash
# Cuando tengas el número de producción
TWILIO_WHATSAPP_NUMBER=whatsapp:+57XXXXXXXXXX
```

### Agregar plantillas en Django Admin

1. Ve a: http://127.0.0.1:8000/admin/core/plantilla/
2. Crear 3 plantillas:

**Plantilla 1:**
```
Nombre interno: bienvenida
Tipo contenido: Texto
Proveedor: Twilio
Twilio Template SID: HXxxxxxxxx... (el que copiaste)
Twilio Variables: {"1": "nombre"}
Activa: ✅
```

**Plantilla 2:**
```
Nombre interno: nueva_clase
Tipo contenido: Video
Proveedor: Twilio
Twilio Template SID: HXyyyyyyyy...
Twilio Variables: {"1": "nombre", "2": "tema", "3": "duracion"}
URL Media: (si agregaste video en Twilio)
Activa: ✅
```

**Plantilla 3:**
```
Nombre interno: recordatorio
Tipo contenido: Texto
Proveedor: Twilio
Twilio Template SID: HXzzzzzzzz...
Twilio Variables: {"1": "nombre", "2": "tarea", "3": "fecha"}
Activa: ✅
```

---

## ⚡ MIENTRAS SE APRUEBAN LAS PLANTILLAS...

### ¡IMPLEMENTAR FUNCTION CALLING! (Hoy mismo)

Las plantillas tardan 1-2 días, pero Function Calling lo hacemos HOY:

```powershell
# Probar la demo
C:/Users/luxia/OneDrive/Escritorio/eki_mvp/.venv/Scripts/python.exe demo_function_calling.py
```

### Después integramos en el webhook (30 min)

Actualizar `core/ai_assistant.py` con las funciones automáticas.

---

## 📊 COSTOS TOTALES

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TWILIO PRODUCCIÓN
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Setup inicial:
├─ Número WhatsApp Business      $20 USD (una vez)
├─ Verificación Facebook         $0 (gratis)
└─ TOTAL SETUP                   $20 USD

Mensual:
├─ Número WhatsApp              $15 USD/mes
├─ Conversaciones (1000 msg)    $5-10 USD/mes
└─ TOTAL MENSUAL                $20-25 USD/mes

Por mensaje:
├─ Plantillas (templates)       $0.005 - $0.01
├─ Mensajes normales (IA)       $0.005
└─ Promedio                     ~$0.007/mensaje

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OPENAI (Function Calling)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GPT-4o-mini:
├─ Input: $0.15 / 1M tokens
├─ Output: $0.60 / 1M tokens
└─ ~1000 conversaciones          $0.50-1.00 USD/mes

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TOTAL MENSUAL (100 estudiantes activos)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Setup:                          $20 USD (una vez)
Mensual operación:              $21-26 USD/mes
Por estudiante:                 $0.21-0.26 USD/mes

¡MUY ECONÓMICO! 🎉
```

---

## ✅ CHECKLIST DE HOY

### Parte 1: Twilio (hacer primero)
- [ ] Comprar número de WhatsApp Business
- [ ] Configurar número para WhatsApp
- [ ] Crear plantilla "bienvenida_eki"
- [ ] Crear plantilla "nueva_clase"
- [ ] Crear plantilla "recordatorio_tarea"
- [ ] Copiar Content SIDs
- [ ] Actualizar .env con nuevo número

### Parte 2: Function Calling (mientras esperas aprobación)
- [ ] Probar demo_function_calling.py
- [ ] Entender cómo funciona
- [ ] Integrar en ai_assistant.py
- [ ] Probar localmente

### Parte 3: Django Admin (después de aprobación)
- [ ] Agregar plantillas en admin con SIDs
- [ ] Probar envío con template_service.py
- [ ] Verificar logs

---

## 🚨 PROBLEMAS COMUNES

### "No puedo comprar número de WhatsApp"
**Solución:** Verifica que tu cuenta Twilio esté verificada (tarjeta de crédito agregada).

### "Plantilla rechazada"
**Solución:** 
- No uses lenguaje promocional agresivo
- Evita emojis excesivos en primera plantilla
- Marca como "Utility" en vez de "Marketing" si te rechazan

### "Número de WhatsApp tarda mucho"
**Solución:** Puede tardar 1-2 días. Mientras tanto, usa el Sandbox.

---

## 🎯 RESULTADO ESPERADO

Al final del día:

```
✅ Número de WhatsApp Business comprado
✅ 3 plantillas creadas (pendientes aprobación)
✅ Function Calling implementado y probando
✅ Django actualizado con configuración

En 1-2 días:
✅ Plantillas aprobadas
✅ Content SIDs en Django Admin
✅ Sistema completo funcionando
```

---

## 📞 SOPORTE

**Twilio Support:**
- https://support.twilio.com
- Chat en vivo en la consola

**Documentación:**
- WhatsApp Business API: https://www.twilio.com/docs/whatsapp
- Content Templates: https://www.twilio.com/docs/content
- Variables: https://www.twilio.com/docs/content/using-variables

---

## 🚀 SIGUIENTE PASO

**AHORA MISMO:** Ve a Twilio y compra el número.

Mientras lo compras, te explico Function Calling! 💪
