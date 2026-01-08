"""
Script de diagnóstico para verificar configuración de Twilio
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()

from django.conf import settings

print("\n" + "="*60)
print("🔍 DIAGNÓSTICO DE CONFIGURACIÓN TWILIO")
print("="*60 + "\n")

# 1. Variables de entorno
print("📋 Variables de Entorno:")
print(f"   TWILIO_ACCOUNT_SID: {settings.TWILIO_ACCOUNT_SID[:10]}..." if settings.TWILIO_ACCOUNT_SID else "   ❌ TWILIO_ACCOUNT_SID no configurado")
print(f"   TWILIO_AUTH_TOKEN: {settings.TWILIO_AUTH_TOKEN[:10]}..." if settings.TWILIO_AUTH_TOKEN else "   ❌ TWILIO_AUTH_TOKEN no configurado")
print(f"   TWILIO_WHATSAPP_NUMBER: {settings.TWILIO_WHATSAPP_NUMBER}")
print()

# 2. Intentar conectar con Twilio
print("🔗 Probando conexión con Twilio...")
try:
    from twilio.rest import Client
    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    
    # Obtener información de la cuenta
    account = client.api.accounts(settings.TWILIO_ACCOUNT_SID).fetch()
    print(f"   ✅ Conexión exitosa")
    print(f"   📱 Cuenta: {account.friendly_name}")
    print(f"   🆔 SID: {account.sid}")
    print(f"   📊 Estado: {account.status}")
    print()
    
    # Listar números de WhatsApp
    print("📞 Números de WhatsApp disponibles:")
    try:
        incoming_numbers = client.incoming_phone_numbers.list(limit=10)
        whatsapp_numbers = [n for n in incoming_numbers if 'WhatsApp' in str(n.capabilities)]
        
        if whatsapp_numbers:
            for number in whatsapp_numbers:
                print(f"   ✅ {number.phone_number} (WhatsApp habilitado)")
        else:
            print("   ⚠️  No se encontraron números con WhatsApp habilitado")
            print("   💡 Verifica en: https://console.twilio.com/us1/develop/sms/whatsapp/sandbox")
    except Exception as e:
        print(f"   ⚠️  No se pudieron listar números: {str(e)}")
    
except Exception as e:
    print(f"   ❌ Error de conexión: {str(e)}")
    print()
    print("💡 Verifica:")
    print("   1. TWILIO_ACCOUNT_SID está correcto")
    print("   2. TWILIO_AUTH_TOKEN está correcto")
    print("   3. Tienes conexión a internet")

print("\n" + "="*60)
print("🏁 DIAGNÓSTICO COMPLETADO")
print("="*60 + "\n")
