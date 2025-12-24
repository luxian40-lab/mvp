"""
Script simple para probar envío de WhatsApp con Twilio AHORA
"""

import os
import sys
import django
from pathlib import Path

# Setup Django
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()

from dotenv import load_dotenv
load_dotenv()


def main():
    print("\n" + "="*60)
    print("📱 TEST RÁPIDO: ENVÍO DE WHATSAPP CON TWILIO")
    print("="*60)
    
    # Verificar credenciales
    sid = os.getenv('TWILIO_ACCOUNT_SID')
    token = os.getenv('TWILIO_AUTH_TOKEN')
    from_number = os.getenv('TWILIO_WHATSAPP_NUMBER', 'whatsapp:+14155238886')
    
    if not sid or not token:
        print("❌ Credenciales de Twilio no configuradas en .env")
        print("\nVerifica que tengas:")
        print("  TWILIO_ACCOUNT_SID=ACxxxxx")
        print("  TWILIO_AUTH_TOKEN=xxxxx")
        print("  TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886")
        return
    
    print(f"\n✅ Credenciales encontradas")
    print(f"   Account SID: {sid[:20]}...")
    print(f"   Número: {from_number}")
    
    # Solicitar número destino
    print("\n📞 Ingresa el número de WhatsApp destino:")
    print("   Formato: +573001234567")
    print("   (Incluye código de país con +)")
    to_number = input("\nNúmero: ").strip()
    
    if not to_number:
        print("❌ Número vacío")
        return
    
    if not to_number.startswith('+'):
        to_number = '+' + to_number
    
    # Formatear para WhatsApp
    if not to_number.startswith('whatsapp:'):
        to_number = f'whatsapp:{to_number}'
    
    # Mensaje a enviar
    mensaje = """¡Hola! 👋

Este es un mensaje de prueba desde tu sistema Eki.

Si recibes esto, ¡el envío de WhatsApp funciona correctamente! ✅

Responde cualquier cosa para probar el webhook (si lo configuraste)."""
    
    print(f"\n📤 Enviando mensaje a: {to_number}")
    print(f"📝 Mensaje: {mensaje[:50]}...")
    
    confirmar = input("\n¿Continuar? (s/n): ").strip().lower()
    if confirmar != 's':
        print("❌ Cancelado")
        return
    
    # Enviar
    try:
        from twilio.rest import Client
        
        client = Client(sid, token)
        
        message = client.messages.create(
            from_=from_number,
            body=mensaje,
            to=to_number
        )
        
        print("\n" + "="*60)
        print("✅ ¡MENSAJE ENVIADO EXITOSAMENTE!")
        print("="*60)
        print(f"Message SID: {message.sid}")
        print(f"Estado: {message.status}")
        print(f"De: {from_number}")
        print(f"Para: {to_number}")
        print("\n💡 Revisa tu WhatsApp, deberías recibir el mensaje")
        print("="*60)
        
    except Exception as e:
        print("\n" + "="*60)
        print("❌ ERROR AL ENVIAR")
        print("="*60)
        print(f"Error: {str(e)}")
        
        error_str = str(e).lower()
        
        if 'unverified' in error_str or '63007' in error_str:
            print("\n💡 SOLUCIÓN:")
            print("El número no está en tu Sandbox.")
            print("\n1. Desde tu WhatsApp, envía al número Sandbox:")
            print(f"   {from_number.replace('whatsapp:', '')}")
            print("\n2. Envía el mensaje:")
            print("   join [código-que-te-muestra-twilio]")
            print("\n3. Espera confirmación")
            print("4. Vuelve a ejecutar este script")
        
        elif 'authenticate' in error_str or 'credentials' in error_str:
            print("\n💡 SOLUCIÓN:")
            print("Credenciales incorrectas.")
            print("Verifica en .env:")
            print("  TWILIO_ACCOUNT_SID")
            print("  TWILIO_AUTH_TOKEN")
        
        print("="*60)


if __name__ == "__main__":
    main()
