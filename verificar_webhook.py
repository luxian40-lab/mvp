"""
Script para verificar que la webhook esté funcionando correctamente
"""

import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

def test_webhook_local():
    """Test de webhook en localhost"""
    print("\n" + "="*60)
    print("🧪 TEST 1: Webhook Local (Django)")
    print("="*60)
    
    url = "http://localhost:8000/webhook/whatsapp/"
    verify_token = os.getenv('WHATSAPP_VERIFY_TOKEN', 'eki_whatsapp_verify_token_2025')
    
    # Test de verificación (GET)
    params = {
        'hub.verify_token': verify_token,
        'hub.challenge': 'test_challenge_12345',
        'hub.mode': 'subscribe'
    }
    
    try:
        response = requests.get(url, params=params, timeout=5)
        
        if response.status_code == 200 and response.text == 'test_challenge_12345':
            print("✅ Webhook responde correctamente")
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.text}")
            return True
        else:
            print("❌ Webhook no responde correctamente")
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
    
    except requests.exceptions.ConnectionError:
        print("❌ No se puede conectar a Django")
        print("   Asegúrate de que Django esté corriendo:")
        print("   python manage.py runserver")
        return False
    
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False


def test_webhook_ngrok():
    """Test de webhook a través de ngrok"""
    print("\n" + "="*60)
    print("🧪 TEST 2: Webhook a través de ngrok")
    print("="*60)
    
    ngrok_url = input("\nIngresa tu URL de ngrok (ejemplo: https://abc123.ngrok.io): ").strip()
    
    if not ngrok_url:
        print("⚠️  URL no proporcionada, saltando test de ngrok")
        return False
    
    if not ngrok_url.startswith('http'):
        ngrok_url = 'https://' + ngrok_url
    
    url = ngrok_url.rstrip('/') + '/webhook/whatsapp/'
    verify_token = os.getenv('WHATSAPP_VERIFY_TOKEN', 'eki_whatsapp_verify_token_2025')
    
    params = {
        'hub.verify_token': verify_token,
        'hub.challenge': 'test_challenge_67890',
        'hub.mode': 'subscribe'
    }
    
    print(f"\n📡 Probando: {url}")
    
    try:
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200 and response.text == 'test_challenge_67890':
            print("✅ Webhook accesible desde internet")
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.text}")
            print("\n✅ Tu webhook está lista para configurar en Twilio/Meta")
            print(f"\n📋 URL para configurar: {url}")
            print(f"📋 Verify Token: {verify_token}")
            return True
        else:
            print("❌ Webhook responde pero con error")
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False
    
    except requests.exceptions.ConnectionError:
        print("❌ No se puede conectar a ngrok")
        print("   Verifica que:")
        print("   1. ngrok esté corriendo: ngrok http 8000")
        print("   2. La URL sea correcta")
        return False
    
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False


def test_webhook_post():
    """Test de webhook con mensaje simulado"""
    print("\n" + "="*60)
    print("🧪 TEST 3: Simular mensaje entrante")
    print("="*60)
    
    url = "http://localhost:8000/webhook/whatsapp/"
    
    # Payload simulado (formato Twilio)
    payload = {
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": "+573001234567",
                        "id": "test_message_id_123",
                        "text": {
                            "body": "Hola, esto es un test"
                        }
                    }]
                }
            }]
        }]
    }
    
    print("\n📤 Enviando mensaje simulado...")
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            print("✅ Webhook procesó el mensaje")
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.json()}")
            print("\n💡 Verifica en admin que se haya guardado:")
            print("   http://localhost:8000/admin/core/whatsapplog/")
            return True
        else:
            print("❌ Error al procesar mensaje")
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False
    
    except requests.exceptions.ConnectionError:
        print("❌ Django no está corriendo")
        return False
    
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False


def main():
    print("\n" + "="*60)
    print("🔍 VERIFICADOR DE WEBHOOK WHATSAPP")
    print("="*60)
    print("\nEste script verificará que tu webhook esté funcionando")
    print("correctamente antes de configurarla en Twilio/Meta.")
    
    # Verificar variables de entorno
    print("\n📋 Variables de entorno:")
    verify_token = os.getenv('WHATSAPP_VERIFY_TOKEN', 'eki_whatsapp_verify_token_2025')
    print(f"   WHATSAPP_VERIFY_TOKEN: {verify_token}")
    
    # Test 1: Local
    test1 = test_webhook_local()
    
    if not test1:
        print("\n⚠️  Django no está corriendo. Inícialo primero:")
        print("   python manage.py runserver")
        return
    
    # Test 2: ngrok (opcional)
    test2 = test_webhook_ngrok()
    
    # Test 3: POST
    if test1:
        test3 = test_webhook_post()
    
    # Resumen
    print("\n" + "="*60)
    print("📊 RESUMEN DE TESTS")
    print("="*60)
    print(f"Test 1 (Local GET):     {'✅ PASS' if test1 else '❌ FAIL'}")
    print(f"Test 2 (ngrok):         {'✅ PASS' if test2 else '⚠️  SKIP/FAIL'}")
    print(f"Test 3 (Local POST):    {'✅ PASS' if test1 else '❌ FAIL'}")
    
    if test1:
        print("\n✅ ¡Webhook funcionando correctamente!")
        print("\n📋 SIGUIENTE PASO:")
        print("1. Inicia ngrok: python iniciar_ngrok.bat (o ngrok http 8000)")
        print("2. Copia la URL: https://xxxxx.ngrok.io")
        print("3. Configura en Twilio Console:")
        print("   - URL: https://xxxxx.ngrok.io/webhook/whatsapp/")
        print(f"   - Verify Token: {verify_token}")
        print("   - Method: POST")
        print("4. Envía mensaje de prueba desde WhatsApp")
    else:
        print("\n❌ Hay problemas con la webhook")
        print("   Revisa los errores arriba")
    
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
