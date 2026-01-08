"""
Diagnóstico Rápido - Por qué no llegan mensajes
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()

from core.models import WhatsappLog, Estudiante
from django.utils import timezone
from datetime import timedelta

print("="*70)
print("🔍 DIAGNÓSTICO RÁPIDO - Sistema de Mensajería")
print("="*70)

# 1. Mensajes últimas 24h
hace_24h = timezone.now() - timedelta(hours=24)
mensajes = WhatsappLog.objects.filter(fecha__gte=hace_24h)
print(f"\n📥 Mensajes últimas 24 horas: {mensajes.count()}")

if mensajes.count() == 0:
    print("\n❌ NO HAY MENSAJES RECIENTES")
    print("\n🔧 CAUSAS POSIBLES:")
    print("  1. Servidor Django no está corriendo")
    print("  2. Ngrok no está activo o cambió de URL")
    print("  3. Webhook no está configurado correctamente")
    print("  4. El número de WhatsApp es incorrecto")
else:
    print("\n✅ Hay mensajes recientes:")
    for msg in mensajes.order_by('-fecha')[:5]:
        print(f"  - {msg.fecha.strftime('%H:%M')}: {msg.telefono}")
        print(f"    {msg.mensaje[:50]}...")

# 2. Último mensaje
ultimo = WhatsappLog.objects.order_by('-fecha').first()
if ultimo:
    print(f"\n📌 Último mensaje general:")
    print(f"  Fecha: {ultimo.fecha}")
    print(f"  De: {ultimo.telefono}")
    print(f"  Texto: {ultimo.mensaje[:80]}")

# 3. Total estudiantes
print(f"\n👥 Total estudiantes: {Estudiante.objects.count()}")

print("\n" + "="*70)
print("\n💡 SOLUCIÓN RÁPIDA:")
print("\n1. Abre 2 terminales:")
print("   Terminal 1: python manage.py runserver")
print("   Terminal 2: ngrok http 8000")
print("\n2. Copia la URL de ngrok (ej: https://abc123.ngrok.io)")
print("\n3. Configura webhook:")
print("   Twilio: https://console.twilio.com/")
print("   URL: https://TU-URL-NGROK/twilio/webhook/")
print("\n4. Envía mensaje de prueba")
print("\n" + "="*70)
