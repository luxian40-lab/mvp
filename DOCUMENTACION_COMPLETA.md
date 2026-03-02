# 📚 EKI - Chatbot Educativo para Agricultura - Documentación Completa

**Sistema de WhatsApp con IA multi-agente para educación agrícola**  
**Última actualización**: 31 Diciembre 2025

---

## 🚀 Inicio Rápido

### Ejecutar el Sistema

```bash
# Windows: Usar el menú unificado
eki_sistema_unificado.bat

# O manualmente:
python manage.py runserver      # Terminal 1
ngrok http 8000                  # Terminal 2
```

### Acceso Administrativo
- **URL Local**: http://localhost:8000/admin
- **Usuario**: admin
- **Contraseña**: tu_contraseña_admin

---

## 📱 Características Principales

### 1. Sistema Multi-Agente IA
**4 agentes especializados que compiten con Huaku:**

- **🎓 Agente Tutor**: Explicaciones académicas estructuradas
- **😤 Agente Frustración**: Manejo de emociones negativas con empatía
- **🌟 Agente Motivador**: Refuerzo positivo y celebración de logros
- **📝 Agente Evaluador**: Genera quizzes adaptativos según progreso

**Selección automática** según contexto del estudiante.

### 2. Integración WhatsApp
- **Twilio WhatsApp Sandbox**: Para desarrollo y pruebas
- **Meta Business API**: Para producción (requiere verificación)
- **Webhook unificado**: `/webhook/whatsapp/` maneja ambos proveedores

### 3. Sistema de Cursos
- Cursos estructurados con lecciones secuenciales
- Seguimiento de progreso individual
- Evaluaciones automáticas con calificaciones
- Etiquetas para filtrado (Café, Cacao, Banano, etc.)

### 4. Certificados (Estilo Coursera)
- Generación automática de PDFs profesionales
- Código de verificación único (EKI-XXXX-YYYY-ZZZZ)
- QR code para validación online
- Menciones académicas según calificación:
  - **95%+**: Con Distinción Sobresaliente
  - **90-94%**: Con Distinción
  - **80-89%**: Con Mérito
  - **70-79%**: Aprobado

### 5. 🎥 Videos Educativos para Campo
- **Videos directos en WhatsApp**: Sin salir de la app
- **Optimización para campo**: 360p para internet lento
- **Almacenamiento flexible**: Archivos directos o YouTube/Vimeo
- **Admin sencillo**: Subir MP4 y automáticamente se incluye en lecciones
- **Producción**: AWS S3 + CloudFront para CDN

**Ver guía completa**: [GUIA_VIDEOS.md](GUIA_VIDEOS.md)

### 6. Procesamiento de Audios
- **OpenAI Whisper**: Transcripción automática
- Formatos soportados: OGG, MP3, WAV, M4A
- Respuesta por texto después de transcribir

### 7. Aprendizaje Continuo
- Guarda cada interacción para mejorar respuestas
- Contexto conversacional (últimos 5 mensajes)
- Análisis de satisfacción del estudiante

---

## 🏗️ Arquitectura del Sistema

### Stack Tecnológico
```
Backend:     Django 5.2.9
Base Datos:  SQLite (desarrollo) / PostgreSQL (producción)
WhatsApp:    Twilio + Meta Business API
IA:          OpenAI GPT-3.5-turbo + Whisper
Frontend:    Django Admin (Jazzmin theme)
Deploy:      Railway / Heroku compatible
```

### Modelos Principales

**Estudiante**
- Perfil del usuario con teléfono único
- Tracking de curso actual y progreso
- Etiquetas para segmentación

**Curso y Leccion**
- Estructura jerárquica de contenido
- Orden secuencial de lecciones
- Contenido markdown con ejemplos

**WhatsappLog**
- Registro completo de mensajes (entrantes/salientes)
- Timestamp, proveedor, agente usado
- Soporte para texto y audio

**Certificado**
- Vinculado a estudiante y curso
- Fechas inicio/completado
- Calificación final y mención

---

## 🔧 Configuración Inicial

### 1. Instalar Dependencias

```bash
pip install -r requirements.txt

# Para certificados:
pip install reportlab qrcode[pil] pillow
```

### 2. Variables de Entorno (.env)

```env
# Django
SECRET_KEY=tu_clave_secreta_django
DEBUG=True

# OpenAI
OPENAI_API_KEY=sk-...

# Twilio WhatsApp
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=tu_auth_token
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886

# Meta WhatsApp (producción)
META_WHATSAPP_TOKEN=tu_token_meta
META_VERIFY_TOKEN=tu_token_verificacion
META_PHONE_NUMBER_ID=123456789

# Base de datos (producción)
DATABASE_URL=postgresql://user:pass@host:5432/db
```

