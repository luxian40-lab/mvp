"""
Verificar que cada módulo tiene preguntas relacionadas
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()

from core.models import PreguntaModulo, Modulo, Curso

print("=" * 70)
print("📝 VERIFICACIÓN DE PREGUNTAS POR MÓDULO")
print("=" * 70)

for curso in Curso.objects.all():
    print(f"\n🎓 CURSO: {curso.nombre}")
    print("-" * 70)
    
    modulos = curso.modulos.all().order_by('numero')
    
    for modulo in modulos:
        print(f"\n  📚 Módulo {modulo.numero}: {modulo.titulo}")
        
        preguntas = modulo.preguntas.filter(activa=True)
        
        if preguntas.exists():
            for i, pregunta in enumerate(preguntas, 1):
                print(f"     ✅ Pregunta {i}: {pregunta.pregunta[:60]}...")
                print(f"        A) {pregunta.opcion_a[:40]}...")
                print(f"        B) {pregunta.opcion_b[:40]}...")
                if pregunta.opcion_c:
                    print(f"        C) {pregunta.opcion_c[:40]}...")
                if pregunta.opcion_d:
                    print(f"        D) {pregunta.opcion_d[:40]}...")
                print(f"        ✔️  Respuesta correcta: {pregunta.respuesta_correcta}")
        else:
            print(f"     ⚠️  SIN PREGUNTAS ASIGNADAS")
    
    print()

print("\n" + "=" * 70)
print("📊 RESUMEN")
print("=" * 70)

total_modulos = Modulo.objects.count()
modulos_con_pregunta = Modulo.objects.filter(preguntas__activa=True).distinct().count()
modulos_sin_pregunta = total_modulos - modulos_con_pregunta

print(f"Total de módulos: {total_modulos}")
print(f"Módulos CON pregunta: {modulos_con_pregunta} ✅")
print(f"Módulos SIN pregunta: {modulos_sin_pregunta} ⚠️")

if modulos_sin_pregunta > 0:
    print("\n⚠️  MÓDULOS SIN PREGUNTAS:")
    for modulo in Modulo.objects.all():
        if not modulo.preguntas.filter(activa=True).exists():
            print(f"   - {modulo.curso.nombre} → {modulo.titulo}")
