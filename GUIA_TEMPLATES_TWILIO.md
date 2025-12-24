# 📱 GUÍA: Crear Templates en Twilio y Enviar Mensajes Proactivos

## 🎯 PASO 1: Crear Templates en Consola Twilio (15 min)

### 1.1 Acceder a Content Template Editor

```
1. Ve a: https://console.twilio.com/
2. Login con tu cuenta
3. En el menú lateral: Messaging → Content Editor
   O directo: https://console.twilio.com/us1/develop/sms/content-editor
4. Clic en "Create new template"
```

### 1.2 Crear Template "Bienvenida"

**Configuración:**

```
Template Name: bienvenida_estudiante
Language: Spanish (es)
Category: UTILITY (para notificaciones educativas)
```

**Content (Cuerpo del mensaje):**

```
¡Hola {{1}}! 👋 Bienvenido a Eki Educación.

Soy tu asistente virtual inteligente. Puedo ayudarte con:

✅ Consultar tus tareas pendientes
✅ Ver tu horario de clases
✅ Revisar tu progreso académico
✅ Recordatorios importantes

Responde este mensaje para empezar a conversar.
```

**Variables:**
- `{{1}}` = Nombre del estudiante

**Footer (opcional):**
```
Eki - Tu asistente educativo
```

**Buttons (opcional):**
- Quick Reply: "Ver tareas"
- Quick Reply: "Horario"

**Submit:**
- Clic en "Submit for approval"
- Esperar 1-2 días aprobación

---

### 1.3 Crear Template "Recordatorio Clase"

**Configuración:**

```
Template Name: recordatorio_clase
Language: Spanish (es)
Category: UTILITY
```

**Content:**

```
¡Hola {{1}}! 🎓

Recordatorio: Tienes clase de {{2}} hoy a las {{3}}.

📍 Tema: {{4}}

¿Necesitas ayuda con algo antes de la clase?
```

**Variables:**
- `{{1}}` = Nombre
- `{{2}}` = Materia
- `{{3}}` = Hora
- `{{4}}` = Tema

---

### 1.4 Crear Template "Tarea Nueva"

**Configuración:**

```
Template Name: tarea_nueva
Language: Spanish (es)
Category: UTILITY
```

**Content:**

```
📚 Nueva tarea asignada

Hola {{1}},

Se ha asignado una nueva tarea:

📖 Materia: {{2}}
📅 Fecha de entrega: {{3}}
⏰ Faltan {{4}} días

Responde "detalles" para ver más información.
```

**Variables:**
- `{{1}}` = Nombre
- `{{2}}` = Materia
- `{{3}}` = Fecha entrega
- `{{4}}` = Días restantes

---

### 1.5 Crear Template "Progreso Semanal"

**Configuración:**

```
Template Name: reporte_progreso
Language: Spanish (es)
Category: UTILITY
```

**Content:**

```
📊 Reporte Semanal - {{1}}

Hola {{2}},

Tu progreso esta semana:

✅ Tareas completadas: {{3}}
📚 Clases asistidas: {{4}}
🎯 Promedio: {{5}}

¡{{6}}!

¿Quieres ver detalles?
```

**Variables:**
- `{{1}}` = Semana
- `{{2}}` = Nombre
- `{{3}}` = Tareas completadas
- `{{4}}` = Clases asistidas
- `{{5}}` = Promedio
- `{{6}}` = Mensaje motivacional

---

## 🎯 PASO 2: Obtener Template SID

Una vez aprobado (1-2 días):

```
1. Ve a Content Editor
2. Clic en tu template
3. Copia el "Content SID" (empieza con HX...)
4. Ejemplo: HXb4df6277ff3ad9a5b6c68993fed6ced8
```

Guarda estos SIDs en tu `.env`:

```env
TWILIO_TEMPLATE_BIENVENIDA=HXxxxxxxxxxxxxxxxxxxxx
TWILIO_TEMPLATE_RECORDATORIO=HXyyyyyyyyyyyyyyyyyyyy
TWILIO_TEMPLATE_TAREA=HXzzzzzzzzzzzzzzzzzzzz
TWILIO_TEMPLATE_PROGRESO=HXaaaaaaaaaaaaaaaaaaaa
```

---

## 🎯 PASO 3: Código Python para Enviar Templates

Ya creado en: `core/twilio_templates.py`

---

## 🎯 PASO 4: Probar Templates

Script de prueba creado en: `test_envio_proactivo.py`

---

## 📋 RESUMEN DE ESTADOS

### Durante Aprobación (1-2 días):

```
✅ Puedes usar Sandbox para pruebas
✅ Usuarios deben enviar "join [code]" primero
✅ Máximo ~10 usuarios
```

### Después de Aprobación:

```
✅ Templates activos
✅ Envío proactivo ilimitado
✅ Sin necesidad de "join"
✅ Cualquier número de WhatsApp
```

---

## ⚡ MIENTRAS ESPERAS APROBACIÓN

Puedes usar **texto libre en Sandbox** para probar el flujo:

```python
# Funciona en Sandbox (para pruebas)
from twilio.rest import Client
client = Client(account_sid, auth_token)

message = client.messages.create(
    from_='whatsapp:+14155238886',  # Tu Sandbox
    body='Hola! Este es un mensaje de prueba',
    to='whatsapp:+573001234567'
)
```

**Limitación:** Usuario debe haber enviado "join [code]" antes.

---

## 🆘 TROUBLESHOOTING

### Error: "Template not found"
- Verifica que el template esté aprobado
- Revisa el Content SID en .env

### Error: "Recipient not in sandbox"
- Usuario debe enviar "join [code]" primero
- O upgrade a producción

### Error: "Template variables mismatch"
- Verifica que envíes todas las variables
- Orden debe coincidir con {{1}}, {{2}}, etc.

---

## 📞 SIGUIENTE PASO

Una vez templates aprobados, actualiza tu código de producción para usar:

```python
from core.twilio_templates import enviar_template_twilio
from core.services import enviar_mensaje_proactivo_inteligente
```

Y estás listo para enviar mensajes proactivos a tus estudiantes! 🚀
