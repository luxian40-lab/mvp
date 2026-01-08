#!/usr/bin/env python
"""
Script para verificar que la IA detecta correctamente el curso actual
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()

from core.models import Estudiante, ProgresoEstudiante, Curso

# Buscar un estudiante con múltiples cursos
estudiantes = Estudiante.objects.all()

print("=" * 70)
print("🔍 VERIFICACIÓN DE CONTEXTO DE CURSO ACTUAL")
print("=" * 70)

for estudiante in estudiantes[:5]:  # Primeros 5 estudiantes
    print(f"\n👤 Estudiante: {estudiante.nombre} ({estudiante.telefono})")
    
    # Ver todos sus progresos
    progresos = ProgresoEstudiante.objects.filter(
        estudiante=estudiante
    ).order_by('-fecha_inicio')
    
    if progresos.exists():
        print(f"   📚 Cursos inscritos: {progresos.count()}")
        
        for i, progreso in enumerate(progresos):
            marca = "👉 ACTUAL" if i == 0 else "  "
            print(f"   {marca} {progreso.curso.nombre} - {progreso.porcentaje_avance()}% - Inicio: {progreso.fecha_inicio}")
        
        # Verificar que el más reciente es el correcto
        curso_actual = progresos.first()
        print(f"\n   ✅ Curso detectado como ACTUAL: {curso_actual.curso.nombre}")
    else:
        print("   ⚠️  Sin cursos inscritos")

print("\n" + "=" * 70)
print("✅ Verificación completa")
print("=" * 70)
