#!/usr/bin/env python
"""
Script de prueba local para Fase 2: API REST.
Simula llamadas HTTP a los endpoints de progreso sin necesidad de servidor.
"""
import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()

from django.test import Client
from django.test.utils import setup_test_environment, teardown_test_environment
from core.models import Estudiante, Campana, Plantilla, EnvioLog
from datetime import datetime, timedelta


def setup_test_data():
    """Crea datos de prueba para los tests."""
    print("\n🔧 Configurando datos de prueba...")
    
    # Crear estudiante
    estudiante, _ = Estudiante.objects.get_or_create(
        telefono='573026480629',
        defaults={'nombre': 'Juan Pérez', 'activo': True}
    )
    print(f"✅ Estudiante: {estudiante.nombre} ({estudiante.telefono})")
    
    # Crear plantilla
    plantilla, _ = Plantilla.objects.get_or_create(
        nombre_interno='Test Plantilla',
        defaults={'cuerpo_mensaje': 'Este es un mensaje de prueba para validar el sistema.'}
    )
    print(f"✅ Plantilla: {plantilla.nombre_interno}")
    
    # Crear campaña
    campana, _ = Campana.objects.get_or_create(
        nombre='Campaña Test',
        defaults={'plantilla': plantilla, 'ejecutada': False}
    )
    campana.destinatarios.add(estudiante)
    print(f"✅ Campaña: {campana.nombre}")
    
    # Crear algunos logs de envío para simular progreso
    for i in range(3):
        EnvioLog.objects.get_or_create(
            campana=campana,
            estudiante=estudiante,
            defaults={
                'estado': 'ENVIADO' if i < 2 else 'PENDIENTE',
                'respuesta_api': f'Message ID: {i}',
                'fecha_envio': datetime.now() - timedelta(days=i)
            }
        )
    
    enviados = EnvioLog.objects.filter(estudiante=estudiante, estado='ENVIADO').count()
    pendientes = EnvioLog.objects.filter(estudiante=estudiante, estado='PENDIENTE').count()
    print(f"✅ Logs de envío: {enviados} enviados, {pendientes} pendiente(s)")
    
    return estudiante


def test_endpoints():
    """Prueba los endpoints REST."""
    
    setup_test_environment()
    client = Client()
    estudiante = setup_test_data()
    telefono = estudiante.telefono
    
    print("\n" + "="*70)
    print("🚀 PRUEBA LOCAL - FASE 2 (API REST de Progreso)")
    print("="*70)
    
    # Test 1: GET /api/estudiante/{telefono}/
    print("\n\n📌 TEST 1: GET /api/estudiante/{telefono}/")
    print("-" * 70)
    response = client.get(f'/api/estudiante/{telefono}/')
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        data = json.loads(response.content)
        print(f"✅ Respuesta:")
        print(f"   Nombre: {data['estudiante']['nombre']}")
        print(f"   Teléfono: {data['estudiante']['telefono']}")
        print(f"   Activo: {data['estudiante']['activo']}")
    else:
        print(f"❌ Error: {response.content}")
    
    # Test 2: GET /api/estudiante/{telefono}/progreso/
    print("\n\n📌 TEST 2: GET /api/estudiante/{telefono}/progreso/")
    print("-" * 70)
    response = client.get(f'/api/estudiante/{telefono}/progreso/')
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        data = json.loads(response.content)
        print(f"✅ Respuesta:")
        prog = data['progreso']
        print(f"   Porcentaje: {prog['porcentaje']}%")
        print(f"   Total tareas: {prog['total_tareas']}")
        print(f"   Completadas: {prog['tareas_completadas']}")
        print(f"   Fallidas: {prog['tareas_fallidas']}")
        print(f"   Módulo actual: {prog['modulo_actual']}")
        print(f"   Estado: {prog['estado']}")
    else:
        print(f"❌ Error: {response.content}")
    
    # Test 3: GET /api/estudiante/{telefono}/siguiente-tarea/
    print("\n\n📌 TEST 3: GET /api/estudiante/{telefono}/siguiente-tarea/")
    print("-" * 70)
    response = client.get(f'/api/estudiante/{telefono}/siguiente-tarea/')
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        data = json.loads(response.content)
        print(f"✅ Respuesta:")
        tarea = data['siguiente_tarea']
        print(f"   Campaña: {tarea['campana']}")
        print(f"   Plantilla: {tarea['plantilla']}")
        print(f"   Descripción: {tarea['descripcion']}")
        print(f"   Vence: {tarea['fecha_vence']}")
        print(f"   Estado: {tarea['estado']}")
    else:
        print(f"❌ Error: {response.content}")
    
    # Test 4: Endpoint con teléfono inexistente
    print("\n\n📌 TEST 4: GET /api/estudiante/999999/progreso/ (No existe)")
    print("-" * 70)
    response = client.get('/api/estudiante/999999/progreso/')
    print(f"Status Code: {response.status_code}")
    if response.status_code == 404:
        data = json.loads(response.content)
        print(f"✅ Error esperado: {data['error']}")
    else:
        print(f"❌ Esperaba 404, obtuve {response.status_code}")
    
    print("\n\n" + "="*70)
    print("✅ Todas las pruebas de API REST completadas")
    print("="*70 + "\n")
    
    teardown_test_environment()


if __name__ == '__main__':
    test_endpoints()