### 3. Migraciones

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
```

### 4. Crear Contenido Inicial

```bash
# Cursos básicos de agricultura colombiana
python crear_cursos_inicial.py
```

---

## 📞 Configuración WhatsApp

### Opción A: Twilio (Desarrollo)

1. Crear cuenta en [Twilio](https://www.twilio.com)
2. WhatsApp Sandbox: https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn
3. Join sandbox: Envía "join <código>" al número Twilio
4. Configurar webhook:
   ```
   URL: https://tu-dominio.ngrok.io/webhook/whatsapp/
   Método: POST
   ```

### Opción B: Meta Business API (Producción)

1. Crear app en [Meta Developers](https://developers.facebook.com)
2. Agregar WhatsApp Business API
3. Verificar número de teléfono business
4. Configurar webhook:
   ```
   URL: https://tu-dominio.com/webhook/whatsapp/
   Verify Token: (el que pusiste en .env)
   Eventos: messages, message_status
   ```

### Ngrok (Túnel Local)

```bash
# Instalar: https://ngrok.com/download
ngrok http 8000

# Copiar URL HTTPS generada
# Actualizar en Twilio/Meta console
```

---

## 👥 Guía de Administración

### Panel de Control (Dashboard)

**Métricas en tiempo real:**
- Total campañas, estudiantes activos
- Mensajes WhatsApp (enviados/recibidos)
- Conversaciones únicas
- Gráfico de actividad semanal

### Gestión de Estudiantes

**Acciones masivas:**
- Importar desde Excel (columnas: telefono, nombre, email)
- Asignar etiquetas en lote
- Enviar mensajes grupales
- Exportar reportes

**Campos importantes:**
- `telefono`: Sin espacios ni símbolos (+573001234567)
- `nombre`: Nombre amigable para personalización
- `etiquetas`: Para segmentar (Zona Cafetera, Cacao, etc.)
- `curso_actual`: Asignación automática de curso

### Campañas de Mensajería

**Crear campañas:**
1. Nombre descriptivo
2. Plantilla (con variables {{nombre}}, {{curso}})
3. Filtro por etiquetas
4. Programar fecha/hora (opcional)

**Tipos de plantillas:**
- **Informativo**: Recordatorios, noticias
- **Motivacional**: Logros, celebraciones
- **Evaluación**: Quizzes, tareas

### Cursos y Lecciones

**Estructura recomendada:**
```
Curso: Cultivo de Café Orgánico
├─ Lección 1: Introducción al Café
├─ Lección 2: Preparación del Terreno
├─ Lección 3: Siembra de Semillas
├─ Lección 4: Cuidados Iniciales
└─ Lección 5: Cosecha y Procesamiento
```

**Contenido de lecciones:**
- Usar formato Markdown
- Incluir ejemplos prácticos
- Agregar preguntas al final
- Máximo 500 palabras por lección

---

## 🎓 Sistema de Certificados

### Generación Automática

Los certificados se generan cuando:
1. Estudiante completa todas las lecciones
2. Calificación final >= 70%
3. Admin marca manualmente "Generar certificado"

### Personalización

**PlantillaCertificado:**
- Logo de la organización
- Colores corporativos (primario, secundario, fondo)
- Texto del título y footer
- Firma digital

### Verificación Online

URL pública: `https://tu-dominio.com/verificar-certificado/EKI-XXXX-YYYY-ZZZZ`

Muestra:
- Nombre del estudiante
- Curso completado
- Fecha de emisión
- Calificación final
- Mención obtenida

### Envío por WhatsApp

```python
# En Django admin, acción masiva:
# "Enviar certificado por WhatsApp"

# O programáticamente:
from core.generador_certificados import generar_certificado_pdf
from core.utils import enviar_whatsapp

pdf_path = generar_certificado_pdf(certificado)
enviar_whatsapp(
    estudiante.telefono,
    f"¡Felicitaciones {estudiante.nombre}! Tu certificado está listo:",
    media_url=pdf_path
)
```

---

## 🤖 Sistema de Agentes IA

### Flujo de Decisión

1. **Mensaje llega** → Guardar en BD
2. **Detectar intención** → Patrones de texto (saludo, ayuda, etc.)
3. **Si no hay intención clara** → Seleccionar agente
4. **Agente analiza contexto** → Historial + estado emocional
5. **Generar respuesta** → OpenAI GPT con prompt especializado
6. **Enviar y guardar** → WhatsApp + Learning System

### Agente Tutor (Default)

**Cuándo se activa:**
- Preguntas técnicas sobre agricultura
- Solicitud de explicaciones
- Inicio de curso nuevo

**Prompt:**
```
Eres un tutor agrícola experto en agricultura colombiana.
Explica de forma clara y didáctica, con ejemplos locales.
Adapta tu respuesta al nivel de conocimiento del estudiante.
```

