"""
Script para crear temas de campaña de ejemplo
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()

from core.models import TemaCampana

print("\n" + "="*60)
print("🏷️  CREANDO TEMAS DE CAMPAÑA")
print("="*60 + "\n")

# Temas de cultivos y categorías
temas_crear = [
    {
        'nombre': 'Café',
        'emoji': '☕',
        'descripcion': 'Plantillas relacionadas con el cultivo de café arábigo, mantenimiento, cosecha y procesamiento.'
    },
    {
        'nombre': 'Aguacate',
        'emoji': '🥑',
        'descripcion': 'Plantillas sobre cultivo de aguacate Hass, injertos, poda y control de plagas.'
    },
    {
        'nombre': 'Maíz',
        'emoji': '🌽',
        'descripcion': 'Información sobre siembra, fertilización y cosecha de maíz.'
    },
    {
        'nombre': 'Yuca',
        'emoji': '🥔',
        'descripcion': 'Guías para el cultivo de yuca, preparación del suelo y control de enfermedades.'
    },
    {
        'nombre': 'Plátano',
        'emoji': '🍌',
        'descripcion': 'Técnicas de cultivo de plátano, riego y manejo de la plantación.'
    },
    {
        'nombre': 'Cacao',
        'emoji': '🍫',
        'descripcion': 'Cultivo de cacao, fermentación y secado del grano.'
    },
    {
        'nombre': 'Motivación General',
        'emoji': '💪',
        'descripcion': 'Mensajes motivacionales para estudiantes, ánimo y perseverancia.'
    },
    {
        'nombre': 'Recordatorios',
        'emoji': '⏰',
        'descripcion': 'Recordatorios de cursos, tareas pendientes y fechas importantes.'
    },
    {
        'nombre': 'Bienvenida',
        'emoji': '👋',
        'descripcion': 'Mensajes de bienvenida a nuevos estudiantes y onboarding.'
    },
    {
        'nombre': 'Evaluaciones',
        'emoji': '📝',
        'descripcion': 'Información sobre exámenes, resultados y certificados.'
    },
    {
        'nombre': 'Técnicas Agrícolas',
        'emoji': '🌱',
        'descripcion': 'Técnicas generales de agricultura, rotación de cultivos y mejores prácticas.'
    },
]

print("Creando temas...")
print("")

creados = 0
existentes = 0

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
        print(f"  ✅ {tema} - CREADO")
        creados += 1
    else:
        print(f"  ℹ️  {tema} - Ya existe")
        existentes += 1

print("\n" + "="*60)
    import logging
    import sys
print("📊 RESUMEN")
print("="*60)
print(f"✅ Temas creados: {creados}")
print(f"ℹ️  Temas existentes: {existentes}")
print(f"📁 Total en base de datos: {TemaCampana.objects.count()}")

print("\n" + "="*60)
        try:
print("💡 PRÓXIMOS PASOS")
print("="*60)
            logging.info("Temas de campaña creados correctamente.")
        except Exception as e:
            logging.exception("Error al crear temas de campaña")
            print(f"\n[ERROR] {e}\n")
            sys.exit(1)
print("\n1. Accede al admin de Django: http://127.0.0.1:8000/admin/")
print("2. Ve a 'Temas de Campañas' para ver todos los temas")
        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
print("3. Edita tus plantillas y asócialas con temas")
print("4. Crea campañas y selecciona un tema")
print("5. Las plantillas se filtrarán automáticamente!\n")

print("🎯 EJEMPLO DE USO:")
print("─────────────────────────────────────────────────────────")
print("1. Tienes 5 plantillas sobre café ☕")
print("2. Asignas el tema 'Café' a todas ellas")
print("3. Creas una campaña 'Promoción Curso Café'")
print("4. Seleccionas tema 'Café' en la campaña")
print("5. Solo verás las 5 plantillas de café!\n")
