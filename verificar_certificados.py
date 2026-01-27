#!/usr/bin/env python
"""
Script para verificar y activar certificados PDF
Genera los PDFs faltantes y verifica que todo esté correcto
"""

import os
import sys
import django
import logging

def main():
    try:
        # Setup Django
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
        django.setup()
        from django.conf import settings
        from core.models_certificados import Certificado, PlantillaCertificado
        from core.certificado_service import generar_y_guardar_certificado
        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
        print("=" * 70)
        print("🎓 VERIFICADOR DE CERTIFICADOS")
        print("=" * 70)
        # 1. Verificar configuración
        print("\n📋 CONFIGURACIÓN DEL SISTEMA:")
        print(f"   MEDIA_ROOT: {settings.MEDIA_ROOT}")
        print(f"   MEDIA_URL: {settings.MEDIA_URL}")
        print(f"   DEBUG: {settings.DEBUG}")
        # 2. Crear directorio si no existe
        media_path = os.path.join(settings.MEDIA_ROOT, 'certificados')
        if not os.path.exists(media_path):
            os.makedirs(media_path, exist_ok=True)
            print(f"\n✅ Creado directorio: {media_path}")
        else:
            print(f"\n✅ Directorio existe: {media_path}")
        # 3. Verificar plantillas
        plantillas = PlantillaCertificado.objects.filter(activa=True)
        print(f"\n📄 PLANTILLAS DISPONIBLES:")
        for p in plantillas:
            marca = "📌" if p.por_defecto else "  "
            print(f"   {marca} {p.nombre} (ID: {p.id})")
        if not plantillas.exists():
            print("   ❌ No hay plantillas activas")
            sys.exit(1)
        # 4. Listar certificados y generar PDFs faltantes
        certificados = Certificado.objects.filter(emitido=True).order_by('-fecha_emision')
        print(f"\n🏆 CERTIFICADOS EMITIDOS: {certificados.count()}")
        if not certificados.exists():
            print("   ℹ️  No hay certificados emitidos aún")
        else:
            sin_pdf = certificados.filter(archivo_pdf='')
            con_pdf = certificados.exclude(archivo_pdf='')
            print(f"\n   ✅ Con PDF: {con_pdf.count()}")
            print(f"   ❌ Sin PDF: {sin_pdf.count()}")
            if sin_pdf.exists():
                print(f"\n   Generando {sin_pdf.count()} PDFs faltantes...\n")
                for idx, cert in enumerate(sin_pdf, 1):
                    print(f"   [{idx}/{sin_pdf.count()}] Generando: {cert.codigo_verificacion}")
                    # Generar PDF
                    success = generar_y_guardar_certificado(cert)
                    if success:
                        print(f"       ✅ OK - Archivo: {cert.archivo_pdf}")
                    else:
                        print(f"       ❌ Error generando PDF")
                print()
        logging.info("Verificación de certificados ejecutada correctamente.")
    except Exception as e:
        logging.exception("Error en la verificación de certificados")
        print(f"\n[ERROR] {e}\n")
        sys.exit(1)

if __name__ == "__main__":
    main()

# 5. Verificar integridad de archivos
print("✅ VERIFICACIÓN DE INTEGRIDAD:\n")
todos_ok = True

for cert in certificados.exclude(archivo_pdf=''):
    try:
        # Verificar que el archivo existe
        ruta_archivo = os.path.join(settings.MEDIA_ROOT, cert.archivo_pdf.name)
        
        if os.path.exists(ruta_archivo):
            tamaño = os.path.getsize(ruta_archivo)
            print(f"   ✅ {cert.codigo_verificacion}")
            print(f"      → {ruta_archivo}")
            print(f"      → Tamaño: {tamaño} bytes")
        else:
            print(f"   ⚠️  {cert.codigo_verificacion}")
            print(f"      → Archivo no encontrado: {ruta_archivo}")
            todos_ok = False
            
    except Exception as e:
        print(f"   ❌ {cert.codigo_verificacion}")
        print(f"      → Error: {e}")
        todos_ok = False

# 6. Resumen
print("\n" + "=" * 70)
if todos_ok:
    print("✅ TODOS LOS CERTIFICADOS ESTÁN LISTOS")
else:
    print("⚠️  ALGUNOS CERTIFICADOS NECESITAN ATENCIÓN")
print("=" * 70)

# 7. URLs de verificación
print("\n🔗 URLS PARA VERIFICAR CERTIFICADOS:")
for cert in certificados[:3]:  # Mostrar los primeros 3
    print(f"   • /certificado/verificar/{cert.codigo_verificacion}/")
if certificados.count() > 3:
    print(f"   ... y {certificados.count() - 3} más")
