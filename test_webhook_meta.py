"""
Script para probar el webhook de WhatsApp localmente
Simula una petición POST de Meta WhatsApp Business
"""
import requests
import json

print("=" * 70)
print("🔗 PRUEBA DE WEBHOOK - META WHATSAPP")
print("=" * 70)

# URL del webhook local (asegúrate de que el servidor esté corriendo)
webhook_url = "http://localhost:8000/webhook/whatsapp/"

# 1. Verificación GET (Meta WhatsApp verifica el webhook así)
print("\n[1/2] 📋 Probando verificación GET...")
print(f"URL: {webhook_url}")

verify_params = {
    'hub.mode': 'subscribe',
    'hub.challenge': '12345678',
    'hub.verify_token': 'eki_whatsapp_verify_token_2025'
}

try:
    response = requests.get(webhook_url, params=verify_params, timeout=5)
    
    if response.status_code == 200 and response.text == '12345678':
        print("✅ Verificación GET exitosa!")
        print(f"   Challenge devuelto: {response.text}")
    else:
        print(f"❌ Verificación falló")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text}")
except Exception as e:
    print(f"❌ Error en verificación: {str(e)}")
    print("\n⚠️ Asegúrate de que el servidor Django esté corriendo:")
    print("   python manage.py runserver")
    exit(1)

# 2. Mensaje entrante POST (simula mensaje de usuario)
print("\n[2/2] 📨 Probando mensaje entrante POST...")

# Payload simulado de Meta WhatsApp
payload = {
    "object": "whatsapp_business_account",
    "entry": [
        {
            "id": "123456789",
            "changes": [
                {
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {
                            "display_phone_number": "15550000000",
                            "phone_number_id": "123456789"
                        },
                        "contacts": [
                            {
                                "profile": {
                                    "name": "Usuario de Prueba"
                                },
                                "wa_id": "573001234567"
                            }
                        ],
                        "messages": [
                            {
                                "from": "573001234567",
                                "id": "wamid.test123",
                                "timestamp": "1234567890",
                                "text": {
                                    "body": "Hola, esta es una prueba"
                                },
                                "type": "text"
                            }
                        ]
                    },
                    "field": "messages"
                }
            ]
        }
    ]
}

try:
    response = requests.post(
        webhook_url,
        json=payload,
        headers={'Content-Type': 'application/json'},
        timeout=10
    )
    
    if response.status_code == 200:
        print("✅ Mensaje procesado exitosamente!")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
        
        print("\n💾 Verifica en el admin:")
        print("   http://localhost:8000/admin/core/whatsapplog/")
        print("   Deberías ver el mensaje 'Hola, esta es una prueba'")
    else:
        print(f"❌ Error al procesar mensaje")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text}")
        
except Exception as e:
    print(f"❌ Error al enviar mensaje: {str(e)}")

print("\n" + "=" * 70)
print("✅ PRUEBA COMPLETADA")
print("=" * 70)
print("\n📝 Notas:")
print("   - Si la verificación GET funciona, puedes configurar en Meta")
print("   - Si el POST funciona, el webhook está listo para recibir mensajes")
print("   - Recuerda configurar OPENAI_API_KEY para respuestas con IA")
