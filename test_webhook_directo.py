"""
Script para probar que el webhook funciona correctamente
Simula un mensaje de Twilio
"""
import requests
import json

# URL del webhook local
webhook_url = "http://localhost:8000/webhook/whatsapp/"

# Payload simulando mensaje de Twilio
# Este es el formato que Twilio envía
payload = {
    "entry": [
        {
            "changes": [
                {
                    "value": {
                        "messages": [
                            {
                                "from": "whatsapp:+573001234567",  # Cambia por tu número
                                "id": "wamid.TEST123",
                                "text": {
                                    "body": "Hola, ¿cómo estás?"
                                }
                            }
                        ]
                    }
                }
            ]
        }
    ]
}

print("=" * 70)
print("🧪 PROBANDO WEBHOOK LOCALMENTE")
print("=" * 70)
print(f"\nEnviando POST a: {webhook_url}")
print(f"Payload: {json.dumps(payload, indent=2)}")
print("\n" + "-" * 70)

try:
    response = requests.post(
        webhook_url,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=30
    )
    
    print(f"\n✅ Respuesta recibida:")
    print(f"   Status Code: {response.status_code}")
    print(f"   Response: {response.text}")
    
    if response.status_code == 200:
        print("\n🎉 ¡WEBHOOK FUNCIONA CORRECTAMENTE!")
        print("\n📝 Ahora verifica en:")
        print("   1. Logs de Django (deberías ver el POST)")
        print("   2. Admin de WhatsApp Logs: http://localhost:8000/admin/core/whatsapplog/")
        print("   3. Deberías ver 2 registros:")
        print("      - INCOMING: El mensaje que enviaste")
        print("      - SENT: La respuesta de la IA")
    else:
        print(f"\n❌ Error: Status code {response.status_code}")
        
except requests.exceptions.Timeout:
    print("\n⏱️ TIMEOUT - La IA está tardando mucho en responder")
    print("   Esto puede ser normal si OpenAI está lento")
    print("   Espera 30 segundos y verifica los logs en el admin")
    
except Exception as e:
    print(f"\n❌ Error: {str(e)}")
    print("\n🔍 Verifica que:")
    print("   1. Django esté corriendo en puerto 8000")
    print("   2. La variable OPENAI_API_KEY esté en el .env")

print("\n" + "=" * 70)
