"""
Generar certificado para Julián Esteban
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()

from core.models import Estudiante, Curso, ProgresoEstudiante
from core.certificado_service import crear_certificado_automatico, enviar_certificado_whatsapp

print("=" * 70)
print("🎓 GENERANDO CERTIFICADO PARA JULIÁN ESTEBAN")
print("=" * 70)

# Buscar estudiante
estudiante = Estudiante.objects.get(nombre="Julián Esteban")
curso = Curso.objects.get(nombre="Fundamentos del Cultivo de Café")
progreso = ProgresoEstudiante.objects.get(estudiante=estudiante, curso=curso)

print(f"\n👤 Estudiante: {estudiante.nombre}")
print(f"📚 Curso: {curso.nombre}")
print(f"✅ Completado: {progreso.completado}")
print(f"📅 Fecha completado: {progreso.fecha_completado}")

# Crear certificado
print("\n" + "=" * 70)
print("🔧 CREANDO CERTIFICADO...")
print("=" * 70)

certificado = crear_certificado_automatico(estudiante, curso)

if certificado:
    print(f"\n✅ CERTIFICADO CREADO:")
    print(f"   🔐 Código: {certificado.codigo_verificacion}")
    print(f"   📊 Calificación: {certificado.calificacion_final}%")
    print(f"   🏆 Mención: {certificado.obtener_mencion()}")
    print(f"   ✉️  Emitido: {'✅ Sí' if certificado.emitido else '❌ No'}")
    print(f"   📄 PDF: {'✅ Sí' if certificado.archivo_pdf else '❌ No'}")
    
    # Enviar por WhatsApp
    print("\n" + "=" * 70)
    print("📲 ENVIANDO POR WHATSAPP...")
    print("=" * 70)
    
    success = enviar_certificado_whatsapp(certificado)
    
    if success:
        print(f"\n✅ CERTIFICADO ENVIADO POR WHATSAPP A {estudiante.telefono}")
        print(f"\n📱 El estudiante recibirá:")
        print(f"   - Mensaje de felicitación")
        print(f"   - Link para descargar PDF")
        print(f"   - Link de verificación pública")
        print(f"   - Código único")
    else:
        print(f"\n⚠️  Error al enviar por WhatsApp")
        print(f"   Pero el certificado está generado y disponible en:")
        print(f"   http://localhost:8000/admin/core/certificado/{certificado.id}/change/")
    
    # Mostrar URLs
    print("\n" + "=" * 70)
    print("🔗 URLS IMPORTANTES")
    print("=" * 70)
    print(f"\nVer certificado en admin:")
    print(f"  http://localhost:8000/admin/core/certificado/{certificado.id}/change/")
    
    print(f"\nVerificar públicamente:")
    print(f"  {certificado.obtener_url_verificacion()}")
    
    if certificado.archivo_pdf:
        print(f"\nDescargar PDF:")
        print(f"  http://localhost:8000{certificado.archivo_pdf.url}")
    
    print(f"\n✅ LISTO - Certificado disponible para Julián Esteban")
else:
    print(f"\n❌ Error al crear el certificado")
