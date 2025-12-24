# 🗓️ PLAN DE ACCIÓN - ESTA SEMANA

## 📋 OBJETIVO
Tener el sistema funcionando con:
- ✅ Plantillas de bienvenida en Twilio
- ✅ Agente IA respondiendo conversaciones
- ✅ Pruebas reales en WhatsApp

---

## 🚀 DÍA 1: LUNES (HOY) - Setup Twilio Templates

### ⏰ Tiempo estimado: 30-45 minutos

### PASO 1: Verificar cuenta de Twilio (5 min)

Ya tienes credenciales configuradas:
```
TWILIO_ACCOUNT_SID=ACdfe1762471d825240c7ac5833cf36bf9
TWILIO_WHATSAPP_NUMBER=+14155238886
```

Este es el **Sandbox** de Twilio (número de prueba).

**Opciones:**

#### A) Usar Sandbox (GRATIS - Recomendado para empezar)
- ✅ Gratis
- ✅ Funciona inmediatamente
- ❌ Solo tú y números que apruebes
- ❌ Mensaje "join [code]" requerido

#### B) Upgrade a Twilio Producción ($15-30/mes)
- ✅ Número propio de WhatsApp Business
- ✅ Sin restricciones
- ✅ Templates con multimedia
- 💰 $20 setup + $15/mes

**Recomendación:** Usa Sandbox esta semana para probar, upgrade después.

---

### PASO 2: Crear plantilla de bienvenida simple (15 min)

**IMPORTANTE:** El Sandbox tiene limitaciones. Vamos a crear una plantilla **MUY SIMPLE** primero.

#### 🔗 Ir a Twilio Console
1. Ve a: https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn
2. Login con tus credenciales

#### 📝 Enviar mensaje de prueba manual

En el Sandbox, puedes enviar mensajes directos (sin Content Templates por ahora):

```python
# Usar el script que ya creamos
python test_twilio_plantillas.py
```

Esto te permite:
- Enviar mensaje de texto
- Enviar mensaje con imagen/video (URL pública)
- Probar respuestas

---

### PASO 3: Probar IA básica (15 min)

```powershell
# Probar el agente IA actual
C:/Users/luxia/OneDrive/Escritorio/eki_mvp/.venv/Scripts/python.exe test_ia_conversacion.py
```

Prueba preguntas:
- "Hola"
- "¿Cuál es mi progreso?"
- "Ayuda con Python"

---

## 📅 DÍA 2: MARTES - Function Calling

### ⏰ Tiempo estimado: 2-3 horas

### PASO 1: Probar demo de Function Calling (30 min)

```powershell
C:/Users/luxia/OneDrive/Escritorio/eki_mvp/.venv/Scripts/python.exe demo_function_calling.py
```

Prueba:
- "¿Cuál es mi progreso?" → Verás que llama get_student_progress()
- "¿Qué tareas tengo?" → Llama get_pending_tasks()
- "¿Cuándo es mi próxima clase?" → Llama get_next_class()

### PASO 2: Integrar en ai_assistant.py (1 hora)

Actualizar el archivo `core/ai_assistant.py` para usar Function Calling.

### PASO 3: Probar desde webhook (30 min)

Exponer con ngrok y probar desde WhatsApp real.

---

## 📅 DÍA 3: MIÉRCOLES - Pruebas Reales

### ⏰ Tiempo estimado: 2-3 horas

### PASO 1: Configurar ngrok (15 min)

```powershell
ngrok http 8000
```

### PASO 2: Configurar webhook en Twilio (10 min)

1. Ve a: https://console.twilio.com/us1/develop/sms/settings/whatsapp-sandbox
2. En "WHEN A MESSAGE COMES IN":
   - URL: `https://tu-url-ngrok.ngrok.io/webhook/whatsapp/`
   - Method: POST

### PASO 3: Probar flujo completo (1 hora)

1. Envía "join [code]" al número de Twilio
2. Escribe "Hola"
3. IA debe responder
4. Pregunta "¿Mi progreso?"
5. IA consulta BD y responde

### PASO 4: Debugging y ajustes (1 hora)

- Ver logs en admin: http://localhost:8000/admin/core/whatsapplog/
- Ajustar prompts si es necesario
- Probar casos edge

---

## 📅 DÍA 4-5: JUEVES/VIERNES - Optimización

### ⏰ Tiempo estimado: 2-4 horas

### Opciones:

#### A) Mejorar Prompts (1 hora)
- Hacer respuestas más concisas
- Agregar más personalidad
- Optimizar para WhatsApp

#### B) Agregar más funciones (2 horas)
- `marcar_tarea_completa()`
- `solicitar_ayuda_tutor()`
- `agendar_recordatorio()`