### Agente Frustración

**Cuándo se activa:**
- Palabras negativas: "no entiendo", "difícil", "aburrido"
- Mensajes consecutivos sin respuestas del estudiante
- Calificación baja en evaluaciones

**Prompt:**
```
El estudiante está frustrado. 
Muestra EMPATÍA genuina sin minimizar su sentimiento.
Ofrece ayuda específica, no solo motivación.
Sugiere descanso o cambiar de actividad.
```

### Agente Motivador

**Cuándo se activa:**
- Completar una lección
- Respuesta correcta en quiz
- Progresos significativos
- Palabras positivas: "logré", "entendí"

**Prompt:**
```
Celebra el logro del estudiante con entusiasmo.
Menciona el progreso específico alcanzado.
Anima a continuar sin presionar.
```

### Agente Evaluador

**Cuándo se activa:**
- Final de lección (generar quiz)
- Palabras: "evaluar", "examen", "quiz"
- Estudiante solicita medirse

**Prompt:**
```
Genera 3 preguntas de opción múltiple (A/B/C/D).
Basadas en la lección actual del estudiante.
Nivel: Intermedio (evita muy fácil o muy difícil).
Formato:
1. [Pregunta]
A) ...
B) ...
C) ...
D) ...
```

---

## 🔍 Troubleshooting

### El chat no responde

**Diagnóstico rápido:**
```bash
python diagnostico_rapido.py
```

**Checklist:**
1. ✅ Servidor Django corriendo (`python manage.py runserver`)
2. ✅ Ngrok activo (`ngrok http 8000`)
3. ✅ Webhook actualizado con URL de ngrok
4. ✅ Variables de entorno configuradas
5. ✅ No hay errores en la terminal del servidor

**Errores comunes:**

**UnboundLocalError: agente_nombre**
- ✅ Ya corregido en última versión
- Inicializar `agente_nombre = None` antes del try/except

**NameError: JsonResponse not defined**
- ✅ Ya corregido en views.py
- Import: `from django.http import HttpResponse, JsonResponse`

**OpenAI API Error**
- Verificar `OPENAI_API_KEY` en .env
- Revisar créditos en cuenta OpenAI

**Twilio 11200: HTTP retrieval failure**
- URL de ngrok cambió (se reinicia cada vez)
- Actualizar webhook en Twilio console

### Mensajes duplicados

**Causa**: Múltiples servidores Django corriendo.

**Solución:**
```bash
# Windows
Stop-Process -Name python -Force

# Linux/Mac
pkill python

# Reiniciar solo uno
python manage.py runserver
```

### Audios no transcriben

**Verificar:**
1. `pip install openai` actualizado
2. `OPENAI_API_KEY` configurado
3. Formato de audio soportado (OGG, MP3, WAV, M4A)
4. Tamaño < 25MB (límite Whisper)

**Error común:** `AttributeError: 'Audio' object has no attribute 'transcribe'`
- Solución: Actualizar librería OpenAI a versión 1.0+
```bash
pip install --upgrade openai
```

---

## 🚀 Despliegue a Producción

### Railway (Recomendado)

1. **Crear proyecto en Railway**:
   - Conectar repositorio GitHub
   - Railway detecta Django automáticamente

2. **Variables de entorno**:
   ```
   DJANGO_SETTINGS_MODULE=mvp_project.settings_production
   DEBUG=False
   SECRET_KEY=(generar nueva)
   DATABASE_URL=(PostgreSQL automático)
   OPENAI_API_KEY=...
   TWILIO_ACCOUNT_SID=...
   TWILIO_AUTH_TOKEN=...
   META_WHATSAPP_TOKEN=...
   ```

3. **Configurar dominio**:
   - Railway provee dominio: `tu-app.up.railway.app`
   - O conectar dominio custom

4. **Migrar base de datos**:
   ```bash
   railway run python manage.py migrate
   railway run python manage.py createsuperuser
   railway run python crear_cursos_inicial.py
   ```

5. **Actualizar webhooks**:
   - Twilio: `https://tu-app.up.railway.app/webhook/whatsapp/`
   - Meta: `https://tu-app.up.railway.app/webhook/whatsapp/`

### Heroku (Alternativa)

```bash
# Instalar Heroku CLI
heroku login
heroku create eki-chatbot

# PostgreSQL addon
heroku addons:create heroku-postgresql:mini

# Variables
heroku config:set DJANGO_SETTINGS_MODULE=mvp_project.settings_production
heroku config:set SECRET_KEY=$(python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")
heroku config:set DEBUG=False
heroku config:set OPENAI_API_KEY=...
heroku config:set TWILIO_ACCOUNT_SID=...

# Deploy
git push heroku main

# Migraciones
heroku run python manage.py migrate
heroku run python manage.py createsuperuser
```

