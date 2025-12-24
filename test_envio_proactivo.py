"""
Script de prueba para envío de mensajes proactivos con Twilio
"""

import os
import sys
import django
from pathlib import Path

# Setup Django
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()

from core.models import Estudiante
from core.services import enviar_mensaje_proactivo_inteligente
from core.twilio_templates import (
    enviar_bienvenida,
    enviar_recordatorio_clase,
    enviar_notificacion_tarea,
    enviar_mensaje_proactivo_simple
)
from dotenv import load_dotenv

load_dotenv()


def verificar_configuracion():
    """Verifica que Twilio esté configurado"""
    print("\n" + "="*60)
    print("🔍 VERIFICANDO CONFIGURACIÓN")
    print("="*60)
    
    sid = os.getenv('TWILIO_ACCOUNT_SID')
    token = os.getenv('TWILIO_AUTH_TOKEN')
    numero = os.getenv('TWILIO_WHATSAPP_NUMBER')
    
    print(f"✅ Twilio Account SID: {sid[:20]}..." if sid else "❌ Twilio Account SID no configurado")
    print(f"✅ Twilio Auth Token: {'*' * 20}..." if token else "❌ Twilio Auth Token no configurado")
    print(f"✅ WhatsApp Number: {numero}" if numero else "❌ WhatsApp Number no configurado")
    
    # Templates
    templates = {
        'Bienvenida': os.getenv('TWILIO_TEMPLATE_BIENVENIDA'),
        'Recordatorio': os.getenv('TWILIO_TEMPLATE_RECORDATORIO'),
        'Tarea': os.getenv('TWILIO_TEMPLATE_TAREA'),
        'Progreso': os.getenv('TWILIO_TEMPLATE_PROGRESO'),
    }
    
    print("\n📋 Templates configurados:")
    for nombre, sid in templates.items():
        if sid:
            print(f"  ✅ {nombre}: {sid}")
        else:
            print(f"  ⚠️  {nombre}: No configurado (opcional hasta aprobación)")
    
    if not sid or not token:
        print("\n❌ ERROR: Faltan credenciales de Twilio")
        return False
    
    return True


def menu_principal():
    """Menú principal del script"""
    print("\n" + "="*60)
    print("📱 TEST DE ENVÍO PROACTIVO - TWILIO WHATSAPP")
    print("="*60)
    print("\nOpciones:")
    print("1. 📨 Enviar mensaje de BIENVENIDA (texto libre)")
    print("2. 🎓 Enviar RECORDATORIO de clase (texto libre)")
    print("3. 📚 Enviar notificación de TAREA (texto libre)")
    print("4. 📊 Enviar REPORTE de progreso (texto libre)")
    print("5. 🎯 Usar TEMPLATE aprobado (requiere SID)")
    print("6. 🤖 Modo INTELIGENTE (auto-detecta ventana 24h)")
    print("0. ❌ Salir")
    print("="*60)
    
    return input("\nSelecciona una opción: ").strip()


def obtener_numero_telefono():
    """Solicita número de teléfono al usuario"""
    print("\n📞 Ingresa el número de WhatsApp:")
    print("Formato: +57XXXXXXXXXX (incluir código país)")
    telefono = input("Número: ").strip()
    
    if not telefono.startswith('+'):
        telefono = '+' + telefono
    
    return telefono


def test_mensaje_bienvenida():
    """Test de mensaje de bienvenida"""
    print("\n" + "="*60)
    print("📨 TEST: MENSAJE DE BIENVENIDA")
    print("="*60)
    
    telefono = obtener_numero_telefono()
    nombre = input("Nombre del estudiante: ").strip() or "Estudiante"
    
    print(f"\n📤 Enviando mensaje de bienvenida a {telefono}...")
    
    # Crear mensaje de texto libre
    texto = f"""¡Hola {nombre}! 👋 Bienvenido a Eki Educación.

Soy tu asistente virtual inteligente. Puedo ayudarte con:

✅ Consultar tus tareas pendientes
✅ Ver tu horario de clases
✅ Revisar tu progreso académico
✅ Recordatorios importantes

¿En qué puedo ayudarte hoy?"""
    
    from core.twilio_templates import enviar_mensaje_proactivo_simple
    resultado = enviar_mensaje_proactivo_simple(telefono, texto)
    
    mostrar_resultado(resultado)


