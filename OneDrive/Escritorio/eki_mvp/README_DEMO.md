# 🚀 Eki MVP - Demo WhatsApp & Dashboard

## Estado Actual: ✅ LISTO PARA DEMO

### ✨ Características Implementadas

1. **Dashboard Interactivo** (`http://localhost:8000/`)
   - Métricas de campañas (exitosas, fallidas, pendientes)
   - Métricas de WhatsApp (total, enviados, recibidos)
   - Tabla en tiempo real de últimos mensajes
   - Botones de acciones rápidas (Nueva Campaña, Nuevo Estudiante, Descargar Reportes)

2. **Gestión de Campañas** (`/admin/core/campana/`)
   - Crear campañas con canal (WhatsApp, SMS, Email, Voz)
   - Seleccionar línea de origen
   - Fecha programada de envío
   - Importar destinatarios vía Excel
   - Visualizar estado de entrega

3. **Descarga de Reportes** (`/admin/descargar-reportes/`)
   - Filtrar por rango de fechas (mes, rango personalizado)
   - Descargar Excel con datos de:
     - Envíos de campañas (ID, Estudiante, Teléfono, Estado, Fecha, Respuesta)
     - Mensajes WhatsApp (Teléfono, Tipo, Estado, Mensaje, Fecha)
   - Formato listo para análisis y auditoría

4. **Webhook WhatsApp Cloud API** 
   - Endpoint: `/webhook/whatsapp/`
   - Recibe mensajes entrantes y estados de entrega
   - Almacena en tabla `WhatsappLog` con todas las metadata
   - GET verification automática para Meta

5. **Admin Panel Avanzado**
   - Tabla `WhatsappLog` con:
     - Filtros por estado y fecha
     - Búsqueda por teléfono, mensaje, ID
     - Color-coding (Verde=Enviado, Azul=Entrante, Amarillo=Pendiente, Rojo=Error)
     - Vista previa de mensaje
   - Tabla `Campana` con Spanish labels ("Campaña" en lugar de "Campana")
   - Exportación a Excel directa desde admin

---

## 🎬 Cómo Hacer Demo Mañana

### Opción 1: Demo Local (Sin Túnel Externo)

Ideal para mostrar la funcionalidad sin necesidad de configurar Meta.

**Terminal 1 - Iniciar servidor:**
```bash
cd C:\Users\luxia\OneDrive\Escritorio\eki_mvp
.\venv\Scripts\python.exe manage.py runserver
```

**Terminal 2 - Probar webhook:**
```bash
cd C:\Users\luxia\OneDrive\Escritorio\eki_mvp
.\venv\Scripts\python.exe test_webhook_local.py
```

**Demostración:**
1. Abre http://localhost:8000/ → Dashboard
2. Ve a Admin (`/admin/`) → WhatsappLog → Verás el mensaje de prueba
3. Ve a `/admin/descargar-reportes/` → Descarga el Excel con el mensaje

---

### Opción 2: Demo con URL Pública (Túnel Externo)

Necesita configuración en Meta Business Manager.

**Paso 1: Arranca el servidor Django**
```bash
cd C:\Users\luxia\OneDrive\Escritorio\eki_mvp
.\venv\Scripts\python.exe manage.py runserver
```

**Paso 2: Obtén URL pública**

Descarga `cloudflared.exe` manualmente desde:
https://github.com/cloudflare/cloudflared/releases/download/2024.12.3/cloudflared-windows-amd64.exe

O usa `ngrok` (si tienes acceso):
```bash
# ngrok (si versión >= 3.19.0)
.\ngrok.exe http 8000
# O ngrok v2 actualizado
ngrok http 8000
```

Cloudflared:
```bash
.\cloudflared.exe tunnel --url http://localhost:8000
# Verás algo como: https://abc-trycloudflare.com
```

**Paso 3: Configurar en Meta Business Manager**

