"""
Verificar certificados del estudiante Julian
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()

from core.models import Estudiante, ProgresoEstudiante
from core.models_certificados import Certificado

print("=" * 70)
print("🔍 VERIFICACIÓN DE CERTIFICADOS - JULIAN")
print("=" * 70)

# Buscar estudiante por contexto (el que usó WhatsApp)
estudiante = Estudiante.objects.filter(nombre__icontains="julian").first()
if not estudiante:
    # Buscar el último estudiante activo
    estudiante = Estudiante.objects.filter(activo=True).first()

if not estudiante:
    print("❌ No se encontró estudiante")
    exit(1)

print(f"\n👤 Estudiante: {estudiante.nombre}")
print(f"📱 Teléfono: {estudiante.telefono}")

# Ver progreso
print("\n" + "=" * 70)
print("📚 CURSOS Y PROGRESO")
print("=" * 70)

progresos = ProgresoEstudiante.objects.filter(estudiante=estudiante)

for progreso in progresos:
    print(f"\n📖 {progreso.curso.nombre}")
    print(f"   ✅ Completado: {progreso.completado}")
    print(f"   📊 Avance: {progreso.porcentaje_avance()}%")
    if progreso.fecha_completado:
        print(f"   📅 Fecha completado: {progreso.fecha_completado}")
    
    # Verificar si tiene certificado
    certificado = Certificado.objects.filter(
        estudiante=estudiante,
        curso=progreso.curso
    ).first()
    
    if certificado:
        print(f"   📜 CERTIFICADO ENCONTRADO:")
        print(f"      🔐 Código: {certificado.codigo_verificacion}")
        print(f"      📊 Calificación: {certificado.calificacion_final}%")
        print(f"      ✉️  Emitido: {'✅ Sí' if certificado.emitido else '❌ No'}")
        print(f"      📲 Enviado WhatsApp: {'✅ Sí' if certificado.enviado_whatsapp else '❌ No'}")
        if certificado.archivo_pdf:
            print(f"      📄 PDF: {certificado.archivo_pdf.name}")
        
        print(f"\n   🔗 URLs:")
        print(f"      Admin: http://localhost:8000/admin/core/certificado/{certificado.id}/change/")
        print(f"      Verificar: {certificado.obtener_url_verificacion()}")
        if certificado.archivo_pdf:
            print(f"      Descargar: http://localhost:8000{certificado.archivo_pdf.url}")
    else:
        print(f"   ⚠️  NO TIENE CERTIFICADO")
        if progreso.completado:
            print(f"      ❗ PROBLEMA: Curso completado pero sin certificado")
            print(f"      💡 Solución: Generar certificado manualmente desde admin")

print("\n" + "=" * 70)
print("📊 RESUMEN")
print("=" * 70)

total_certificados = Certificado.objects.filter(estudiante=estudiante).count()
print(f"Total de certificados: {total_certificados}")

if total_certificados == 0 and progresos.filter(completado=True).exists():
    print("\n⚠️  ACCIÓN REQUERIDA:")
    print("   El estudiante completó curso(s) pero no tiene certificados.")
    print("   Opciones:")
    print("   1. Ir a: http://localhost:8000/admin/core/certificado/")
    print("   2. Click en 'Agregar certificado'")
    print("   3. O ejecutar script de generación automática")
