"""
Script para probar el asistente de IA local
Simula conversaciones sin necesidad de WhatsApp
"""
import os
import sys
from pathlib import Path

# Agregar el directorio del proyecto al path
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
import django
django.setup()

from core.ai_assistant import EkiAIAssistant, responder_con_ia
from core.models import Estudiante, WhatsappLog
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

def verificar_openai():
    """Verifica que OpenAI esté configurado"""
    api_key = os.environ.get('OPENAI_API_KEY')
    
    if not api_key:
        print("❌ OPENAI_API_KEY no está configurada en el archivo .env")
        print("\n📝 Para configurarla:")
        print("   1. Ve a https://platform.openai.com/api-keys")
        print("   2. Crea una nueva API key")
        print("   3. Agrégala al archivo .env:")
        print("      OPENAI_API_KEY=sk-proj-...")
        return False
    
    print(f"✅ OpenAI API Key configurada: {api_key[:10]}...{api_key[-4:]}")
    return True

def crear_estudiante_prueba():
    """Crea un estudiante de prueba si no existe"""
    telefono = "573001234567"  # Número de prueba
    
    estudiante, created = Estudiante.objects.get_or_create(
        telefono=telefono,
        defaults={
            'nombre': 'Juan Pérez (Prueba)',
            'activo': True
        }
    )
    
    if created:
        print(f"✅ Estudiante de prueba creado: {estudiante.nombre}")
    else:
        print(f"✅ Usando estudiante existente: {estudiante.nombre}")
    
    return estudiante

def simular_conversacion():
    """Simula una conversación con el asistente de IA"""
    
    print("\n" + "=" * 70)
    print("🤖 SIMULADOR DE CONVERSACIÓN CON IA")
    print("=" * 70)
    
    # Verificar OpenAI
    if not verificar_openai():
        return
    
    # Crear estudiante de prueba
    estudiante = crear_estudiante_prueba()
    
    print(f"\n📱 Conversación con: {estudiante.nombre} ({estudiante.telefono})")
    print("=" * 70)
    
    try:
        assistant = EkiAIAssistant()
        
        # Mensajes de ejemplo para probar
        mensajes_prueba = [
            "Hola, ¿cómo estás?",
            "¿Cuál es mi progreso?",
            "¿Qué tareas tengo pendientes?",
            "Necesito ayuda con matemáticas",
        ]
        
        print("\n🎯 OPCIONES:")
        print("1. Conversación interactiva (tú escribes)")
        print("2. Prueba automática con mensajes predefinidos")
        print("3. Ver historial de conversación")
        
        opcion = input("\nElige una opción (1, 2 o 3): ").strip()
        
        if opcion == "3":
            # Ver historial
            logs = WhatsappLog.objects.filter(
                telefono=estudiante.telefono
            ).order_by('-fecha')[:10]
            
            if not logs:
                print("\n📭 No hay mensajes en el historial")
            else:
                print(f"\n📜 ÚLTIMOS {logs.count()} MENSAJES:")
                print("=" * 70)
                for log in reversed(logs):
                    tipo = "👤 Tú" if log.estado == "INCOMING" else "🤖 Eki"
                    print(f"\n{tipo} ({log.fecha.strftime('%d/%m %H:%M')}):")
                    print(f"   {log.mensaje}")
            
            return
        
        elif opcion == "2":
            # Prueba automática
            print("\n🤖 INICIANDO PRUEBA AUTOMÁTICA")
            print("=" * 70)
            
            for i, mensaje in enumerate(mensajes_prueba, 1):
                print(f"\n[{i}/{len(mensajes_prueba)}] 👤 Tú: {mensaje}")
                print("-" * 70)
                
                # Guardar mensaje del usuario
                WhatsappLog.objects.create(
                    telefono=estudiante.telefono,
                    mensaje=mensaje,
                    estado='INCOMING'
                )
                
                # Generar respuesta
                respuesta = assistant.generar_respuesta(mensaje, estudiante.telefono)
                
                print(f"🤖 Eki: {respuesta}")
                
                # Guardar respuesta
                WhatsappLog.objects.create(
                    telefono=estudiante.telefono,
                    mensaje=respuesta,
                    estado='SENT'
                )
                
                if i < len(mensajes_prueba):
                    input("\n⏸️ Presiona Enter para continuar...")
        
        else:
            # Conversación interactiva
            print("\n💬 MODO INTERACTIVO")
            print("=" * 70)
            print("Escribe tus mensajes (escribe 'salir' para terminar)")
            print("-" * 70)
            
            while True:
                mensaje_usuario = input("\n👤 Tú: ").strip()
                
                if mensaje_usuario.lower() in ['salir', 'exit', 'quit']:
                    print("👋 ¡Hasta luego!")
                    break
                
                if not mensaje_usuario:
                    continue
                
                # Guardar mensaje del usuario
                WhatsappLog.objects.create(
                    telefono=estudiante.telefono,
                    mensaje=mensaje_usuario,
                    estado='INCOMING'
                )
                
                # Generar respuesta
                print("\n🤖 Eki está pensando...")
                respuesta = assistant.generar_respuesta(mensaje_usuario, estudiante.telefono)
                
                print(f"\n🤖 Eki: {respuesta}")
                
                # Guardar respuesta
                WhatsappLog.objects.create(
                    telefono=estudiante.telefono,
                    mensaje=respuesta,
                    estado='SENT'
                )
    
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 70)
    print("✅ SIMULACIÓN COMPLETADA")
    print("=" * 70)
    print(f"\n💡 Los mensajes se guardaron en WhatsappLog")
    print(f"   Puedes verlos en el admin: http://localhost:8000/admin/core/whatsapplog/")


if __name__ == "__main__":
    simular_conversacion()
