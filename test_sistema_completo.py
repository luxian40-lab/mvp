"""
Script de prueba rápida del sistema completo de mensajes proactivos
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
from core.services import enviar_bienvenida_nuevo_estudiante
from dotenv import load_dotenv

load_dotenv()


def main():
    print("\n" + "="*60)
    print("🚀 TEST RÁPIDO: Sistema de Mensajes Proactivos")
    print("="*60)
    
    # 1. Verificar configuración
    print("\n📋 Verificando configuración...")
    
    sid = os.getenv('TWILIO_ACCOUNT_SID')
    if not sid:
        print("❌ TWILIO_ACCOUNT_SID no configurado")
        return
    
    print(f"✅ Twilio configurado: {sid[:20]}...")
    
    # 2. Seleccionar estudiante de prueba
    print("\n📱 Estudiantes disponibles:")
    estudiantes = Estudiante.objects.filter(activo=True)[:5]
    
    if not estudiantes.exists():
        print("❌ No hay estudiantes activos. Crea uno primero.")
        crear = input("\n¿Crear estudiante de prueba? (s/n): ").strip().lower()
        
        if crear == 's':
            nombre = input("Nombre: ").strip()
            telefono = input("Teléfono (+57...): ").strip()
            
            if not telefono.startswith('+'):
                telefono = '+' + telefono
            
            estudiante = Estudiante.objects.create(
                nombre=nombre,
                telefono=telefono,
                activo=True
            )
            print(f"✅ Estudiante creado: {estudiante.nombre}")
        else:
            return
    else:
        for i, est in enumerate(estudiantes, 1):
            print(f"{i}. {est.nombre} - {est.telefono}")
        
        opcion = input("\nSelecciona estudiante (número) o presiona Enter para el primero: ").strip()
        
        if opcion.isdigit() and 1 <= int(opcion) <= estudiantes.count():
            estudiante = estudiantes[int(opcion) - 1]
        else:
            estudiante = estudiantes.first()
    
    print(f"\n👤 Estudiante seleccionado: {estudiante.nombre}")
    print(f"📞 Teléfono: {estudiante.telefono}")
    
    # 3. Enviar mensaje de bienvenida
    print("\n📤 Enviando mensaje de bienvenida...")
    print("(Este mensaje llegará al WhatsApp del estudiante)")
    
    confirmar = input("\n¿Continuar? (s/n): ").strip().lower()
    
    if confirmar != 's':
        print("❌ Cancelado")
        return
    
    resultado = enviar_bienvenida_nuevo_estudiante(estudiante)
    
    print("\n" + "="*60)
    print("📊 RESULTADO")
    print("="*60)
    
    if resultado.get('exito'):
        print("✅ ¡Mensaje enviado exitosamente!")
        print(f"📱 Message SID: {resultado.get('mensaje_id', 'N/A')}")
        print(f"🎯 Método usado: {resultado.get('metodo_usado', 'desconocido').upper()}")
        print("\n💡 El estudiante debería recibir el mensaje en su WhatsApp")
        print("💡 Cuando responda, tu webhook lo recibirá y la IA contestará")
        
        print("\n📋 PRÓXIMOS PASOS:")
        print("1. Verifica el mensaje en WhatsApp")
        print("2. Responde desde WhatsApp")
        print("3. Verifica que tu webhook reciba la respuesta")
        print("4. Verifica que la IA responda automáticamente")
        
    else:
        print("❌ Error al enviar mensaje")
        print(f"Error: {resultado.get('error', 'Desconocido')}")
        
        error_msg = resultado.get('error', '').lower()
        
        if 'sandbox' in error_msg or '63007' in error_msg:
            print("\n💡 SOLUCIÓN:")
            print("El número debe enviar 'join [code]' primero al Sandbox")
            print("O upgrade tu cuenta Twilio a producción")
        
        elif 'template' in error_msg:
            print("\n💡 SOLUCIÓN:")
            print("Verifica que el template esté aprobado en Twilio Console")
    
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
