#!/usr/bin/env python
"""
SCRIPT: Backup de Certificados
Respalda todos los certificados PDF y genera un archivo ZIP
"""

import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()

from core.models_certificados import Certificado
from django.conf import settings
import shutil
from datetime import datetime
import zipfile

def crear_backup_certificados():
    """Crea un ZIP con todos los certificados"""
    print("\n" + "="*80)
    print("💾 BACKUP DE CERTIFICADOS")
    print("="*80)
    
    # Crear directorio de backup
    backup_dir = os.path.join(settings.BASE_DIR, 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    
    # Nombre del archivo ZIP
    fecha = datetime.now().strftime('%Y%m%d_%H%M%S')
    zip_name = f"certificados_backup_{fecha}.zip"
    zip_path = os.path.join(backup_dir, zip_name)
    
    # Ruta de certificados
    media_certificados = os.path.join(settings.MEDIA_ROOT, 'certificados')
    
    if not os.path.exists(media_certificados):
        print(f"❌ Directorio de certificados no encontrado: {media_certificados}")
        return False
    
    # Contar certificados
    certificados = Certificado.objects.filter(emitido=True, archivo_pdf__isnull=False)
    total = certificados.count()
    
    print(f"\n📊 Total de certificados a respaldar: {total}")
    
    if total == 0:
        print("⚠️  No hay certificados para respaldar")
        return False
    
    # Crear ZIP
    print(f"📦 Creando archivo: {zip_name}...")
    
    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for cert in certificados:
                if cert.archivo_pdf:
                    pdf_path = os.path.join(settings.MEDIA_ROOT, str(cert.archivo_pdf))
                    if os.path.exists(pdf_path):
                        # Agregar al ZIP con estructura de carpetas
                        arcname = f"certificados/{cert.codigo_verificacion}.pdf"
                        zipf.write(pdf_path, arcname)
                        print(f"  ✅ {cert.codigo_verificacion} ({cert.estudiante.nombre})")
        
        # Información del backup
        file_size = os.path.getsize(zip_path) / (1024 * 1024)  # Convertir a MB
        
        print("\n" + "="*80)
        print("✅ BACKUP COMPLETADO")
        print("="*80)
        print(f"📁 Ubicación: {zip_path}")
        print(f"📊 Tamaño: {file_size:.2f} MB")
        print(f"📜 Certificados respal dados: {total}")
        print(f"📅 Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        
        # Crear resumen
        resumen_path = os.path.join(backup_dir, f"resumen_backup_{fecha}.txt")
        with open(resumen_path, 'w', encoding='utf-8') as f:
            f.write(f"RESUMEN DE BACKUP - {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
            f.write("="*80 + "\n\n")
            f.write(f"Total de certificados: {total}\n")
            f.write(f"Tamaño del backup: {file_size:.2f} MB\n")
            f.write(f"Archivo: {zip_name}\n\n")
            f.write("CERTIFICADOS INCLUIDOS:\n")
            f.write("-"*80 + "\n")
            for cert in certificados:
                f.write(f"{cert.codigo_verificacion} | {cert.estudiante.nombre} | {cert.curso.nombre} | {cert.calificacion_final}%\n")
        
        print(f"📝 Resumen: {resumen_path}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error al crear backup: {str(e)}")
        return False

def listar_backups():
    """Lista los backups disponibles"""
    backup_dir = os.path.join(settings.BASE_DIR, 'backups')
    
    if not os.path.exists(backup_dir):
        print("No hay backups disponibles")
        return
    
    backups = [f for f in os.listdir(backup_dir) if f.endswith('.zip')]
    
    if not backups:
        print("No hay archivos de backup (.zip)")
        return
    
    print("\n📦 BACKUPS DISPONIBLES:")
    print("-"*80)
    for backup in sorted(backups):
        path = os.path.join(backup_dir, backup)
        size = os.path.getsize(path) / (1024 * 1024)
        print(f"• {backup} ({size:.2f} MB)")

if __name__ == '__main__':
    print("\n¿Qué deseas hacer?")
    print("1. Crear nuevo backup")
    print("2. Listar backups existentes")
    
    opcion = input("\nOpción (1/2): ").strip()
    
    if opcion == '1':
        crear_backup_certificados()
    elif opcion == '2':
        listar_backups()
    else:
        print("Opción inválida")
