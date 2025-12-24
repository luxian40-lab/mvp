"""
🤖 DEMO COMPLETA: PLANTILLAS + AGENTE IA

Este script demuestra el flujo completo:
1. Sistema envía plantilla de bienvenida (formal)
2. Estudiante responde
3. Agente IA mantiene la conversación (natural)
"""
import os
import sys
from pathlib import Path

# Setup Django
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')

import django
django.setup()

from core.template_service import TwilioTemplateService, enviar_mensaje_ia
from core.ai_assistant import EkiAIAssistant
from core.models import Estudiante, WhatsappLog, Plantilla
from dotenv import load_dotenv

load_dotenv()

print("=" * 80)
print("🤖 DEMO: PLANTILLAS + AGENTE IA")
print("=" * 80)

# Verificar configuración
print("\n📋 Verificando configuración...")

# OpenAI
openai_key = os.environ.get('OPENAI_API_KEY')
if openai_key:
    print(f"   ✅ OpenAI API Key: {openai_key[:20]}...")
else:
    print("   ❌ Falta OPENAI_API_KEY")
    exit(1)

# Twilio
twilio_sid = os.environ.get('TWILIO_ACCOUNT_SID')
twilio_auth = os.environ.get('TWILIO_AUTH_TOKEN')
twilio_number = os.environ.get('TWILIO_WHATSAPP_NUMBER')

if all([twilio_sid, twilio_auth, twilio_number]):
    print(f"   ✅ Twilio Account: {twilio_sid[:15]}...")
    print(f"   ✅ Twilio Number: {twilio_number}")
else:
    print("   ❌ Faltan credenciales de Twilio")
    exit(1)

print("\n" + "=" * 80)
print("🎭 ESCENARIO DE PRUEBA")
print("=" * 80)

print("""
Vamos a simular este flujo:

1. 📨 Sistema envía PLANTILLA de bienvenida (Twilio Template)
   → Mensaje formal con video/imagen
   → Pre-aprobado por Twilio
   
2. 👤 Estudiante responde "Hola"
   → Se registra en WhatsappLog
   
3. 🤖 Agente IA responde (OpenAI)
   → Conversación natural
   → Usa contexto del estudiante
   
4. 👤 Estudiante pregunta por su progreso
   → Mensaje registrado
   
5. 🤖 Agente IA responde con datos reales
   → Consulta progreso en BD
   → Respuesta personalizada
""")

# Solicitar datos
print("=" * 80)
print("📝 CONFIGURACIÓN DE LA PRUEBA")
print("=" * 80)

usar_real = input("\n¿Usar Twilio REAL o solo SIMULAR? (real/sim) [sim]: ").strip().lower()
usar_twilio_real = usar_real == 'real'

telefono_test = None
if usar_twilio_real:
    telefono_test = input("\n📱 Tu número de WhatsApp (+57XXXXXXXXXX): ").strip()
    if not telefono_test.startswith('+'):
        telefono_test = f'+{telefono_test}'
else:
    telefono_test = "+573001234567"  # Número de prueba

# Buscar o crear estudiante de prueba
print(f"\n🔍 Buscando estudiante con teléfono: {telefono_test}")
telefono_clean = telefono_test.replace('+', '')

estudiante, created = Estudiante.objects.get_or_create(
    telefono=telefono_clean,
    defaults={
        'nombre': 'Juan Test',
        'activo': True
    }
)

if created:
    print(f"   ✨ Estudiante creado: {estudiante.nombre}")
else:
    print(f"   ✅ Estudiante encontrado: {estudiante.nombre}")

# ============================================================================
# FASE 1: ENVIAR PLANTILLA DE BIENVENIDA
# ============================================================================

print("\n" + "=" * 80)
print("📨 FASE 1: PLANTILLA DE BIENVENIDA (Sistema → Estudiante)")
print("=" * 80)

print("""
Las plantillas se usan para:
✅ Primera impresión profesional
✅ Mensajes con multimedia (videos)
✅ Notificaciones formales del sistema
✅ Mensajes pre-aprobados por Twilio

Contenido típico:
────────────────
📚 ¡Hola Juan! Bienvenido a Eki

Soy tu asistente educativo inteligente.
Mira este video de bienvenida:

[VIDEO INTRODUCTORIO]

👉 Responde aquí para empezar
────────────────
""")

