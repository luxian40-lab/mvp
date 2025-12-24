#!/usr/bin/env python
"""
Script de prueba para enviar un mensaje WhatsApp.
python test_whatsapp.py
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()

from core.utils import enviar_whatsapp

# Enviar un mensaje de prueba
telefono = '573026480629'  # El número que proporcionaste
mensaje = '¡Hola! Este es un mensaje de prueba desde Eki MVP 🎉'

print(f"📤 Enviando mensaje a {telefono}...")
resultado = enviar_whatsapp(telefono, mensaje)

print(f"\n✅ Resultado:")
print(f"  - Éxito: {resultado['success']}")
print(f"  - Mensaje ID: {resultado['mensaje_id']}")
print(f"  - Respuesta: {resultado['response']}")

if resultado['success']:
    print(f"\n✅ ¡Mensaje enviado correctamente!")
else:
    print(f"\n❌ Error al enviar: {resultado['response']}")
