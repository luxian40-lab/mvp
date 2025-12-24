"""
Script de prueba para Twilio - WhatsApp y SMS
Ejecutar con: python test_twilio.py

Ejemplos de uso de Twilio API para enviar mensajes reales
"""
import os
from dotenv import load_dotenv
from twilio.rest import Client

# Cargar variables de entorno
load_dotenv()

def test_whatsapp_simple():
    """Enviar mensaje simple por WhatsApp usando Twilio"""
    print("\n" + "="*60)
    print("🧪 TEST: WhatsApp - Mensaje Simple")
    print("="*60)
    
    # Obtener credenciales del .env
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    
    if not account_sid or not auth_token:
        print("❌ Error: Configura TWILIO_ACCOUNT_SID y TWILIO_AUTH_TOKEN en .env")
        return
    
    # Número de destino
    telefono_destino = input("Ingresa el número destino (ej: +573001234567): ").strip()
    if not telefono_destino:
        print("❌ Número de destino requerido")
        return
    
    # Asegurar formato whatsapp:
    if not telefono_destino.startswith('whatsapp:'):
        telefono_destino = f'whatsapp:{telefono_destino}'
    
    try:
        client = Client(account_sid, auth_token)
        
        message = client.messages.create(
            from_="whatsapp:+14155238886",  # Número sandbox de Twilio
            body="¡Hola! Este es un mensaje de prueba desde EKI MVP con Twilio 🚀",
            to=telefono_destino,
        )
        
        print(f"\n✅ Mensaje enviado exitosamente!")
        print(f"📝 SID: {message.sid}")
        print(f"📊 Estado: {message.status}")
        print(f"📅 Fecha: {message.date_created}")
        print(f"💬 Body: {message.body}")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")


def test_whatsapp_con_imagen():
    """Enviar mensaje con imagen por WhatsApp usando Twilio"""
    print("\n" + "="*60)
    print("🧪 TEST: WhatsApp - Mensaje con Imagen")
    print("="*60)
    
    # Obtener credenciales del .env
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    
    if not account_sid or not auth_token:
        print("❌ Error: Configura TWILIO_ACCOUNT_SID y TWILIO_AUTH_TOKEN en .env")
        return
    
    # Número de destino
    telefono_destino = input("Ingresa el número destino (ej: +573001234567): ").strip()
    if not telefono_destino:
        print("❌ Número de destino requerido")
        return
    
    # Asegurar formato whatsapp:
    if not telefono_destino.startswith('whatsapp:'):
        telefono_destino = f'whatsapp:{telefono_destino}'
    
    # URL de imagen personalizada
    url_imagen = input("URL de la imagen (Enter para usar demo): ").strip()
    if not url_imagen:
        url_imagen = "https://demo.twilio.com/owl.png"
    
    try:
        client = Client(account_sid, auth_token)
        
        message = client.messages.create(
            body="📷 Aquí está la imagen que solicitaste desde EKI MVP",
            media_url=[url_imagen],
            to=telefono_destino,
            from_="whatsapp:+14155238886",  # Número sandbox de Twilio
        )
        
        print(f"\n✅ Mensaje con imagen enviado exitosamente!")
        print(f"📝 SID: {message.sid}")
        print(f"📊 Estado: {message.status}")
        print(f"📅 Fecha: {message.date_created}")
        print(f"💬 Body: {message.body}")
        print(f"🖼️  Imagen: {url_imagen}")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")


def test_whatsapp_con_callback():
    """Enviar mensaje con status callback"""
    print("\n" + "="*60)
    print("🧪 TEST: WhatsApp - Mensaje con Status Callback")
    print("="*60)
    
    # Obtener credenciales del .env
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    
    if not account_sid or not auth_token:
        print("❌ Error: Configura TWILIO_ACCOUNT_SID y TWILIO_AUTH_TOKEN en .env")
        return
    
    # Número de destino
    telefono_destino = input("Ingresa el número destino (ej: +573001234567): ").strip()
    if not telefono_destino:
        print("❌ Número de destino requerido")
        return
    
    # Asegurar formato whatsapp:
    if not telefono_destino.startswith('whatsapp:'):
        telefono_destino = f'whatsapp:{telefono_destino}'
    
    # URL de callback
    callback_url = input("URL de callback (Enter para omitir): ").strip()
    
    try:
        client = Client(account_sid, auth_token)
        
        params = {
            "to": telefono_destino,
            "from_": "whatsapp:+14155238886",
            "body": "🔔 Mensaje con seguimiento de estado desde EKI MVP"
        }
        
        if callback_url:
            params["status_callback"] = callback_url
        
        message = client.messages.create(**params)
        
        print(f"\n✅ Mensaje enviado exitosamente!")
        print(f"📝 SID: {message.sid}")
        print(f"📊 Estado: {message.status}")
        print(f"📅 Fecha: {message.date_created}")
        print(f"💬 Body: {message.body}")
        if callback_url:
            print(f"🔗 Callback: {callback_url}")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")


def main():
    """Menú principal"""
    print("\n" + "="*60)
    print("🚀 EKI MVP - Prueba de Integración Twilio")
    print("="*60)
    
    print("\n⚠️  IMPORTANTE: WhatsApp Sandbox")
    print("   1. Ve a: https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn")
    print("   2. Envía el código desde tu WhatsApp al número sandbox")
    print("   3. Espera confirmación antes de probar\n")
    
    print("Selecciona el tipo de prueba:")
    print("1. WhatsApp - Mensaje Simple")
    print("2. WhatsApp - Mensaje con Imagen")
    print("3. WhatsApp - Mensaje con Callback")
    print("4. Todas las pruebas")
    print("0. Salir")
    
    opcion = input("\nOpción: ")
    
    if opcion == "1":
        test_whatsapp_simple()
    elif opcion == "2":
        test_whatsapp_con_imagen()
    elif opcion == "3":
        test_whatsapp_con_callback()
    elif opcion == "4":
        test_whatsapp_simple()
        input("\nPresiona Enter para continuar con el test de imagen...")
        test_whatsapp_con_imagen()
        input("\nPresiona Enter para continuar con el test de callback...")
        test_whatsapp_con_callback()
    elif opcion == "0":
        print("👋 ¡Hasta luego!")
        return
    else:
        print("❌ Opción inválida")
        return
    
    print("\n✅ Pruebas completadas")


if __name__ == "__main__":
    main()