if usar_twilio_real:
    # Verificar si existe plantilla de bienvenida
    plantilla_bienvenida = Plantilla.objects.filter(
        nombre_interno='bienvenida',
        activa=True
    ).first()
    
    if plantilla_bienvenida and plantilla_bienvenida.twilio_template_sid:
        print(f"✅ Plantilla encontrada: {plantilla_bienvenida.nombre_interno}")
        print(f"   Content SID: {plantilla_bienvenida.twilio_template_sid}")
        
        confirmar = input("\n¿Enviar plantilla de bienvenida por Twilio? (s/n): ").strip().lower()
        
        if confirmar == 's':
            try:
                service = TwilioTemplateService()
                msg_sid = service.enviar_bienvenida(telefono_clean, estudiante.nombre)
                print(f"\n✅ ¡Plantilla enviada!")
                print(f"   Message SID: {msg_sid}")
                print(f"   Revisa tu WhatsApp: {telefono_test}")
            except Exception as e:
                print(f"\n❌ Error: {str(e)}")
                print("\n💡 Asegúrate de:")
                print("   1. Haber creado la plantilla 'bienvenida' en Twilio Console")
                print("   2. Copiar el Content SID (HXxxx) al admin de Django")
                print("   3. Activar la plantilla en el admin")
    else:
        print("⚠️ No hay plantilla 'bienvenida' configurada")
        print("\n📝 Para configurarla:")
        print("   1. Ve a Twilio Console: https://console.twilio.com/us1/develop/sms/content-editor")
        print("   2. Crea Content Template 'bienvenida'")
        print("   3. Copia el Content SID (HXxxx)")
        print("   4. Agrégalo en: http://127.0.0.1:8000/admin/core/plantilla/")
else:
    print("📋 [SIMULADO] Plantilla de bienvenida enviada")
    print(f"   To: {telefono_test}")
    print(f"   Template: bienvenida")

input("\n⏸️  Presiona Enter para continuar a la conversación con IA...")

# ============================================================================
# FASE 2: ESTUDIANTE SALUDA
# ============================================================================

print("\n" + "=" * 80)
print("👤 FASE 2: ESTUDIANTE RESPONDE (Usuario → Sistema)")
print("=" * 80)

mensaje_estudiante = "Hola"
print(f'\n👤 {estudiante.nombre}: "{mensaje_estudiante}"')

# Registrar mensaje entrante
WhatsappLog.objects.create(
    telefono=telefono_clean,
    mensaje=mensaje_estudiante,
    estado='INCOMING'
)
print(f"   💾 Mensaje registrado en WhatsappLog")

# ============================================================================
# FASE 3: IA RESPONDE
# ============================================================================

print("\n" + "=" * 80)
print("🤖 FASE 3: AGENTE IA RESPONDE (IA → Estudiante)")
print("=" * 80)

print("""
El agente IA ahora:
✅ Analiza el mensaje del estudiante
✅ Obtiene contexto (nombre, progreso, historial)
✅ Genera respuesta natural con OpenAI
✅ Responde de forma personalizada
""")

try:
    assistant = EkiAIAssistant()
    
    print("\n🔍 Obteniendo contexto del estudiante...")
    contexto = assistant.get_student_context(telefono_clean)
    print(f"   ✅ Contexto obtenido")
    
    print("\n🧠 Generando respuesta con GPT-4o-mini...")
    respuesta_ia = assistant.generar_respuesta(
        mensaje_estudiante, 
        telefono_clean, 
        incluir_historial=True
    )
    
    print(f"\n🤖 Eki: \n{respuesta_ia}")
    
    # Registrar respuesta
    WhatsappLog.objects.create(
        telefono=telefono_clean,
        mensaje=respuesta_ia,
        estado='SENT'
    )
    print(f"\n   💾 Respuesta registrada en WhatsappLog")
    
    if usar_twilio_real:
        confirmar = input("\n¿Enviar esta respuesta por WhatsApp? (s/n): ").strip().lower()
        if confirmar == 's':
            try:
                msg_sid = enviar_mensaje_ia(telefono_clean, respuesta_ia)
                print(f"   ✅ Mensaje enviado! SID: {msg_sid}")
            except Exception as e:
                print(f"   ❌ Error: {str(e)}")
    
except Exception as e:
    print(f"\n❌ Error en IA: {str(e)}")
    import traceback
    traceback.print_exc()

input("\n⏸️  Presiona Enter para simular segunda pregunta...")

# ============================================================================
# FASE 4: ESTUDIANTE PREGUNTA POR PROGRESO
# ============================================================================