def test_recordatorio_clase():
    """Test de recordatorio de clase"""
    print("\n" + "="*60)
    print("🎓 TEST: RECORDATORIO DE CLASE")
    print("="*60)
    
    telefono = obtener_numero_telefono()
    nombre = input("Nombre del estudiante: ").strip() or "Estudiante"
    materia = input("Materia (ej: Matemáticas): ").strip() or "Matemáticas"
    hora = input("Hora (ej: 10:00am): ").strip() or "10:00am"
    tema = input("Tema (ej: Ecuaciones): ").strip() or "Revisar contenido"
    
    print(f"\n📤 Enviando recordatorio a {telefono}...")
    
    texto = f"""¡Hola {nombre}! 🎓

Recordatorio: Tienes clase de {materia} hoy a las {hora}.

📍 Tema: {tema}

¿Necesitas ayuda con algo antes de la clase?"""
    
    from core.twilio_templates import enviar_mensaje_proactivo_simple
    resultado = enviar_mensaje_proactivo_simple(telefono, texto)
    
    mostrar_resultado(resultado)


def test_notificacion_tarea():
    """Test de notificación de tarea"""
    print("\n" + "="*60)
    print("📚 TEST: NOTIFICACIÓN DE TAREA")
    print("="*60)
    
    telefono = obtener_numero_telefono()
    nombre = input("Nombre del estudiante: ").strip() or "Estudiante"
    materia = input("Materia: ").strip() or "General"
    fecha_entrega = input("Fecha entrega (ej: 25 de Diciembre): ").strip() or "pronto"
    dias = input("Días restantes: ").strip() or "varios"
    
    print(f"\n📤 Enviando notificación a {telefono}...")
    
    texto = f"""📚 Nueva tarea asignada

Hola {nombre},

Se ha asignado una nueva tarea:

📖 Materia: {materia}
📅 Fecha de entrega: {fecha_entrega}
⏰ Faltan {dias} días

Responde "detalles" para ver más información."""
    
    from core.twilio_templates import enviar_mensaje_proactivo_simple
    resultado = enviar_mensaje_proactivo_simple(telefono, texto)
    
    mostrar_resultado(resultado)


def test_reporte_progreso():
    """Test de reporte de progreso"""
    print("\n" + "="*60)
    print("📊 TEST: REPORTE DE PROGRESO")
    print("="*60)
    
    telefono = obtener_numero_telefono()
    nombre = input("Nombre del estudiante: ").strip() or "Estudiante"
    tareas = input("Tareas completadas (ej: 8/10): ").strip() or "N/A"
    clases = input("Clases asistidas (ej: 4/5): ").strip() or "N/A"
    promedio = input("Promedio (ej: 4.5): ").strip() or "N/A"
    mensaje = input("Mensaje motivacional: ").strip() or "¡Excelente trabajo!"
    
    print(f"\n📤 Enviando reporte a {telefono}...")
    
    texto = f"""📊 Reporte Semanal

Hola {nombre},

Tu progreso esta semana:

✅ Tareas completadas: {tareas}
📚 Clases asistidas: {clases}
🎯 Promedio: {promedio}

¡{mensaje}!

¿Quieres ver detalles?"""
    
    from core.twilio_templates import enviar_mensaje_proactivo_simple
    resultado = enviar_mensaje_proactivo_simple(telefono, texto)
    
    mostrar_resultado(resultado)


def test_template_aprobado():
    """Test usando template aprobado"""
    print("\n" + "="*60)
    print("🎯 TEST: USAR TEMPLATE APROBADO")
    print("="*60)
    print("\n⚠️  NOTA: Esto solo funciona si ya creaste y aprobaron tu template en Twilio")
    
    telefono = obtener_numero_telefono()
    nombre = input("Nombre del estudiante: ").strip() or "Estudiante"
    
    print("\nTemplates disponibles:")
    print("1. bienvenida")
    print("2. recordatorio")
    print("3. tarea")
    print("4. progreso")
    
    template = input("\nSelecciona template (número o nombre): ").strip()
    
    template_map = {
        '1': 'bienvenida',
        '2': 'recordatorio',
        '3': 'tarea',
        '4': 'progreso'
    }
    
    template_name = template_map.get(template, template)
    
    print(f"\n📤 Enviando template '{template_name}' a {telefono}...")
    
    if template_name == 'bienvenida':
        resultado = enviar_bienvenida(telefono, nombre)
    else:
        print("⚠️  Para otros templates, usa la función enviar_mensaje_proactivo_inteligente")
        return
    
    mostrar_resultado(resultado)


