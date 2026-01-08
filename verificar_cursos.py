import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()

from core.models import Curso

print("CURSOS EN BASE DE DATOS:")
print("=" * 50)

cursos = Curso.objects.filter(activo=True).order_by('orden')
for idx, curso in enumerate(cursos, 1):
    print(f"\nPosición en lista: {idx}")
    print(f"ID real: {curso.id}")
    print(f"Nombre: {curso.nombre}")
    print(f"Emoji: {curso.emoji}")
    print(f"Orden: {curso.orden}")

print("\n" + "=" * 50)
print("PROBLEMA: Si el usuario escribe '3', ¿qué curso se inscribe?")
print("=" * 50)
print("\nLógica actual en inscribir_curso:")
print("- Toma la posición (idx) en la lista ordenada")
print("- Si usuario escribe '3', debería inscribir el curso en posición 3")
print("\nVerificando si coincide con Plátano...")
if len(cursos) >= 3:
    curso_posicion_3 = list(cursos)[2]  # índice 2 = posición 3
    print(f"\nCurso en posición 3: {curso_posicion_3.nombre}")
    print(f"ID: {curso_posicion_3.id}")
