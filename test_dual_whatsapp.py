"""
🧪 SCRIPT DE PRUEBA: SISTEMA DUAL META + TWILIO

Prueba ambos proveedores para verificar que funcionan.
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

from core.whatsapp_dual_service import WhatsAppDualService
from dotenv import load_dotenv

load_dotenv()

print("=" * 70)
print("🔗 PRUEBA: SISTEMA DUAL WHATSAPP")
print("=" * 70)

# Inicializar servicio
service = WhatsAppDualService()

print("\n📋 CONFIGURACIÓN DETECTADA:")
print("-" * 70)

# Verificar Meta
if service.meta_token and service.meta_phone_id:
    print(f"✅ Meta WhatsApp:")
    print(f"   Token: {service.meta_token[:20]}...")
    print(f"   Phone ID: {service.meta_phone_id}")
    print(f"   API Version: {service.meta_api_version}")
    meta_disponible = True
else:
    print("❌ Meta WhatsApp: No configurado")
    print("   Falta: META_WHATSAPP_TOKEN o META_PHONE_NUMBER_ID en .env")
    meta_disponible = False

# Verificar Twilio
if service.twilio_client:
    print(f"\n✅ Twilio:")
    print(f"   Account SID: {service.twilio_sid[:15]}...")
    print(f"   Number: {service.twilio_number}")
    twilio_disponible = True
else:
    print("\n❌ Twilio: No configurado")
    print("   Falta: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN o TWILIO_WHATSAPP_NUMBER")
    twilio_disponible = False

print(f"\n🎯 Modo actual: {service.provider.upper()}")

if not meta_disponible and not twilio_disponible:
    print("\n⚠️ ERROR: No hay ningún proveedor configurado!")
    print("\nPara configurar Meta WhatsApp:")
    print("1. Ve a: https://developers.facebook.com/apps")
    print("2. Crea una app y agrega WhatsApp")
    print("3. Copia el token y phone ID")
    print("4. Actualiza .env con META_WHATSAPP_TOKEN y META_PHONE_NUMBER_ID")
    print("\nPara configurar Twilio:")
    print("1. Ya tienes credenciales en .env")
    print("2. Verifica que sean correctas")
    exit(1)

# Menú de opciones
print("\n" + "=" * 70)
print("🧪 OPCIONES DE PRUEBA")
print("=" * 70)

print("\n1. Probar Meta WhatsApp (si está configurado)")
print("2. Probar Twilio WhatsApp (si está configurado)")
print("3. Probar sistema dual (envía por el mejor disponible)")
print("4. Salir")

opcion = input("\nSelecciona opción (1-4): ").strip()

if opcion == '4':
    print("\n👋 ¡Hasta luego!")
    exit(0)

# Solicitar datos
print("\n" + "=" * 70)
print("📱 DATOS DEL MENSAJE")
print("=" * 70)

telefono = input("\nNúmero de WhatsApp (+57XXXXXXXXXX): ").strip()
if not telefono:
    telefono = "+573001234567"
    print(f"   Usando número de prueba: {telefono}")

texto = input("Mensaje a enviar: ").strip()
if not texto:
    texto = "Hola! Este es un mensaje de prueba desde Eki 🤖"
    print(f"   Usando mensaje de prueba: {texto}")

# Enviar según opción
print("\n" + "=" * 70)
print("📤 ENVIANDO MENSAJE...")
print("=" * 70)

try:
    if opcion == '1':
        if not meta_disponible:
            print("\n❌ Meta WhatsApp no está configurado")
            exit(1)
        
        print("\n🔵 Enviando por Meta WhatsApp...")
        result = service.enviar_mensaje(telefono, texto, provider='meta')
        
    elif opcion == '2':
        if not twilio_disponible:
            print("\n❌ Twilio no está configurado")
            exit(1)
        
        print("\n🟣 Enviando por Twilio...")
        result = service.enviar_mensaje(telefono, texto, provider='twilio')
        
    elif opcion == '3':
        print("\n🔄 Enviando por sistema dual (automático)...")
        result = service.enviar_mensaje(telefono, texto)
    
    # Mostrar resultado
    print("\n" + "=" * 70)
    if result['success']:
        print("✅ MENSAJE ENVIADO EXITOSAMENTE")
        print("=" * 70)
        print(f"\nProveedor usado: {result['provider'].upper()}")
        print(f"ID del mensaje: {result.get('mensaje_id', 'N/A')}")
        
        if 'response' in result:
            print(f"\nRespuesta completa:")
            import json
            print(json.dumps(result['response'], indent=2))
    else:
        print("❌ ERROR AL ENVIAR")
        print("=" * 70)
        print(f"\nError: {result.get('error', 'Desconocido')}")
        print(f"Proveedor: {result.get('provider', 'N/A')}")
    
except Exception as e:
    print(f"\n❌ ERROR INESPERADO: {str(e)}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("✅ PRUEBA COMPLETADA")
print("=" * 70)

print("\n💡 PRÓXIMOS PASOS:")
print("1. Si funcionó, configura el webhook en Meta/Twilio")
print("2. Expón el servidor con ngrok: ngrok http 8000")
print("3. Configura webhook URL: https://tu-url.ngrok.io/webhook/whatsapp/")
print("4. Prueba enviando mensaje desde tu WhatsApp")
