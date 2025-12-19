#!/usr/bin/env python
"""
Script de prueba local para la Fase 1.
Simula un mensaje de WhatsApp, ejecuta el detector de intents y genera respuestas.
No necesita token real ni ngrok, todo es local.
"""
import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()

from core.intent_detector import detect_intent
from core.response_templates import get_response_for_intent
from core.models import Estudiante, WhatsappLog


def simulate_whatsapp_message(telefono: str, mensaje: str, crear_estudiante: bool = True):
    """
    Simula la llegada de un mensaje de WhatsApp y ejecuta el flujo completo.
    
    Args:
        telefono: número del usuario (ej. 573026480629)
        mensaje: texto del mensaje
        crear_estudiante: si True, crea un estudiante mock si no existe
    """
    
    print("\n" + "="*70)
    print(f"📱 MENSAJE ENTRANTE DE {telefono}")
    print("="*70)
    print(f"Texto: {mensaje}")
    
    # 1. Crear estudiante mock si no existe
    if crear_estudiante:
        estudiante, creado = Estudiante.objects.get_or_create(
            telefono=telefono,
            defaults={'nombre': 'Estudiante Test', 'activo': True}
        )
        if creado:
            print(f"✅ Estudiante creado: {estudiante.nombre}")
        else:
            print(f"📋 Estudiante existente: {estudiante.nombre}")
    else:
        try:
            estudiante = Estudiante.objects.get(telefono=telefono)
        except Estudiante.DoesNotExist:
            print("⚠️  Estudiante no encontrado, usaré nombre genérico")
            estudiante = None
    
    # 2. Guardar log entrante
    log_entrada = WhatsappLog.objects.create(
        telefono=telefono,
        mensaje=mensaje,
        estado='INCOMING'
    )
    print(f"📥 Log guardado: {log_entrada.id}")
    
    # 3. Detectar intent
    intent = detect_intent(mensaje)
    print(f"\n🔍 Intent detectado: '{intent}'")
    
    # 4. Obtener datos del estudiante para respuesta
    nombre_usuario = estudiante.nombre if estudiante else "Estudiante"
    datos_respuesta = {
        'progreso': '50%',
        'modulo_actual': 'Introducción a la Plataforma',
        'siguiente_tarea': 'Completa tu perfil',
        'fecha_vence': 'hoy'
    }
    
    # 5. Generar respuesta
    respuesta = get_response_for_intent(intent, nombre_usuario, **datos_respuesta)
    print(f"\n💬 RESPUESTA GENERADA:")
    print("-" * 70)
    print(respuesta)
    print("-" * 70)
    
    # 6. Guardar log de respuesta (simulando envío)
    log_salida = WhatsappLog.objects.create(
        telefono=telefono,
        mensaje=respuesta,
        estado='SENT'  # En producción, solo se marca como SENT si la API de Meta responde 200
    )
    print(f"\n📤 Respuesta registrada: {log_salida.id}")
    
    print("\n✅ Flujo completado exitosamente\n")
    
    return {
        'intent': intent,
        'respuesta': respuesta,
        'log_entrada_id': log_entrada.id,
        'log_salida_id': log_salida.id
    }


def main():
    """Ejecuta pruebas del flujo Fase 1."""
    
    print("\n" + "="*70)
    print("🚀 PRUEBA LOCAL - FASE 1 (Intent Detector + Response Templates)")
    print("="*70)
    
    telefono_test = '573026480629'
    
    # Test 1: Saludo
    print("\n\n📌 TEST 1: Saludo")
    simulate_whatsapp_message(telefono_test, "Hola!")
    
    # Test 2: Opción 1 (Progreso)
    print("\n\n📌 TEST 2: Opción 1 (Progreso)")
    simulate_whatsapp_message(telefono_test, "1")
    
    # Test 3: Opción 2 (Tareas)
    print("\n\n📌 TEST 3: Opción 2 (Tareas)")
    simulate_whatsapp_message(telefono_test, "2")
    
    # Test 4: Opción 3 (Ayuda)
    print("\n\n📌 TEST 4: Opción 3 (Ayuda)")
    simulate_whatsapp_message(telefono_test, "3")
    
    # Test 5: Palabra clave (progreso)
    print("\n\n📌 TEST 5: Palabra clave 'progreso'")
    simulate_whatsapp_message(telefono_test, "¿Cuál es mi progreso?")
    
    # Test 6: Palabra clave (tareas)
    print("\n\n📌 TEST 6: Palabra clave 'tareas'")
    simulate_whatsapp_message(telefono_test, "¿Qué tareas tengo?")
    
    # Test 7: Intent desconocido
    print("\n\n📌 TEST 7: Intent desconocido")
    simulate_whatsapp_message(telefono_test, "Me gusta el chocolate")
    
    # Resumen final
    print("\n\n" + "="*70)
    print("📊 RESUMEN DE LOGS GUARDADOS")
    print("="*70)
    logs = WhatsappLog.objects.filter(telefono=telefono_test).order_by('-fecha')
    for i, log in enumerate(logs[:14], 1):  # Últimos 14 (7 entradas + 7 salidas)
        tipo = "📥 ENTRADA" if log.estado == 'INCOMING' else "📤 SALIDA"
        print(f"{i}. {tipo} | {log.estado:10} | {log.mensaje[:50]}...")
    
    print("\n✅ Todas las pruebas completadas\n")


if __name__ == '__main__':
    main()
