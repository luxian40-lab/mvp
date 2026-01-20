"""
Script para resetear estudiante y probar flujo de habeas data completo
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()

from core.models import Estudiante

print("🔄 RESETEAR ESTUDIANTE PARA PRUEBA DE HABEAS DATA\n")
print("=" * 60)

# Buscar estudiante para prueba (puedes cambiar el teléfono)
telefono_prueba = input("\n📱 Ingresa el teléfono del estudiante a resetear (con 57): ")

try:
    estudiante = Estudiante.objects.get(telefono=telefono_prueba)
    
    print(f"\n✅ Estudiante encontrado: {estudiante.nombre}")
    print(f"   Teléfono: {estudiante.telefono}")
    print(f"   Aceptó términos: {estudiante.acepto_terminos}")
    print(f"   Estado onboarding: {estudiante.estado_onboarding}")
    
    confirmar = input("\n¿Resetear este estudiante? (s/n): ")
    
    if confirmar.lower() == 's':
        # Resetear campos de habeas data
        estudiante.acepto_terminos = False
        estudiante.fecha_aceptacion_terminos = None
        estudiante.estado_onboarding = 'nuevo'
        estudiante.tipo_documento = None
        estudiante.cedula = None
        estudiante.save()
        
        print("\n✅ Estudiante reseteado exitosamente")
        print("\n📋 Estado actual:")
        print(f"   - acepto_terminos: {estudiante.acepto_terminos}")
        print(f"   - estado_onboarding: {estudiante.estado_onboarding}")
        print(f"   - tipo_documento: {estudiante.tipo_documento}")
        print(f"   - cedula: {estudiante.cedula}")
        print("\n🎯 Ahora envía un mensaje desde WhatsApp para probar el flujo completo")
        
    else:
        print("\n❌ Operación cancelada")

except Estudiante.DoesNotExist:
    print(f"\n❌ No se encontró estudiante con teléfono: {telefono_prueba}")
    print("\n📝 Creando nuevo estudiante de prueba...")
    
    nombre = input("Nombre temporal: ")
    
    estudiante = Estudiante.objects.create(
        telefono=telefono_prueba,
        nombre=nombre,
        acepto_terminos=False,
        estado_onboarding='nuevo'
    )
    
    print(f"\n✅ Estudiante creado: {estudiante.nombre}")
    print("🎯 Envía un mensaje desde WhatsApp para iniciar el flujo")

print("\n" + "=" * 60)
print("\n📋 FLUJO ESPERADO:")
print("1. Usuario envía primer mensaje")
print("2. Sistema pide aceptar términos")
print("3. Usuario responde 'sí'")
print("4. Sistema pide tipo de documento (1-4)")
print("5. Usuario responde número")
print("6. Sistema pide número de documento")
print("7. Usuario responde número")
print("8. Sistema pide nombre")
print("9. Usuario responde nombre")
print("10. Sistema muestra menú principal con 3 opciones")
print("\n" + "=" * 60)
