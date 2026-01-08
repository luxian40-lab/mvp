"""
Script para crear datos de prueba para las conversaciones
"""
import os
import django
from datetime import timedelta

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()

from core.models import Estudiante, WhatsappLog
from django.utils import timezone

print("\n" + "="*60)
print("🎯 CREANDO DATOS DE PRUEBA PARA CONVERSACIONES")
print("="*60 + "\n")

# Verificar si ya hay estudiantes
total_estudiantes = Estudiante.objects.count()
print(f"👥 Estudiantes existentes: {total_estudiantes}")

if total_estudiantes == 0:
    print("\n⚠️  No hay estudiantes. Creando estudiante de prueba...")
    estudiante = Estudiante.objects.create(
        nombre="Juan Pérez",
        telefono="573001234567",
        correo="juan.perez@test.com",
        nivel_educativo="Primaria"
    )
    print(f"✅ Estudiante creado: {estudiante.nombre} - {estudiante.telefono}")
else:
    estudiante = Estudiante.objects.first()
    print(f"✅ Usando estudiante existente: {estudiante.nombre}")

# Verificar mensajes existentes
total_mensajes = WhatsappLog.objects.filter(estudiante=estudiante).count()
print(f"\n💬 Mensajes existentes para {estudiante.nombre}: {total_mensajes}")

if total_mensajes > 0:
    print("\n⚠️  Este estudiante ya tiene mensajes. ¿Deseas crear más de todas formas?")
    respuesta = input("Escribe 'si' para continuar: ")
    if respuesta.lower() != 'si':
        print("❌ Cancelado.")
        exit()

print("\n📝 Creando conversación de prueba...")

# Conversación simulada
conversacion = [
    # Mensaje 1: Estudiante pregunta
    {
        'tipo': 'INCOMING',
        'mensaje': 'Hola, necesito ayuda con el tema de matemáticas',
        'tiempo': -10  # hace 10 minutos
    },
    # Respuesta 1: Bot responde
    {
        'tipo': 'SENT',
        'mensaje': '¡Hola Juan! 👋 Claro que sí, estoy aquí para ayudarte con matemáticas. ¿Qué tema específico te está costando trabajo?',
        'tiempo': -9
    },
    # Mensaje 2: Estudiante explica
    {
        'tipo': 'INCOMING',
        'mensaje': 'Es que no entiendo las fracciones',
        'tiempo': -8
    },
    # Respuesta 2: Bot explica
    {
        'tipo': 'SENT',
        'mensaje': '📊 Perfecto, las fracciones son muy útiles. Una fracción representa una parte de un todo. Por ejemplo: 1/2 significa "1 de 2 partes iguales", es decir, la mitad. ¿Quieres que te explique con ejemplos prácticos del campo?',
        'tiempo': -7
    },
    # Mensaje 3: Estudiante pide más info
    {
        'tipo': 'INCOMING',
        'mensaje': 'Sí, con ejemplos del campo por favor',
        'tiempo': -6
    },
    # Respuesta 3: Bot da ejemplos
    {
        'tipo': 'SENT',
        'mensaje': '🌾 ¡Excelente! Imagina que tienes 1 hectárea de tierra:\n\n• 1/2 hectárea = la mitad del terreno\n• 1/4 hectárea = una cuarta parte\n• 3/4 hectárea = tres cuartas partes\n\nSi plantas maíz en 1/2 de tu terreno y yuca en 1/4, ¿cuánto terreno usaste en total?',
        'tiempo': -5
    },
    # Mensaje 4: Estudiante intenta responder
    {
        'tipo': 'INCOMING',
        'mensaje': 'Creo que 3/4?',
        'tiempo': -3
    },
    # Respuesta 4: Bot confirma
    {
        'tipo': 'SENT',
        'mensaje': '🎉 ¡Correcto! Muy bien, Juan. 1/2 + 1/4 = 3/4. Has usado tres cuartas partes de tu terreno. ¿Te gustaría practicar más con otros ejercicios?',
        'tiempo': -2
    },
    # Mensaje 5: Estudiante agradece
    {
        'tipo': 'INCOMING',
        'mensaje': 'Sí, me gustaría practicar más',
        'tiempo': -1
    },
    # Respuesta 5: Bot motiva
    {
        'tipo': 'SENT',
        'mensaje': '💪 ¡Excelente actitud! Aquí va otro ejercicio:\n\nTienes 8 costales de café. Le das 1/4 a tu vecino. ¿Cuántos costales le diste?\n\nPista: Divide 8 entre 4 😊',
        'tiempo': 0
    }
]

print(f"\n📤 Guardando {len(conversacion)} mensajes...")

for i, msg_data in enumerate(conversacion, 1):
    # Calcular fecha del mensaje
    fecha_mensaje = timezone.now() + timedelta(minutes=msg_data['tiempo'])
    
    # Crear mensaje
    msg = WhatsappLog.objects.create(
        telefono=estudiante.telefono,
        mensaje=msg_data['mensaje'],
        mensaje_id=f"test_msg_{timezone.now().timestamp()}_{i}",
        tipo=msg_data['tipo'],
        estado='SENT' if msg_data['tipo'] == 'SENT' else 'RECEIVED',
        estudiante=estudiante,
        fecha=fecha_mensaje
    )
    
    tipo_emoji = "📥" if msg.tipo == 'INCOMING' else "📤"
    print(f"   {tipo_emoji} Mensaje {i}/{len(conversacion)}: {msg.tipo}")

print("\n" + "="*60)
print("✅ CONVERSACIÓN DE PRUEBA CREADA EXITOSAMENTE")
print("="*60)
print(f"\n🎯 Accede a las conversaciones:")
print(f"   http://127.0.0.1:8000/admin/conversaciones/?estudiante={estudiante.id}")
print(f"\n👤 Estudiante: {estudiante.nombre}")
print(f"📱 Teléfono: {estudiante.telefono}")
print(f"💬 Mensajes creados: {len(conversacion)}")
print("\n")
