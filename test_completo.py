"""
🚀 PRUEBA COMPLETA: Twilio + OpenAI
Envía un mensaje real con respuesta de IA
"""
import os
import sys
from pathlib import Path

# Agregar el directorio del proyecto al path
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
import django
django.setup()

from twilio.rest import Client
from dotenv import load_dotenv
from core.ai_assistant import responder_con_ia
from core.models import Estudiante, WhatsappLog

# Cargar variables de entorno
load_dotenv()

def prueba_completa():
    """Prueba completa de Twilio + OpenAI"""
    
    print("\n" + "=" * 70)
    print("🚀 PRUEBA COMPLETA: TWILIO + OPENAI")
    print("=" * 70)
    
    # 1. Verificar OpenAI
    print("\n[1/5] 🤖 Verificando OpenAI...")
    api_key = os.environ.get('OPENAI_API_KEY')
    
    if not api_key:
        print("   ❌ OPENAI_API_KEY no configurada")
        return
    
    print(f"   ✅ API Key: {api_key[:15]}...{api_key[-8:]}")
    
    # 2. Verificar Twilio
    print("\n[2/5] 📱 Verificando Twilio...")
    account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
    auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
    from_number = os.environ.get('TWILIO_WHATSAPP_NUMBER')
    
    if not all([account_sid, auth_token, from_number]):
        print("   ❌ Credenciales de Twilio incompletas")
        return
    
    print(f"   ✅ Account SID: {account_sid[:15]}...")
    print(f"   ✅ From Number: {from_number}")
    
    # 3. Crear/obtener estudiante de prueba
    print("\n[3/5] 👤 Configurando estudiante de prueba...")
    
    telefono_prueba = input("\n   📱 Ingresa tu número de WhatsApp (ej: +573001234567): ").strip()
    
    if not telefono_prueba:
        print("   ❌ Número no proporcionado")
        return
    
    # Asegurar formato correcto
    if not telefono_prueba.startswith('+'):
        telefono_prueba = f'+{telefono_prueba}'
    
    telefono_limpio = telefono_prueba.replace('+', '').replace(' ', '')
    
    estudiante, created = Estudiante.objects.get_or_create(
        telefono=telefono_limpio,
        defaults={'nombre': 'Prueba IA', 'activo': True}
    )
    
    if created:
        print(f"   ✅ Estudiante creado: {estudiante.nombre}")
    else:
        print(f"   ✅ Estudiante encontrado: {estudiante.nombre}")
    
    # 4. Probar IA localmente
    print("\n[4/5] 🧠 Probando respuesta de IA...")
    
    mensaje_prueba = input("\n   ✍️ Escribe un mensaje para probar la IA (o Enter para 'Hola'): ").strip()
    if not mensaje_prueba:
        mensaje_prueba = "Hola, ¿cómo estás?"
    
    print(f"\n   📤 Mensaje: {mensaje_prueba}")
    print("   🤖 Generando respuesta con IA...")
    
    try:
        respuesta_ia = responder_con_ia(mensaje_prueba, telefono_limpio)
        print(f"\n   ✅ Respuesta generada:")
        print("   " + "-" * 66)
        for line in respuesta_ia.split('\n'):
            print(f"   {line}")
        print("   " + "-" * 66)
    except Exception as e:
        print(f"   ❌ Error en IA: {str(e)}")
        return
    
    # 5. Enviar por Twilio
    print("\n[5/5] 📤 Enviando por Twilio WhatsApp...")
    
    confirmar = input("\n   ¿Enviar este mensaje a tu WhatsApp? (s/n): ").strip().lower()
    
    if confirmar != 's':
        print("\n   ⏸️ Envío cancelado por el usuario")
        print("\n" + "=" * 70)
        print("✅ PRUEBA COMPLETADA (sin envío)")
        print("=" * 70)
        return
    
    try:
        client = Client(account_sid, auth_token)
        
        message = client.messages.create(
            body=respuesta_ia,
            from_=from_number,
            to=f"whatsapp:{telefono_prueba}"
        )
        
        print(f"\n   ✅ MENSAJE ENVIADO!")
        print(f"      Message SID: {message.sid}")
        print(f"      Status: {message.status}")
        print(f"      To: {message.to}")
        
        # Guardar en WhatsappLog
        WhatsappLog.objects.create(
            telefono=telefono_limpio,
            mensaje=respuesta_ia,
            mensaje_id=message.sid,
            estado='SENT'
        )
        
        print(f"      💾 Log guardado en base de datos")
        
    except Exception as e:
        print(f"\n   ❌ ERROR AL ENVIAR: {str(e)}")
        
        if "not a valid" in str(e).lower() or "sandbox" in str(e).lower():
            print("\n   ⚠️ NOTA IMPORTANTE:")
            print("      Para recibir mensajes, debes activar el sandbox de Twilio:")
            print(f"      1. Envía un mensaje a: {from_number}")
            print("      2. Escribe: join <tu-sandbox-code>")
            print("      3. Encuentra tu código en: https://console.twilio.com")
        
        return
    
    print("\n" + "=" * 70)
    print("🎉 PRUEBA COMPLETA EXITOSA!")
    print("=" * 70)
    print("\n💡 Próximos pasos:")
    print("   1. Responde al mensaje que acabas de recibir")
    print("   2. Configura el webhook con ngrok para recibir respuestas automáticas")
    print("   3. Ve al admin para ver las conversaciones: http://localhost:8000/admin/conversaciones/")
    print("\n")


if __name__ == "__main__":
    try:
        prueba_completa()
    except KeyboardInterrupt:
        print("\n\n⏸️ Prueba cancelada por el usuario")
    except Exception as e:
        print(f"\n\n❌ ERROR INESPERADO: {str(e)}")
        import traceback
        traceback.print_exc()