def test_modo_inteligente():
    """Test del sistema inteligente que detecta ventana 24h"""
    print("\n" + "="*60)
    print("🤖 TEST: MODO INTELIGENTE (Auto-detecta ventana 24h)")
    print("="*60)
    print("\nEste modo:")
    print("✅ Detecta si usuario respondió en últimas 24h")
    print("✅ Si SÍ: Usa texto libre")
    print("✅ Si NO: Usa template aprobado")
    
    telefono = obtener_numero_telefono()
    
    # Verificar si estudiante existe en BD
    from core.models import Estudiante
    estudiante = Estudiante.objects.filter(telefono=telefono).first()
    
    if not estudiante:
        print(f"\n⚠️  Estudiante con {telefono} no existe en BD.")
        crear = input("¿Crear estudiante de prueba? (s/n): ").strip().lower()
        
        if crear == 's':
            nombre = input("Nombre: ").strip() or "Estudiante Prueba"
            estudiante = Estudiante.objects.create(
                nombre=nombre,
                telefono=telefono,
                activo=True
            )
            print(f"✅ Estudiante creado: {estudiante.nombre}")
        else:
            return
    
    print("\nTipos de mensaje disponibles:")
    print("1. bienvenida")
    print("2. recordatorio")
    print("3. tarea")
    print("4. progreso")
    
    tipo = input("\nSelecciona tipo: ").strip()
    tipo_map = {'1': 'bienvenida', '2': 'recordatorio', '3': 'tarea', '4': 'progreso'}
    tipo_mensaje = tipo_map.get(tipo, tipo)
    
    print(f"\n📤 Enviando mensaje inteligente tipo '{tipo_mensaje}'...")
    
    # Preparar kwargs según tipo
    kwargs = {}
    if tipo_mensaje == 'recordatorio':
        kwargs = {
            'materia': 'Matemáticas',
            'hora': '10:00am',
            'tema': 'Ecuaciones cuadráticas'
        }
    elif tipo_mensaje == 'tarea':
        kwargs = {
            'materia': 'Historia',
            'fecha_entrega': '25 de Diciembre',
            'dias_restantes': '2'
        }
    elif tipo_mensaje == 'progreso':
        kwargs = {
            'semana': 'Semana 12',
            'tareas_completadas': '8/10',
            'clases_asistidas': '4/5',
            'promedio': '4.5',
            'mensaje_motivacional': '¡Excelente trabajo!'
        }
    
    resultado = enviar_mensaje_proactivo_inteligente(estudiante, tipo_mensaje, **kwargs)
    
    print(f"\n📋 Método usado: {resultado.get('metodo_usado', 'desconocido').upper()}")
    mostrar_resultado(resultado)


def mostrar_resultado(resultado):
    """Muestra el resultado del envío"""
    print("\n" + "="*60)
    print("📊 RESULTADO")
    print("="*60)
    
    if resultado.get('exito'):
        print("✅ ¡Mensaje enviado exitosamente!")
        print(f"📱 Message SID: {resultado.get('mensaje_id', 'N/A')}")
        if 'metodo_usado' in resultado:
            print(f"🎯 Método: {resultado['metodo_usado']}")
        print("\n💡 Revisa tu WhatsApp para ver el mensaje")
    else:
        print("❌ Error al enviar mensaje")
        print(f"Error: {resultado.get('error', 'Desconocido')}")
        
        error_msg = resultado.get('error', '').lower()
        
        if 'sandbox' in error_msg or '63007' in error_msg:
            print("\n💡 SOLUCIÓN:")
            print("1. El número debe enviar 'join [code]' primero al Sandbox")
            print("2. O upgrade tu cuenta a producción")
        
        elif 'template' in error_msg or 'content' in error_msg:
            print("\n💡 SOLUCIÓN:")
            print("1. Verifica que el template esté aprobado en Twilio Console")
            print("2. Confirma que el Content SID esté en .env")
        
        elif 'credentials' in error_msg or 'auth' in error_msg:
            print("\n💡 SOLUCIÓN:")
            print("Verifica tus credenciales en .env:")
            print("  - TWILIO_ACCOUNT_SID")
            print("  - TWILIO_AUTH_TOKEN")
    
    print("="*60)


def main():
    """Función principal"""
    if not verificar_configuracion():
        print("\n❌ Por favor configura Twilio en tu archivo .env")
        return
    
    while True:
        opcion = menu_principal()
        
        if opcion == '0':
            print("\n👋 ¡Hasta luego!")
            break
        elif opcion == '1':
            test_mensaje_bienvenida()
        elif opcion == '2':
            test_recordatorio_clase()
        elif opcion == '3':
            test_notificacion_tarea()
        elif opcion == '4':
            test_reporte_progreso()
        elif opcion == '5':
            test_template_aprobado()
        elif opcion == '6':
            test_modo_inteligente()
        else:
            print("\n❌ Opción inválida")
        
        input("\nPresiona ENTER para continuar...")


if __name__ == "__main__":
    main()
