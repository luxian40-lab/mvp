"""
Listar TODOS los estudiantes con sus progresos y certificados
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()

from core.models import Estudiante, ProgresoEstudiante
from core.models_certificados import Certificado

print("=" * 80)
print("📋 TODOS LOS ESTUDIANTES - PROGRESO Y CERTIFICADOS")
print("=" * 80)

estudiantes = Estudiante.objects.all().order_by('-id')

for estudiante in estudiantes:
    print(f"\n{'='*80}")
    print(f"👤 {estudiante.nombre} ({estudiante.telefono})")
    print(f"{'='*80}")
    
    progresos = ProgresoEstudiante.objects.filter(estudiante=estudiante)
    
    if not progresos.exists():
        print("   📚 Sin cursos inscritos")
        continue
    
    for progreso in progresos:
        print(f"\n   📖 {progreso.curso.nombre}")
        print(f"      📊 Avance: {progreso.porcentaje_avance()}%")
        print(f"      ✅ Completado: {'Sí' if progreso.completado else 'No'}")
        
        if progreso.fecha_completado:
            print(f"      📅 Completado el: {progreso.fecha_completado.strftime('%d/%m/%Y %H:%M')}")
        
        # Buscar certificado
        certificado = Certificado.objects.filter(
            estudiante=estudiante,
            curso=progreso.curso
        ).first()
        
        if certificado:
            print(f"      📜 CERTIFICADO:")
            print(f"         🔐 Código: {certificado.codigo_verificacion}")
            print(f"         📊 Calificación: {certificado.calificacion_final}%")
            print(f"         📄 PDF: {'✅' if certificado.archivo_pdf else '❌'}")
            print(f"         📲 Enviado: {'✅' if certificado.enviado_whatsapp else '❌'}")
            print(f"         🔗 Ver: http://localhost:8000/admin/core/certificado/{certificado.id}/change/")
        else:
            if progreso.completado:
                print(f"      ⚠️  ¡CURSO COMPLETO PERO SIN CERTIFICADO!")
            else:
                print(f"      📜 Sin certificado (curso no completado)")

print("\n" + "=" * 80)
print("📊 RESUMEN GLOBAL")
print("=" * 80)

total_estudiantes = Estudiante.objects.count()
cursos_completados = ProgresoEstudiante.objects.filter(completado=True).count()
certificados_emitidos = Certificado.objects.filter(emitido=True).count()
certificados_enviados = Certificado.objects.filter(enviado_whatsapp=True).count()

print(f"👥 Total estudiantes: {total_estudiantes}")
print(f"✅ Cursos completados: {cursos_completados}")
print(f"📜 Certificados emitidos: {certificados_emitidos}")
print(f"📲 Certificados enviados: {certificados_enviados}")

# Buscar cursos completados sin certificado
sin_certificado = ProgresoEstudiante.objects.filter(completado=True).exclude(
    curso__certificados_emitidos__estudiante__in=Estudiante.objects.all()
)

if sin_certificado.exists():
    print(f"\n⚠️  CURSOS COMPLETADOS SIN CERTIFICADO: {sin_certificado.count()}")
    for p in sin_certificado:
        print(f"   - {p.estudiante.nombre}: {p.curso.nombre}")
