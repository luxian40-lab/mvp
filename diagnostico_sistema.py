"""
Script de Diagnóstico - Sistema de Mensajería EKI
Verifica por qué los mensajes no están llegando
"""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()

from core.models import WhatsAppLog, Estudiante
from django.utils import timezone
from datetime import timedelta
from django.conf import settings


def print_separator():
    print("\n" + "="*70 + "\n")


def diagnostico_mensajes():
    """Verificar mensajes recientes"""
    print("📊 DIAGNÓSTICO: Mensajes Recientes")
    print_separator()
    
    # Últimas 24 horas
    hace_24h = timezone.now() - timedelta(hours=24)
    mensajes_24h = WhatsAppLog.objects.filter(fecha_hora__gte=hace_24h)
    
    print(f"📥 Mensajes últimas 24 horas: {mensajes_24h.count()}")
    
    if mensajes_24h.exists():
        print("\n✅ HAY MENSAJES RECIENTES:")
        for msg in mensajes_24h.order_by('-fecha_hora')[:5]:
            print(f"  - {msg.fecha_hora.strftime('%H:%M:%S')}: {msg.telefono}")
            print(f"    Texto: {msg.texto[:50]}...")
            print(f"    Dirección: {msg.direccion}")
    else:
        print("\n⚠️ NO HAY MENSAJES EN LAS ÚLTIMAS 24 HORAS")
        print("\n❌ CAUSA PROBABLE:")
        print("  1. Webhook no está recibiendo mensajes")
        print("  2. Ngrok no está activo o cambió de URL")
        print("  3. Configuración del webhook incorrecta")
    
    # Último mensaje general
    ultimo_mensaje = WhatsAppLog.objects.order_by('-fecha_hora').first()
    if ultimo_mensaje:
        print(f"\n📌 Último mensaje registrado:")
        print(f"  - Fecha: {ultimo_mensaje.fecha_hora}")
        print(f"  - De: {ultimo_mensaje.telefono}")
        print(f"  - Texto: {ultimo_mensaje.texto[:100]}")
    
    print_separator()


def diagnostico_configuracion():
    """Verificar configuración de APIs"""
    print("🔧 DIAGNÓSTICO: Configuración de APIs")
    print_separator()
    
    # Twilio
    if hasattr(settings, 'TWILIO_ACCOUNT_SID') and settings.TWILIO_ACCOUNT_SID:
        print("✅ Twilio CONFIGURADO")
        print(f"   SID: {settings.TWILIO_ACCOUNT_SID[:15]}...")
        if hasattr(settings, 'TWILIO_AUTH_TOKEN'):
            print(f"   Token: {settings.TWILIO_AUTH_TOKEN[:10]}...")
        if hasattr(settings, 'TWILIO_WHATSAPP_NUMBER'):
            print(f"   Número: {settings.TWILIO_WHATSAPP_NUMBER}")
    else:
        print("⚠️ Twilio NO CONFIGURADO")
    
    print()
    
    # Meta WhatsApp API
    if hasattr(settings, 'WHATSAPP_API_TOKEN') and settings.WHATSAPP_API_TOKEN:
        print("✅ Meta WhatsApp API CONFIGURADA")
        print(f"   Token: {settings.WHATSAPP_API_TOKEN[:15]}...")
        if hasattr(settings, 'WHATSAPP_PHONE_ID'):
            print(f"   Phone ID: {settings.WHATSAPP_PHONE_ID}")
    else:
        print("⚠️ Meta WhatsApp API NO CONFIGURADA")
    
    print()
    
    # OpenAI
    if hasattr(settings, 'OPENAI_API_KEY') and settings.OPENAI_API_KEY:
        print("✅ OpenAI CONFIGURADO")
        print(f"   Key: {settings.OPENAI_API_KEY[:15]}...")
    else:
        print("❌ OpenAI NO CONFIGURADO")
    
    print_separator()


def diagnostico_servidor():
    """Verificar estado del servidor"""
    print("🖥️ DIAGNÓSTICO: Estado del Servidor")
    print_separator()
    
    import socket
    
    # Verificar puerto 8000
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    resultado = sock.connect_ex(('127.0.0.1', 8000))
    
    if resultado == 0:
        print("✅ Servidor Django ACTIVO en puerto 8000")
    else:
        print("❌ Servidor Django NO ESTÁ CORRIENDO")
        print("\n🔧 SOLUCIÓN:")
        print("   python manage.py runserver")
    
    sock.close()
    
    print_separator()


