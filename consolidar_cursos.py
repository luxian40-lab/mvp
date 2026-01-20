"""
Script para consolidar cursos duplicados
Dejamos 4 cursos bien hechos de temas diversos
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()

from core.models import Curso, Modulo, ProgresoEstudiante

print("🔍 CONSOLIDANDO CURSOS...\n")
print("=" * 60)

# Ver cursos actuales
cursos = Curso.objects.all()
print("\n📚 CURSOS ACTUALES:")
for c in cursos:
    modulos = c.modulos.count()
    print(f"   {c.id}. {c.emoji} {c.nombre} ({modulos} módulos)")

print("\n" + "=" * 60)

# Consolidación: Eliminar duplicados manteniendo los mejores
print("\n🔧 CONSOLIDANDO...")

# CAFÉ: Eliminar ID 4, mantener ID 2 (Cultivo de Café Arábigo)
cafe_viejo = Curso.objects.filter(id=4).first()
if cafe_viejo:
    # Mover progresos al curso consolidado
    ProgresoEstudiante.objects.filter(curso=cafe_viejo).update(curso_id=2)
    print(f"\n❌ Eliminando: {cafe_viejo.nombre}")
    cafe_viejo.delete()
    print("   ✅ Progresos migrados a 'Cultivo de Café Arábigo'")

# AGUACATE: Eliminar ID 5, mantener ID 1 (Producción de Aguacate Hass)
aguacate_viejo = Curso.objects.filter(id=5).first()
if aguacate_viejo:
    # Mover progresos al curso consolidado
    ProgresoEstudiante.objects.filter(curso=aguacate_viejo).update(curso_id=1)
    print(f"\n❌ Eliminando: {aguacate_viejo.nombre}")
    aguacate_viejo.delete()
    print("   ✅ Progresos migrados a 'Producción de Aguacate Hass'")

print("\n" + "=" * 60)
print("\n✅ CURSOS CONSOLIDADOS:")

cursos_final = Curso.objects.all().order_by('orden')
for idx, c in enumerate(cursos_final, 1):
    modulos = c.modulos.count()
    print(f"   {idx}. {c.emoji} {c.nombre} ({modulos} módulos)")

print("\n" + "=" * 60)
print("\n🎉 CONSOLIDACIÓN COMPLETADA!")
print("\nTenemos 3 cursos. Necesitamos agregar 1 curso más diverso.")
print("Sugerencias: Ganadería, Cacao, Cultivos de Pancoger, etc.\n")
