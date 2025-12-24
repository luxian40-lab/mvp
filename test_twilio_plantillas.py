"""
Script de prueba para enviar plantillas de Twilio con video
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
from core.models import Estudiante, WhatsappLog

# Cargar variables de entorno
load_dotenv()

print("=" * 70)
print("🎥 PRUEBA DE PLANTILLAS TWILIO CON VIDEO")
print("=" * 70)

# Verificar credenciales
account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
from_number = os.environ.get('TWILIO_WHATSAPP_NUMBER')

if not all([account_sid, auth_token, from_number]):
    print("\n❌ Faltan credenciales de Twilio en .env")
    exit(1)

print(f"\n✅ Credenciales Twilio:")
print(f"   Account SID: {account_sid[:15]}...")
print(f"   From: {from_number}")

# Solicitar información
print("\n" + "=" * 70)
print("📋 CONFIGURACIÓN DEL MENSAJE")
print("=" * 70)

print("\n¿Qué tipo de mensaje quieres enviar?")
print("1. Plantilla aprobada (Content Template)")
print("2. Mensaje libre con video/imagen")
print("3. Mensaje de texto simple")

tipo = input("\nOpción (1, 2 o 3): ").strip()

to_number = input("\n📱 Número de WhatsApp destino (+57XXXXXXXXXX): ").strip()

if not to_number.startswith('+'):
    to_number = f'+{to_number}'

# Crear cliente
client = Client(account_sid, auth_token)

try:
    if tipo == "1":
        # Plantilla aprobada
        print("\n📝 PLANTILLA APROBADA")
        
        content_sid = input("\nContent SID (HXxxx...): ").strip()
        
        print("\n¿Cuántas variables tiene tu plantilla?")
        num_vars = input("Número (0-5): ").strip()
        
        content_variables = {}
        if num_vars and int(num_vars) > 0:
            for i in range(1, int(num_vars) + 1):
                valor = input(f"  Variable {{{{ {i} }}}}: ").strip()
                content_variables[str(i)] = valor
        
        print(f"\n📤 Enviando plantilla {content_sid}...")
        print(f"   Variables: {content_variables}")
        
        message = client.messages.create(
            content_sid=content_sid,
            content_variables=content_variables if content_variables else None,
            from_=from_number,
            to=f"whatsapp:{to_number}"
        )
        
        print(f"\n✅ ¡Plantilla enviada!")
        print(f"   Message SID: {message.sid}")
        print(f"   Status: {message.status}")
        
    elif tipo == "2":
        # Mensaje con media
        print("\n🎥 MENSAJE CON MEDIA")
        
        texto = input("\nTexto del mensaje: ").strip()
        media_url = input("URL del video/imagen: ").strip()
        
        print(f"\n📤 Enviando mensaje con media...")
        
        message = client.messages.create(
            body=texto,
            media_url=[media_url],
            from_=from_number,
            to=f"whatsapp:{to_number}"
        )
        
        print(f"\n✅ ¡Mensaje enviado!")
        print(f"   Message SID: {message.sid}")
        print(f"   Status: {message.status}")
        
    else:
        # Mensaje simple
        print("\n📝 MENSAJE SIMPLE")
        
        texto = input("\nTexto del mensaje: ").strip()
        
        print(f"\n📤 Enviando mensaje...")
        
        message = client.messages.create(
            body=texto,
            from_=from_number,
            to=f"whatsapp:{to_number}"
        )
        
        print(f"\n✅ ¡Mensaje enviado!")
        print(f"   Message SID: {message.sid}")
        print(f"   Status: {message.status}")
    
    # Guardar en log
    WhatsappLog.objects.create(
        telefono=to_number.replace('whatsapp:', '').replace('+', ''),
        mensaje=texto if tipo != "1" else f"Template: {content_sid}",
        mensaje_id=message.sid,
        estado='SENT'
    )
    
    print(f"\n💾 Log guardado en la base de datos")
    
except Exception as e:
    print(f"\n❌ ERROR: {str(e)}")
    
    if "sandbox" in str(e).lower():
        print("\n⚠️ NOTA: Si usas el sandbox, asegúrate de:")
        print("   1. Haber enviado 'join <code>' al número de Twilio")
        print("   2. El número debe estar en la whitelist del sandbox")
    
    if "content" in str(e).lower():
        print("\n⚠️ NOTA: Para usar plantillas:")
        print("   1. La plantilla debe estar aprobada en Twilio")
        print("   2. Verifica el Content SID (HXxxx...)")
        print("   3. Asegúrate de pasar las variables correctas")

print("\n" + "=" * 70)
print("✅ PRUEBA COMPLETADA")
print("=" * 70)

print("\n💡 PRÓXIMOS PASOS:")
print("   1. Crea plantillas en: https://console.twilio.com/us1/develop/sms/content-editor")
print("   2. Espera aprobación (1-2 días)")
print("   3. Usa el Content SID para enviar desde Django")
print("   4. Ve los logs en: http://localhost:8000/admin/core/whatsapplog/")