print("\n" + "=" * 80)
print("👤 FASE 4: CONSULTA DE PROGRESO (Usuario → Sistema)")
print("=" * 80)

mensaje_estudiante2 = "¿Cuál es mi progreso?"
print(f'\n👤 {estudiante.nombre}: "{mensaje_estudiante2}"')

WhatsappLog.objects.create(
    telefono=telefono_clean,
    mensaje=mensaje_estudiante2,
    estado='INCOMING'
)

# ============================================================================
# FASE 5: IA RESPONDE CON DATOS REALES
# ============================================================================

print("\n" + "=" * 80)
print("🤖 FASE 5: IA RESPONDE CON DATOS (IA → Estudiante)")
print("=" * 80)

try:
    print("\n📊 Consultando progreso en base de datos...")
    
    respuesta_ia2 = assistant.generar_respuesta(
        mensaje_estudiante2,
        telefono_clean,
        incluir_historial=True
    )
    
    print(f"\n🤖 Eki: \n{respuesta_ia2}")
    
    WhatsappLog.objects.create(
        telefono=telefono_clean,
        mensaje=respuesta_ia2,
        estado='SENT'
    )
    
    if usar_twilio_real:
        confirmar = input("\n¿Enviar respuesta por WhatsApp? (s/n): ").strip().lower()
        if confirmar == 's':
            try:
                msg_sid = enviar_mensaje_ia(telefono_clean, respuesta_ia2)
                print(f"   ✅ Mensaje enviado! SID: {msg_sid}")
            except Exception as e:
                print(f"   ❌ Error: {str(e)}")
    
except Exception as e:
    print(f"\n❌ Error: {str(e)}")

# ============================================================================
# RESUMEN
# ============================================================================

print("\n" + "=" * 80)
print("📊 RESUMEN DE LA DEMO")
print("=" * 80)

total_logs = WhatsappLog.objects.filter(telefono=telefono_clean).count()
print(f"\n✅ Mensajes registrados: {total_logs}")

print("\n🔍 Últimos 5 mensajes:")
ultimos = WhatsappLog.objects.filter(telefono=telefono_clean).order_by('-fecha')[:5]
for log in reversed(list(ultimos)):
    tipo = "👤" if log.estado == 'INCOMING' else "🤖"
    timestamp = log.fecha.strftime("%H:%M:%S")
    preview = log.mensaje[:50] + "..." if len(log.mensaje) > 50 else log.mensaje
    print(f"   [{timestamp}] {tipo} {preview}")

print("\n" + "=" * 80)
print("✨ DIFERENCIAS CLAVE")
print("=" * 80)

print("""
📋 PLANTILLAS TWILIO:
   ✅ Mensajes formales y profesionales
   ✅ Multimedia (videos, imágenes)
   ✅ Botones interactivos
   ✅ Pre-aprobadas por Twilio
   ✅ Mayor tasa de apertura
   💰 ~$0.005 - $0.01 por mensaje
   
   Uso: Bienvenida, notificaciones oficiales

🤖 AGENTE IA (OpenAI):
   ✅ Conversación natural e inteligente
   ✅ Respuestas personalizadas
   ✅ Aprende del contexto
   ✅ Acceso a datos en tiempo real
   ✅ Historial conversacional
   💰 ~$0.0005 por mensaje
   
   Uso: Todas las conversaciones normales
""")

print("\n" + "=" * 80)
print("🎯 PRÓXIMOS PASOS")
print("=" * 80)

print("""
1. 📝 Crear plantillas en Twilio Console
   → https://console.twilio.com/us1/develop/sms/content-editor
   → Plantillas: bienvenida, nueva_clase, recordatorio
   
2. ⚙️ Configurar en Django Admin
   → http://127.0.0.1:8000/admin/core/plantilla/
   → Agregar Content SIDs (HXxxx)
   
3. 🧪 Probar webhook completo
   → Exponer con ngrok
   → Configurar webhook en Twilio
   
4. 🚀 Deploy a producción
   → Render.com (ya configurado)
   → Variables de entorno
   
5. 📊 Monitorear y optimizar
   → Ver logs en admin
   → Ajustar prompts de IA
""")

print("\n" + "=" * 80)
print("✅ DEMO COMPLETADA")
print("=" * 80)

print(f"\n📖 Más info en: ARQUITECTURA_IA.md")
print(f"🔗 Ver logs: http://127.0.0.1:8000/admin/core/whatsapplog/")
