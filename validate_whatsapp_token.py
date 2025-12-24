#!/usr/bin/env python
"""
Script para validar y diagnosticar el token de WhatsApp Cloud API.
Verifica que el token sea válido y tiene los permisos correctos.
"""
import os
import sys
import requests
import json
from datetime import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')

import django
django.setup()

from django.conf import settings

print("\n" + "="*70)
print("🔍 VALIDACIÓN DE TOKEN - WhatsApp Cloud API")
print("="*70)

# 1. Obtener credenciales
token = settings.WHATSAPP_TOKEN
phone_id = settings.WHATSAPP_PHONE_ID
verify_token = settings.WHATSAPP_VERIFY_TOKEN
api_version = getattr(settings, 'WHATSAPP_API_VERSION', 'v19.0')

print("\n📋 Credenciales Configuradas:")
print(f"   Token: {token[:30]}...{token[-10:] if len(token) > 40 else ''}")
print(f"   Phone ID: {phone_id}")
print(f"   Verify Token: {verify_token}")

# 2. Validar token con API de Meta
print("\n🧪 Test 1: Validar Token")
print("-" * 70)

graph_url = f"https://graph.facebook.com/{api_version}"

try:
    # Obtener info del token
    response = requests.get(
        f"{graph_url}/me",
        params={"access_token": token},
        timeout=10
    )
    
    print(f"Status Code: {response.status_code}")
    data = response.json()
    
    if response.status_code == 200:
        print("✅ Token Válido")
        print(f"   ID: {data.get('id')}")
        print(f"   Name: {data.get('name')}")
    else:
        print(f"❌ Error: {data}")
        if 'error' in data:
            error = data['error']
            print(f"   Código: {error.get('code')}")
            print(f"   Mensaje: {error.get('message')}")
            print(f"   Type: {error.get('type')}")
            
except Exception as e:
    print(f"❌ Error de conexión: {e}")

# 3. Validar permisos
print("\n🧪 Test 2: Validar Permisos del Token")
print("-" * 70)

try:
    response = requests.get(
        f"{graph_url}/me/permissions",
        params={"access_token": token},
        timeout=10
    )
    
    if response.status_code == 200:
        data = response.json()
        perms = data.get('data', [])
        
        print("✅ Permisos del Token:")
        required_perms = [
            'whatsapp_business_messaging',
            'whatsapp_business_management',
            'business_management'
        ]
        
        for perm in perms:
            status = "✓" if perm['permission'] in required_perms else " "
            print(f"   [{status}] {perm['permission']}: {perm.get('status', 'unknown')}")
        
        missing = [p for p in required_perms if not any(pm['permission'] == p for pm in perms)]
        if missing:
            print(f"\n   ⚠️  Permisos faltantes: {missing}")
            print("   → Regenera el token en Meta con estos scopes")
    else:
        print(f"❌ Error: {response.json()}")
        
except Exception as e:
    print(f"❌ Error: {e}")

# 4. Validar Phone Number ID
print("\n🧪 Test 3: Validar Phone Number ID")
print("-" * 70)

try:
    response = requests.get(
        f"{graph_url}/{phone_id}",
        params={"access_token": token},
        timeout=10
    )
    
    print(f"Status Code: {response.status_code}")
    data = response.json()
    
    if response.status_code == 200:
        print("✅ Phone ID Válido")
        print(f"   ID: {data.get('id')}")
        print(f"   Display Name: {data.get('display_name_quality')}")
        print(f"   Quality: {data.get('quality_rating')}")
        print(f"   Phone: {data.get('phone_number')}")
        print(f"   Status: {data.get('status')}")
    else:
        error = data.get('error', {})
        print(f"❌ Error: {error.get('message')}")
        print(f"   Código: {error.get('code')} - {error.get('error_subcode')}")
        
        # Decodificar errores comunes
        if error.get('error_subcode') == 33:
            print("\n   💡 Error 33: Objeto no existe o permisos insuficientes")
            print("      • Verifica que el Phone ID sea correcto")
            print("      • Verifica que el número esté verificado en Meta")
            print("      • Regenera el token con permisos correctos")
        elif error.get('code') == 100:
            print("\n   💡 Error 100: Parámetro inválido o Token expirado")
            print("      • El token pudo haber expirado")
            print("      • Regenera un nuevo token en Meta")
            
except Exception as e:
    print(f"❌ Error de conexión: {e}")

# 5. Test de envío (simulado)
print("\n🧪 Test 4: Validar Capacidad de Envío")
print("-" * 70)

try:
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": "573026480629",  # Número de prueba
        "type": "text",
        "text": {"body": "Test desde Eki MVP"}
    }
    
    response = requests.post(
        f"{graph_url}/{phone_id}/messages",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
        timeout=10
    )
    
    data = response.json()
    
    if response.status_code in [200, 201]:
        print("✅ Envío Exitoso (Simulado)")
        print(f"   Message ID: {data.get('messages', [{}])[0].get('id')}")
    else:
        error = data.get('error', {})
        print(f"❌ Error al enviar: {error.get('message')}")
        print(f"   Código: {error.get('code')} - {error.get('error_subcode')}")
        
        if error.get('error_subcode') == 33:
            print("\n   💡 Este es el error que viste ayer!")
            print("   Solución:")
            print("   1. Ve a https://developers.facebook.com")
            print("   2. Selecciona tu app > WhatsApp > Configuration")
            print("   3. Verifica que el número esté verificado (verde ✓)")
            print("   4. Genera un nuevo token con permisos:")
            print("      - whatsapp_business_messaging")
            print("      - whatsapp_business_management")
            print("   5. Reemplaza el token en settings.py")
            
except Exception as e:
    print(f"❌ Error de conexión: {e}")

# 6. Resumen
print("\n" + "="*70)
print("📝 RESUMEN Y PRÓXIMOS PASOS")
print("="*70)

print("""
Si todos los tests pasaron (✅):
  ✓ El token es válido y tiene permisos
  ✓ El Phone ID es válido
  ✓ Puedes enviar mensajes
  
  → Configura el webhook en Meta:
     1. Ve a WhatsApp Configuration en Developers
     2. Callback URL: https://<TU_URL>/webhook/whatsapp/
     3. Verify Token: """ + verify_token + """
     4. Subscribe: messages, statuses
     5. Envía un mensaje desde WhatsApp

Si hay errores:
  ❌ Error 33: Verifica número + Token + Permisos
  ❌ Token expirado: Genera uno nuevo
  ❌ Phone ID inválido: Copia exacto de Meta
  
Generador de Token: https://developers.facebook.com/docs/whatsapp/cloud-api/get-started
""")

print("="*70 + "\n")