### Consideraciones de Seguridad (Producción)

**settings_production.py ya incluye:**
- `DEBUG = False`
- `SECURE_SSL_REDIRECT = True`
- `SECURE_HSTS_SECONDS = 31536000`
- `SESSION_COOKIE_SECURE = True`
- `CSRF_COOKIE_SECURE = True`
- `X_FRAME_OPTIONS = 'DENY'`

**Adicionales:**
- Rotar `SECRET_KEY` periódicamente
- Limitar acceso a `/admin` por IP (Whitelist)
- Backups automáticos de base de datos
- Monitoreo de errores (Sentry recomendado)

---

## 💰 Valoración Comercial

### Análisis Competitivo

**Huaku (Competidor directo):**
- Precio: ~40M COP implementación
- Limitaciones: Sin sistema de cursos estructurados
- Ventaja EKI: Certificados + Gamificación + 4 agentes

**EKI - Precio Sugerido:**
- **Implementación**: 25-30M COP
- **Licencia mensual**: 800K-1.2M COP
- **Por estudiante adicional**: 15-20K COP/mes

**Incluye:**
- Sistema completo de cursos
- Certificados profesionales
- 4 agentes IA especializados
- WhatsApp ilimitado (según plan Twilio/Meta)
- Panel administrativo completo
- Soporte técnico

---

## 📊 Reportes y Métricas

### Exportar Datos

**Estudiantes:**
```python
# Admin action: "Exportar estudiantes a Excel"
# Incluye: telefono, nombre, email, etiquetas, curso_actual, progreso
```

**Mensajes WhatsApp:**
```python
# Filtros disponibles:
# - Fecha (rango)
# - Tipo (INCOMING/SENT)
# - Proveedor (twilio/meta)
# - Agente usado
```

**Certificados:**
```python
# Listado con:
# - Estudiante
# - Curso
# - Calificación
# - Fecha emisión
# - Código verificación
```

### Dashboard de Agentes

```bash
python ver_reporte_agentes.bat
```

Muestra:
- Conversaciones totales
- Uso de cada agente (%)
- Promedio de satisfacción
- Top 5 estudiantes más activos

---

## 🔄 Mantenimiento

### Backups Automáticos

```bash
# Ejecutar una vez para programar:
powershell -ExecutionPolicy Bypass -File programar_backup.ps1

# Manual:
python manage.py dumpdata > backup.json
```

**Frecuencia recomendada:** Diaria a las 2 AM

### Limpiar Logs Antiguos

```python
# core/management/commands/limpiar_logs.py
python manage.py limpiar_logs --dias=90
```

Elimina mensajes WhatsApp de hace más de X días.

### Actualizar Contenido

**Agregar nuevos cursos:**
1. Admin → Cursos → Agregar
2. Crear lecciones asociadas
3. Asignar etiquetas relevantes
4. Probar con estudiante test

**Modificar plantillas de respuesta:**
```python
# core/response_templates.py
TEMPLATES = {
    'saludo': "¡Hola {nombre}! 🌱...",
    'ayuda': "Puedo ayudarte con...",
    # Agregar nuevas aquí
}
```

---

## 🆘 Soporte

### Logs del Sistema

**Ubicación:** `logs/eki.log`

**Niveles:**
- `INFO`: Operaciones normales
- `WARNING`: Problemas no críticos
- `ERROR`: Errores que requieren atención

**Ver en tiempo real:**
```bash
tail -f logs/eki.log  # Linux/Mac
Get-Content logs/eki.log -Wait  # Windows
```

### Contacto Desarrollo

- **Email**: comunidad.educativa@eki.com.co
- **Repositorio**: github.com/tu-usuario/eki_mvp (ajustar)
- **Documentación**: Este archivo

---

## 📚 Recursos Adicionales

### APIs Usadas
- **OpenAI GPT-3.5**: https://platform.openai.com/docs
- **OpenAI Whisper**: https://platform.openai.com/docs/guides/speech-to-text
- **Twilio WhatsApp**: https://www.twilio.com/docs/whatsapp
- **Meta WhatsApp Business**: https://developers.facebook.com/docs/whatsapp

### Herramientas
- **Django Admin**: https://docs.djangoproject.com/en/5.0/ref/contrib/admin/
- **Jazzmin Theme**: https://django-jazzmin.readthedocs.io/
- **ReportLab (PDFs)**: https://www.reportlab.com/docs/reportlab-userguide.pdf

### Comunidad
- **Django Forum**: https://forum.djangoproject.com/
- **Twilio Community**: https://www.twilio.com/community

---

**Versión**: 2.0  
**Última revisión**: 31 Diciembre 2025  
**Autor**: Equipo EKI
