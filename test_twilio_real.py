"""
Script para probar Twilio WhatsApp - Envío de mensaje real
Fecha: 22 de diciembre de 2025
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

# Cargar variables de entorno
load_dotenv()

def probar_twilio_whatsapp():
    """Prueba envío de WhatsApp con Twilio"""
    
    print("=" * 60)
    print("🧪 PRUEBA DE TWILIO WHATSAPP")
    print("=" * 60)
    
    # Obtener credenciales
    account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
    auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
    from_number = os.environ.get('TWILIO_WHATSAPP_NUMBER')
    template_sid = os.environ.get('TWILIO_TEMPLATE_SID')
    
    print(f"\n📋 Credenciales cargadas:")
    print(f"   Account SID: {account_sid[:10]}..." if account_sid else "   ❌ Account SID no configurado")
    print(f"   Auth Token: {'✅ Configurado' if auth_token else '❌ No configurado'}")
    print(f"   From Number: {from_number}")
    print(f"   Template SID: {template_sid}")
    
    if not all([account_sid, auth_token, from_number]):
        print("\n❌ Error: Faltan credenciales de Twilio en el archivo .env")
        return
    
    # Solicitar número de destino
    print("\n" + "=" * 60)
    print("📱 CONFIGURACIÓN DEL MENSAJE")
    print("=" * 60)
    
    to_number = input("\n🔢 Ingresa tu número de WhatsApp (formato: +57XXXXXXXXXX): ").strip()
    
    if not to_number:
        print("❌ Número no proporcionado")
        return
    
    # Asegurar formato correcto
    if not to_number.startswith('+'):
        to_number = f'+{to_number}'
    
    # Elegir tipo de mensaje
    print("\n¿Qué tipo de mensaje quieres enviar?")
    print("1. Mensaje libre (texto personalizado)")
    print("2. Template aprobado (Twilio Content SID)")
    
    opcion = input("\nOpción (1 o 2): ").strip()
    
    # Crear cliente Twilio
    client = Client(account_sid, auth_token)
    
    try:
        if opcion == "2" and template_sid:
            # Usar template aprobado
            print(f"\n📤 Enviando template aprobado a {to_number}...")
            
            message = client.messages.create(
                content_sid=template_sid,
                from_=from_number,
                to=f"whatsapp:{to_number}"
            )
            
            print(f"\n✅ MENSAJE ENVIADO CON ÉXITO!")
            print(f"   Message SID: {message.sid}")
            print(f"   Status: {message.status}")
            print(f"   To: {message.to}")
            print(f"   From: {message.from_}")
            print(f"   Fecha: {message.date_created}")
            
        else:
            # Mensaje libre
            texto_mensaje = input("\n✍️ Escribe el mensaje que quieres enviar: ").strip()
            
            if not texto_mensaje:
                print("❌ No se proporcionó texto del mensaje")
                return
            
            # Preguntar si quiere agregar imagen
            agregar_imagen = input("\n🖼️ ¿Quieres agregar una imagen? (s/n): ").strip().lower()
            
            if agregar_imagen == 's':
                url_imagen = input("   URL de la imagen: ").strip()
                
                print(f"\n📤 Enviando mensaje con imagen a {to_number}...")
                
                message = client.messages.create(
                    body=texto_mensaje,
                    from_=from_number,
                    to=f"whatsapp:{to_number}",
                    media_url=[url_imagen]
                )
            else:
                print(f"\n📤 Enviando mensaje a {to_number}...")
                
                message = client.messages.create(
                    body=texto_mensaje,
                    from_=from_number,
                    to=f"whatsapp:{to_number}"
                )
            
            print(f"\n✅ MENSAJE ENVIADO CON ÉXITO!")
            print(f"   Message SID: {message.sid}")
            print(f"   Status: {message.status}")
            print(f"   Cuerpo: {message.body[:50]}...")
            print(f"   To: {message.to}")
            print(f"   From: {message.from_}")
            print(f"   Fecha: {message.date_created}")
        
        # Guardar en WhatsappLog
        from core.models import WhatsappLog
        
        WhatsappLog.objects.create(
            telefono=to_number.replace('whatsapp:', '').replace('+', ''),
            mensaje=texto_mensaje if opcion == "1" else "Template aprobado",
            mensaje_id=message.sid,
            estado='SENT'
        )
        
        print(f"\n💾 Registro guardado en WhatsappLog")
        
    except Exception as e:
        print(f"\n❌ ERROR AL ENVIAR MENSAJE:")
        print(f"   {str(e)}")
        
        # Verificar si es problema del sandbox
        if "sandbox" in str(e).lower():
            print("\n⚠️ NOTA: Si usas el sandbox de Twilio, asegúrate de:")
            print("   1. Enviar 'join <sandbox-code>' desde tu WhatsApp al número de Twilio")
            print("   2. Esperar la confirmación de activación")
            print(f"   3. Más info: https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn")

    print("\n" + "=" * 60)
    print("🎉 PRUEBA COMPLETADA")
    print("=" * 60)


if __name__ == "__main__":
    probar_twilio_whatsapp()
