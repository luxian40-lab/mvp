"""
Prueba rápida de OpenAI - Verificar que la API key funciona
"""
import os
from dotenv import load_dotenv
from openai import OpenAI

# Cargar variables de entorno
load_dotenv()

print("=" * 60)
print("🤖 PRUEBA RÁPIDA DE OPENAI")
print("=" * 60)

# Verificar API key
api_key = os.environ.get('OPENAI_API_KEY')

if not api_key:
    print("❌ OPENAI_API_KEY no encontrada en .env")
    exit(1)

print(f"\n✅ API Key encontrada: {api_key[:20]}...{api_key[-10:]}")
print("\n🔄 Probando conexión con OpenAI...")

try:
    # Crear cliente
    client = OpenAI(api_key=api_key)
    
    # Hacer una pregunta simple
    print("\n📤 Enviando mensaje de prueba...")
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Eres Eki, un asistente educativo amigable."},
            {"role": "user", "content": "Hola, preséntate brevemente en español"}
        ],
        max_tokens=150
    )
    
    respuesta = response.choices[0].message.content
    
    print("\n✅ ¡CONEXIÓN EXITOSA!")
    print("=" * 60)
    print("\n🤖 Respuesta de Eki:")
    print("-" * 60)
    print(respuesta)
    print("-" * 60)
    
    print(f"\n💰 Tokens usados: {response.usage.total_tokens}")
    print(f"   - Prompt: {response.usage.prompt_tokens}")
    print(f"   - Completion: {response.usage.completion_tokens}")
    
    print("\n✅ TODO FUNCIONA CORRECTAMENTE")
    print("=" * 60)
    
except Exception as e:
    print(f"\n❌ ERROR: {str(e)}")
    print("\n💡 Posibles causas:")
    print("   - API key inválida o expirada")
    print("   - Sin créditos en la cuenta de OpenAI")
    print("   - Problema de conexión a internet")
    print("\n🔗 Verifica tu cuenta: https://platform.openai.com/account/usage")