def diagnostico_estudiantes():
    """Verificar estudiantes registrados"""
    print("👥 DIAGNÓSTICO: Estudiantes Registrados")
    print_separator()
    
    total = Estudiante.objects.count()
    print(f"📊 Total estudiantes: {total}")
    
    if total > 0:
        print("\n✅ Estudiantes en sistema:")
        for est in Estudiante.objects.all()[:10]:
            # Contar mensajes
            mensajes = WhatsAppLog.objects.filter(telefono=est.telefono).count()
            print(f"  - {est.nombre} ({est.telefono}): {mensajes} mensajes")
    else:
        print("\n⚠️ No hay estudiantes registrados")
        print("   Los estudiantes se crean automáticamente al enviar primer mensaje")
    
    print_separator()


def soluciones_recomendadas():
    """Sugerir soluciones"""
    print("💡 SOLUCIONES RECOMENDADAS")
    print_separator()
    
    print("🔧 PASOS PARA RESOLVER:")
    print("\n1. VERIFICAR SERVIDOR DJANGO:")
    print("   Terminal 1:")
    print("   > cd C:\\Users\\luxia\\OneDrive\\Escritorio\\eki_mvp")
    print("   > python manage.py runserver")
    print("   Deberías ver: 'Starting development server at http://127.0.0.1:8000/'")
    
    print("\n2. VERIFICAR NGROK:")
    print("   Terminal 2:")
    print("   > ngrok http 8000")
    print("   Copia la URL que aparece (ej: https://abc123.ngrok.io)")
    
    print("\n3. CONFIGURAR WEBHOOK:")
    print("   Para Twilio:")
    print("   - Ir a: https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn")
    print("   - Sandbox Settings")
    print("   - 'When a message comes in': https://TU-URL-NGROK/twilio/webhook/")
    print("   - Guardar")
    
    print("\n   Para Meta:")
    print("   - Ir a: https://developers.facebook.com/")
    print("   - Tu App > WhatsApp > Configuration")
    print("   - Webhook URL: https://TU-URL-NGROK/whatsapp/webhook/")
    print("   - Guardar")
    
    print("\n4. PROBAR:")
    print("   - Envía mensaje de prueba al número de WhatsApp")
    print("   - Revisa Terminal 1 (Django) para ver logs")
    print("   - Deberías ver: '🔵 ENTRANDO A procesar_mensaje_entrante'")
    
    print_separator()


def resumen_gamificacion():
    """Informar sobre gamificación desactivada"""
    print("🎮 ESTADO: Gamificación")
    print_separator()
    
    print("⚠️ GAMIFICACIÓN DESACTIVADA")
    print("\nCambios aplicados:")
    print("  ✅ Signals desactivados (core/apps.py)")
    print("  ✅ Bloque de puntos comentado (message_handler.py)")
    print("  ✅ Sin notificaciones de nivel")
    print("  ✅ Sin badges automáticos")
    
    print("\n📜 NUEVO ENFOQUE: CERTIFICADOS")
    print("  - Sistema profesional como Coursera")
    print("  - Certificados en PDF con QR")
    print("  - Código de verificación único")
    print("  - Envío automático por WhatsApp")
    
    print("\n📄 Documentación:")
    print("  - CERTIFICADOS.md")
    print("  - core/models_certificados.py")
    print("  - core/generador_certificados.py")
    
    print_separator()


def main():
    """Ejecutar todos los diagnósticos"""
    print("\n" + "="*70)
    print("  🔍 DIAGNÓSTICO COMPLETO DEL SISTEMA - EKI")
    print("="*70)
    
    try:
        diagnostico_mensajes()
        input("Presiona ENTER para continuar...")
        
        diagnostico_configuracion()
        input("Presiona ENTER para continuar...")
        
        diagnostico_servidor()
        input("Presiona ENTER para continuar...")
        
        diagnostico_estudiantes()
        input("Presiona ENTER para continuar...")
        
        resumen_gamificacion()
        input("Presiona ENTER para continuar...")
        
        soluciones_recomendadas()
        
        print("\n" + "="*70)
        print("  ✅ DIAGNÓSTICO COMPLETADO")
        print("="*70)
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
