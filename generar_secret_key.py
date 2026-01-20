"""
Script para generar una SECRET_KEY segura para Django
Ejecutar: python generar_secret_key.py
"""
from django.core.management.utils import get_random_secret_key

if __name__ == "__main__":
    secret_key = get_random_secret_key()
    print("=" * 70)
    print("🔐 SECRET_KEY GENERADA PARA DJANGO")
    print("=" * 70)
    print("\nCopia esta clave y pégala en tu archivo .env en AWS:")
    print("\nSECRET_KEY=" + secret_key)
    print("\n" + "=" * 70)
    print("✅ Esta clave tiene 50+ caracteres y es criptográficamente segura")
    print("⚠️  NO la subas a Git ni la compartas públicamente")
    print("=" * 70)
