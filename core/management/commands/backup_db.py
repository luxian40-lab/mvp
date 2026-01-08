"""
Comando de Django para crear backups automáticos de la base de datos
Uso: python manage.py backup_db
"""
from django.core.management.base import BaseCommand
from django.conf import settings
import shutil
import os
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Crea un backup de la base de datos SQLite'

    def add_arguments(self, parser):
        parser.add_argument(
            '--keep-days',
            type=int,
            default=7,
            help='Días de backups a mantener (por defecto 7)'
        )

    def handle(self, *args, **options):
        keep_days = options['keep_days']
        
        # Directorio de backups
        backup_dir = os.path.join(settings.BASE_DIR, 'backups')
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
            self.stdout.write(self.style.SUCCESS(f'✅ Directorio de backups creado: {backup_dir}'))
        
        # Archivo de base de datos
        db_path = os.path.join(settings.BASE_DIR, 'db.sqlite3')
        
        if not os.path.exists(db_path):
            self.stdout.write(self.style.ERROR('❌ No se encontró la base de datos'))
            return
        
        # Nombre del backup con timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f'db_backup_{timestamp}.sqlite3'
        backup_path = os.path.join(backup_dir, backup_filename)
        
        try:
            # Crear backup
            self.stdout.write('📦 Creando backup...')
            shutil.copy2(db_path, backup_path)
            
            # Obtener tamaño del archivo
            size_mb = os.path.getsize(backup_path) / (1024 * 1024)
            
            self.stdout.write(self.style.SUCCESS(f'✅ Backup creado exitosamente'))
            self.stdout.write(f'   Archivo: {backup_filename}')
            self.stdout.write(f'   Tamaño: {size_mb:.2f} MB')
            self.stdout.write(f'   Ubicación: {backup_path}')
            
            # Limpiar backups antiguos
            self._cleanup_old_backups(backup_dir, keep_days)
            
            logger.info(f'Backup creado: {backup_filename} ({size_mb:.2f} MB)')
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error al crear backup: {str(e)}'))
            logger.error(f'Error en backup: {str(e)}')
    
    def _cleanup_old_backups(self, backup_dir, keep_days):
        """Elimina backups más antiguos que keep_days"""
        from datetime import timedelta
        
        cutoff_date = datetime.now() - timedelta(days=keep_days)
        deleted_count = 0
        
        for filename in os.listdir(backup_dir):
            if filename.startswith('db_backup_') and filename.endswith('.sqlite3'):
                filepath = os.path.join(backup_dir, filename)
                file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                
                if file_time < cutoff_date:
                    try:
                        os.remove(filepath)
                        deleted_count += 1
                        self.stdout.write(f'🗑️  Eliminado backup antiguo: {filename}')
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f'⚠️  No se pudo eliminar {filename}: {str(e)}'))
        
        if deleted_count > 0:
            self.stdout.write(self.style.SUCCESS(f'✅ {deleted_count} backup(s) antiguo(s) eliminado(s)'))
        else:
            self.stdout.write('ℹ️  No hay backups antiguos para eliminar')
