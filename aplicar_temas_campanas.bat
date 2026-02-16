@echo off
cd /d "%~dp0"
echo.
echo ============================================================
echo    CREANDO MIGRACION: Temas de Campaña
echo ============================================================
echo.

.venv\Scripts\python.exe manage.py makemigrations core

echo.
echo ============================================================
echo    APLICANDO MIGRACION
echo ============================================================
echo.

.venv\Scripts\python.exe manage.py migrate core

echo.
echo ============================================================
echo    CREANDO TEMAS DE EJEMPLO
echo ============================================================
echo.

.venv\Scripts\python.exe -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()

from core.models import TemaCampana

# Temas de cultivos
temas_crear = [
    {'nombre': 'Café', 'emoji': '☕', 'descripcion': 'Plantillas relacionadas con cultivo de café'},
    {'nombre': 'Aguacate', 'emoji': '🥑', 'descripcion': 'Plantillas relacionadas con cultivo de aguacate'},
    {'nombre': 'Maíz', 'emoji': '🌽', 'descripcion': 'Plantillas relacionadas con cultivo de maíz'},
    {'nombre': 'Yuca', 'emoji': '🥔', 'descripcion': 'Plantillas relacionadas con cultivo de yuca'},
    {'nombre': 'Plátano', 'emoji': '🍌', 'descripcion': 'Plantillas relacionadas con cultivo de plátano'},
    {'nombre': 'Motivación General', 'emoji': '💪', 'descripcion': 'Mensajes motivacionales generales'},
    {'nombre': 'Recordatorios', 'emoji': '⏰', 'descripcion': 'Mensajes de recordatorio de cursos'},
    {'nombre': 'Bienvenida', 'emoji': '👋', 'descripcion': 'Mensajes de bienvenida y onboarding'},
]

print('\\nCreando temas de campaña...')
for tema_data in temas_crear:
    tema, created = TemaCampana.objects.get_or_create(
        nombre=tema_data['nombre'],
        defaults={
            'emoji': tema_data['emoji'],
            'descripcion': tema_data['descripcion'],
            'activo': True
        }
    )
    if created:
        print(f'  ✅ {tema}')
    else:
        print(f'  ℹ️  {tema} ya existe')

print(f'\\n✅ Total de temas: {TemaCampana.objects.count()}')
"

echo.
echo ============================================================
echo    COMPLETADO
echo ============================================================
echo.
echo Presiona cualquier tecla para cerrar...
pause >nul