1. Ve a https://developers.facebook.com
2. Selecciona tu app WhatsApp Business
3. Ve a "Webhooks" o "Configuration"
4. Añade webhook:
   - **Callback URL:** `https://<TU_URL_PÚBLICA>/webhook/whatsapp/`
   - **Verify Token:** El valor configurado en `WHATSAPP_VERIFY_TOKEN` (ver settings.py)
   - **Subscribe to fields:** `messages`, `statuses`

5. Salva y Meta verificará tu webhook (automático con nuestra vista)

**Paso 4: Envía un mensaje de WhatsApp**

Desde WhatsApp Business App envía un mensaje → Aparecerá en:
- Dashboard en tiempo real
- Admin → WhatsappLog
- Descarga de reportes

---

## 🔧 Configuración Requerida para Meta

Edita `mvp_project/settings.py` y asegúrate de:

```python
# WhatsApp Cloud API
WHATSAPP_TOKEN = 'tu_token_de_acceso'  # Obtén de Meta Business Manager
WHATSAPP_PHONE_ID = 'tu_phone_id'  # ID del teléfono comercial
WHATSAPP_VERIFY_TOKEN = 'tu_token_secreto_para_verificacion'
```

---

## 📊 Estructura de Datos

### Tabla: WhatsappLog
```
ID | Teléfono | Tipo | Estado | Mensaje | Fecha | ID_Mensaje
1  | 573000000 | 📤 Saliente | ENVIADO | Hola | 2025-12-19 04:30 | wamid...
2  | 573000000 | 📥 Entrante | INCOMING | Hola también | 2025-12-19 04:31 | wamid...
```

### Estados Soportados
- `SENT` - Enviado exitosamente
- `INCOMING` - Mensaje entrante
- `DELIVERED` - Entregado
- `READ` - Leído
- `FAILED` - Falló el envío
- `PENDING` - En espera

---

## 🛠️ Scripts Útiles

### Probar webhook localmente:
```bash
.\venv\Scripts\python.exe test_webhook_local.py
```

### Acceder a shell Django:
```bash
.\venv\Scripts\python.exe manage.py shell
```

Dentro del shell:
```python
from core.models import WhatsappLog
# Ver últimos 5 mensajes
WhatsappLog.objects.order_by('-fecha')[:5].values('telefono', 'mensaje', 'estado', 'fecha')

# Contar por estado
WhatsappLog.objects.values('estado').annotate(count=Count('id'))

# Limpiar registros de prueba
WhatsappLog.objects.filter(telefono='573000000000').delete()
```

---

## 📱 URLs Importantes

| Descripción | URL |
|-------------|-----|
| Dashboard | http://localhost:8000/ |
| Admin Panel | http://localhost:8000/admin/ |
| Webhook WhatsApp | http://localhost:8000/webhook/whatsapp/ |
| Descargar Reportes | http://localhost:8000/admin/descargar-reportes/ |
| Gestión de Campañas | http://localhost:8000/admin/core/campana/ |
| Tabla WhatsappLog | http://localhost:8000/admin/core/whatsapplog/ |

---

## ✅ Checklist para Mañana

- [ ] Servidor Django en puerto 8000
- [ ] Dashboard accesible
- [ ] Test local webhook ejecutado exitosamente
- [ ] Meta webhook configurado (si es demo con URL pública)
- [ ] Enviar mensaje de prueba desde WhatsApp
- [ ] Verificar que aparece en dashboard y admin
- [ ] Descargar reporte Excel

---

## 🚨 Troubleshooting

**El dashboard no carga:**
```bash
.\venv\Scripts\python.exe manage.py check
```

**WhatsappLog vacío:**
- Ejecuta: `.\venv\Scripts\python.exe test_webhook_local.py`
- Verifica que webhook devuelve 200 OK

**Reporte Excel no descarga:**
- Asegúrate de tener `openpyxl` instalado
- Selecciona fechas correctas

---

## 📞 Contacto & Notas

- **Fecha de creación:** Dic 18-19, 2025
- **Versión:** MVP 1.0
- **Estado:** Producción-Ready (excepto credenciales Meta)
- **Próximas features:** Celery para envíos programados, auto-respuestas

---


