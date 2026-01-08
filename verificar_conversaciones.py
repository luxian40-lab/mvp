"""
Script para verificar el estado de las conversaciones en la base de datos
"""
import os
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()

from core.models import Estudiante, WhatsappLog, EnvioLog

print("\n" + "="*60)
print("🔍 DIAGNÓSTICO DE CONVERSACIONES")
print("="*60 + "\n")

# 1. Estudiantes
total_estudiantes = Estudiante.objects.count()
print(f"👥 Total de estudiantes: {total_estudiantes}")

# 2. WhatsappLog
total_whatsapp = WhatsappLog.objects.count()
whatsapp_con_estudiante = WhatsappLog.objects.filter(estudiante__isnull=False).count()
whatsapp_sin_estudiante = WhatsappLog.objects.filter(estudiante__isnull=True).count()
whatsapp_incoming = WhatsappLog.objects.filter(tipo='INCOMING').count()
whatsapp_sent = WhatsappLog.objects.filter(tipo='SENT').count()

print(f"\n💬 Mensajes de WhatsApp:")
print(f"   - Total: {total_whatsapp}")
print(f"   - Con estudiante asignado: {whatsapp_con_estudiante}")
print(f"   - Sin estudiante asignado: {whatsapp_sin_estudiante}")
print(f"   - Mensajes recibidos (INCOMING): {whatsapp_incoming}")
print(f"   - Mensajes enviados (SENT): {whatsapp_sent}")

# 3. EnvioLog
total_envios = EnvioLog.objects.count()
envios_con_estudiante = EnvioLog.objects.filter(estudiante__isnull=False).count()

print(f"\n📤 Mensajes de campañas:")
print(f"   - Total: {total_envios}")
print(f"   - Con estudiante asignado: {envios_con_estudiante}")

# 4. Estudiantes con mensajes
estudiantes_con_whatsapp = WhatsappLog.objects.filter(estudiante__isnull=False).values_list('estudiante_id', flat=True).distinct()
estudiantes_con_envios = EnvioLog.objects.filter(estudiante__isnull=False).values_list('estudiante_id', flat=True).distinct()

total_con_conversaciones = len(set(list(estudiantes_con_whatsapp) + list(estudiantes_con_envios)))

print(f"\n✅ Estudiantes con conversaciones: {total_con_conversaciones}")

# 5. Ejemplos
print(f"\n📋 EJEMPLOS DE DATOS:")

if total_whatsapp > 0:
    print("\n🔵 Últimos 5 mensajes WhatsApp:")
    for msg in WhatsappLog.objects.select_related('estudiante').order_by('-fecha')[:5]:
        estudiante_nombre = msg.estudiante.nombre if msg.estudiante else "❌ Sin asignar"
        tipo_emoji = "📥" if msg.tipo == 'INCOMING' else "📤"
        tipo_texto = "Recibido" if msg.tipo == 'INCOMING' else "Enviado"
        print(f"   {tipo_emoji} {msg.fecha.strftime('%Y-%m-%d %H:%M')} | {estudiante_nombre} | {tipo_texto} | {msg.mensaje[:40]}...")
else:
    print("\n⚠️  No hay mensajes de WhatsApp en la base de datos")

if total_envios > 0:
    print("\n🟢 Últimos 3 envíos de campañas:")
    for envio in EnvioLog.objects.select_related('estudiante', 'campana').order_by('-fecha_envio')[:3]:
        estudiante_nombre = envio.estudiante.nombre if envio.estudiante else "❌ Sin asignar"
        campana_nombre = envio.campana.nombre if envio.campana else "Sin campaña"
        print(f"   - {envio.fecha_envio.strftime('%Y-%m-%d %H:%M')} | {estudiante_nombre} | {campana_nombre}")
else:
    print("\n⚠️  No hay envíos de campañas en la base de datos")

# 6. Recomendaciones
print("\n" + "="*60)
print("💡 RECOMENDACIONES:")
print("="*60)

if total_con_conversaciones == 0:
    print("\n⚠️  NO HAY CONVERSACIONES PARA MOSTRAR")
    print("\nPara ver conversaciones, necesitas:")
    print("1. ✅ Tener estudiantes registrados")
    print("2. ✅ Que los estudiantes envíen mensajes por WhatsApp")
    print("3. ✅ O crear y enviar campañas a estudiantes")
    print("\n💡 Opciones:")
    print("   - Envía un mensaje de prueba al bot de WhatsApp")
    print("   - Crea una campaña desde el admin de Django")
    print("   - Importa estudiantes con teléfonos válidos")
else:
    print(f"\n✅ Tienes {total_con_conversaciones} estudiantes con conversaciones")
    print("   Las conversaciones deberían aparecer en /admin/conversaciones/")
    
    if whatsapp_sin_estudiante > 0:
        print(f"\n⚠️  ATENCIÓN: Hay {whatsapp_sin_estudiante} mensajes sin estudiante asignado")
        print("   Solución: Asegúrate de que los teléfonos de WhatsApp coincidan con los de estudiantes")

print("\n" + "="*60 + "\n")