#### C) Setup Celery para triggers (3 horas)
- Recordatorio diario automático
- Mensaje de inactividad

---

## 🎯 ENTREGABLE FIN DE SEMANA

### Lo que debes tener funcionando:

✅ **Sistema básico:**
- Webhook recibe mensajes de WhatsApp
- IA responde con OpenAI
- Logs guardados en BD

✅ **Function Calling:**
- IA consulta progreso automáticamente
- IA consulta tareas automáticamente
- Respuestas más precisas

✅ **Pruebas reales:**
- Al menos 5 conversaciones de prueba
- Screenshots/evidencia
- Bugs documentados y solucionados

---

## 📝 CHECKLIST DIARIA

### Lunes ✅
- [ ] Verificar credenciales Twilio
- [ ] Probar envío manual con test_twilio_plantillas.py
- [ ] Probar IA con test_ia_conversacion.py
- [ ] Documentar cualquier error

### Martes ✅
- [ ] Probar demo_function_calling.py
- [ ] Entender cómo funciona
- [ ] Actualizar ai_assistant.py con Function Calling
- [ ] Probar localmente

### Miércoles ✅
- [ ] Instalar/iniciar ngrok
- [ ] Configurar webhook en Twilio
- [ ] Primera prueba real de WhatsApp
- [ ] Verificar logs en admin
- [ ] Ajustar según errores

### Jueves ✅
- [ ] Probar con 5+ conversaciones reales
- [ ] Documentar casos que no funcionan bien
- [ ] Ajustar prompts
- [ ] Optimizar respuestas

### Viernes ✅
- [ ] Revisar todos los logs
- [ ] Crear reporte de pruebas
- [ ] Planear próximas mejoras
- [ ] Backup de código

---

## 🚨 SI TIENES PROBLEMAS

### Problema: No puedo crear Content Templates en Sandbox
**Solución:** En Sandbox, usa mensajes directos de texto/imagen. Content Templates requieren cuenta de producción.

### Problema: OpenAI muy lento
**Solución:** Reduce `max_tokens` a 200 en ai_assistant.py

### Problema: Webhook no recibe mensajes
**Solución:** 
1. Verifica ngrok está corriendo
2. Verifica URL correcta en Twilio Console
3. Revisa logs de Django: `python manage.py runserver`

### Problema: IA responde mal
**Solución:** 
1. Revisa el system_prompt
2. Agrega más ejemplos
3. Reduce temperature a 0.5

---

## 💰 COSTOS ESTA SEMANA

```
Twilio Sandbox:     $0 (gratis)
OpenAI (testing):   ~$0.50 (100-200 mensajes)
ngrok:              $0 (plan gratis)
───────────────────────────
TOTAL:              ~$0.50
```

---

## 📊 MÉTRICAS A MEDIR

Al final de la semana, debes saber:

1. **Velocidad de respuesta**
   - Promedio de segundos por respuesta

2. **Precisión**
   - % de respuestas correctas
   - % de veces que usa funciones correctamente

3. **Engagement**
   - Cantidad de mensajes por conversación
   - Tasa de respuesta de estudiantes

4. **Errores**
   - Cantidad de errores en logs
   - Tipos de errores comunes

---

## 🎓 RESULTADO ESPERADO

Al final de la semana tendrás:

```
┌─────────────────────────────────────────┐
│  MVP FUNCIONAL DE EKI                   │
├─────────────────────────────────────────┤
│                                         │
│  ✅ WhatsApp conectado                  │
│  ✅ IA respondiendo inteligentemente    │
│  ✅ Consulta datos reales (Function)    │
│  ✅ Logs completos en admin             │
│  ✅ Probado con usuarios reales         │
│                                         │
│  📊 Métricas recolectadas               │
│  🐛 Bugs identificados                  │
│  📝 Plan para próxima semana            │
│                                         │
└─────────────────────────────────────────┘
```

---

## 📞 PRÓXIMA SEMANA (Preview)

Dependiendo de resultados, semana 2:
- Upgrade a Twilio producción (si necesitas)
- Content Templates con video (si tienes producción)
- Celery para automatización
- Más funciones para el agente
- Dashboard de métricas

---

## 🚀 EMPIEZA AHORA

**Primer comando:**

```powershell
# Probar que todo esté instalado
C:/Users/luxia/OneDrive/Escritorio/eki_mvp/.venv/Scripts/python.exe test_twilio_plantillas.py
```

Esto te permite enviar tu primer mensaje de prueba por WhatsApp! 🎉

**¿Listo para empezar?** 💪
