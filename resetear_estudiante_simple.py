"""
Resetear estudiante específico para pruebas frescas
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()

from core.models import Estudiante

# Cambiar este teléfono por el que quieras resetear
TELEFONO = input("Teléfono a resetear (ej: 573026480629): ").strip()

try:
    estudiante = Estudiante.objects.get(telefono=TELEFONO)
    
    print(f"\n🔍 Estudiante encontrado: {estudiante.nombre}")
    print(f"   📞 Teléfono: {estudiante.telefono}")
    print(f"   📝 Estado: {estudiante.estado_onboarding}")
    
    confirmar = input("\n⚠️ ¿Resetear este estudiante? (s/n): ").strip().lower()
    
    if confirmar == 's':
        # Limpiar progreso
        estudiante.progresos.all().delete()
        
        # Limpiar contexto temporal
        estudiante.contexto_temporal = None
        estudiante.estado_onboarding = 'completado'
        estudiante.save()
        
        # Resetear gamificación
        from core.gamificacion import PerfilGamificacion
        perfil = PerfilGamificacion.objects.filter(estudiante=estudiante).first()
        if perfil:
            perfil.puntos_totales = 0
            perfil.nivel = 1
            perfil.modulos_completados = 0
            perfil.cursos_completados = 0
            perfil.racha_dias_actual = 0
            perfil.save()
            print("   ✅ Gamificación reseteada")
        
        print(f"\n✅ Estudiante {estudiante.nombre} reseteado exitosamente")
        print("\n📱 Ahora puedes probar desde WhatsApp:")
        print("   1. Enviar: '2' (ver cursos)")
        print("   2. Enviar: 'TOMAR 1' (inscribirse)")
        print("   3. Enviar: 'CONTINUAR' (ver módulo)")
        print("   4. Enviar: 'LISTO' (completar → pregunta)")
        print("   5. Enviar: 'A' (responder pregunta)")
        print("   6. Ver siguiente módulo automático")
    else:
        print("❌ Cancelado")
        
except Estudiante.DoesNotExist:
    print(f"❌ No existe estudiante con teléfono: {TELEFONO}")
    print("\n💡 Sugerencia: Verifica el formato (ej: 573026480629)")
