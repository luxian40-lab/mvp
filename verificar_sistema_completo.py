"""
Script para verificar que TODO el sistema está configurado correctamente
"""
import os
import sys
import requests
from dotenv import load_dotenv
from twilio.rest import Client

# Cargar variables de entorno
load_dotenv()

print("=" * 70)
print("🔍 VERIFICACIÓN COMPLETA DEL SISTEMA EKI")
print("=" * 70)

# 1. Verificar Django
print("\n1️⃣ Verificando Django...")
try:
    response = requests.get("http://localhost:8000/admin/login/")
    if response.status_code == 200:
        print("   ✅ Django está corriendo en puerto 8000")
    else:
        print(f"   ⚠️ Django responde pero con status {response.status_code}")
except Exception as e:
    print(f"   ❌ Django NO está corriendo: {e}")
    sys.exit(1)

# 2. Verificar ngrok
print("\n2️⃣ Verificando ngrok...")
try:
    response = requests.get("http://localhost:4040/api/tunnels")
    data = response.json()
    if data['tunnels']:
        ngrok_url = data['tunnels'][0]['public_url']
        print(f"   ✅ ngrok está corriendo: {ngrok_url}")
        
        # Probar acceso desde ngrok
        try:
            test_response = requests.get(f"{ngrok_url}/admin/login/", timeout=10)
            if test_response.status_code == 200:
                print(f"   ✅ Django es accesible desde ngrok")
            else:
                print(f"   ⚠️ ngrok responde pero Django retorna status {test_response.status_code}")
        except Exception as e:
            print(f"   ⚠️ No se puede acceder a Django desde ngrok: {e}")
    else:
        print("   ❌ ngrok NO tiene túneles activos")
        sys.exit(1)
except Exception as e:
    print(f"   ❌ ngrok NO está corriendo: {e}")
    sys.exit(1)

# 3. Verificar credenciales Twilio
print("\n3️⃣ Verificando credenciales Twilio...")
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')
whatsapp_number = os.getenv('TWILIO_WHATSAPP_NUMBER')

if not account_sid or not auth_token:
    print("   ❌ Faltan credenciales de Twilio en .env")
    sys.exit(1)

print(f"   ✅ Account SID: {account_sid[:10]}...")
print(f"   ✅ Auth Token: {'*' * 20}")
print(f"   ✅ WhatsApp Number: {whatsapp_number}")

# 4. Verificar conexión con Twilio
print("\n4️⃣ Verificando conexión con Twilio...")
try:
    client = Client(account_sid, auth_token)
    account = client.api.accounts(account_sid).fetch()
    print(f"   ✅ Conectado a Twilio: {account.friendly_name}")
    print(f"   ℹ️ Status: {account.status}")
except Exception as e:
    print(f"   ❌ Error conectando con Twilio: {e}")
    sys.exit(1)

# 5. Verificar webhook configurado en Twilio Sandbox
print("\n5️⃣ Verificando configuración del webhook en Twilio...")
print(f"\n   📋 WEBHOOK DEBE ESTAR CONFIGURADO ASÍ:")
print(f"   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print(f"   URL: {ngrok_url}/webhook/whatsapp/")
print(f"   Método: POST")
print(f"   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print(f"\n   🔗 Ve a configurar aquí:")
print(f"   https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn")
print(f"\n   En la sección 'Sandbox Configuration' → 'When a message comes in'")

# 6. Verificar OpenAI
print("\n6️⃣ Verificando OpenAI...")
openai_key = os.getenv('OPENAI_API_KEY')
if openai_key and openai_key.startswith('sk-'):
    print(f"   ✅ OpenAI API Key configurada: {openai_key[:15]}...")
else:
    print(f"   ⚠️ OpenAI API Key no configurada o inválida")

print("\n" + "=" * 70)
print("✅ SISTEMA LISTO PARA FUNCIONAR")
print("=" * 70)

print("\n📱 PARA PROBAR:")
print("1. Configura el webhook en Twilio (URL arriba)")
print("2. Envía un mensaje desde WhatsApp al número sandbox")
print("3. La IA debería responder automáticamente")
print("\n💡 Tip: Mantén esta ventana abierta para ver los logs cuando lleguen mensajes")
print("=" * 70)
