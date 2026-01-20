"""
Script para crear datos de ejemplo en el sistema de gamificación
Simula progreso de estudiantes para ver cómo funciona el sistema
"""
import os
import django
from datetime import datetime, timedelta
from random import randint, choice

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()

from core.gamificacion import PerfilGamificacion, Badge, BadgeEstudiante, TransaccionPuntos
from core.models import Estudiante
from core.gamificacion_actions import (
    otorgar_puntos_modulo,
    otorgar_puntos_examen,
    otorgar_puntos_curso_completado,
    otorgar_puntos_primer_curso
)

print("\n" + "="*70)
print("🎮 CREANDO DATOS DE EJEMPLO - GAMIFICACIÓN")
print("="*70 + "\n")

# Obtener o crear estudiantes de ejemplo
estudiantes_demo = []

estudiante_principal = Estudiante.objects.first()
if estudiante_principal:
    estudiantes_demo.append(estudiante_principal)
    print(f"✅ Estudiante encontrado: {estudiante_principal.nombre}")

# Crear algunos estudiantes de ejemplo adicionales (opcional)
from core.models import Cliente

# Obtener el cliente por defecto
cliente_default = Cliente.objects.first()

nombres_ejemplo = [
    ("María Rodríguez", "CC", "1234567890", "3001234567"),
    ("Carlos González", "CC", "1234567891", "3009876543"),
    ("Ana Martínez", "CC", "1234567892", "3007654321"),
    ("Pedro López", "CC", "1234567893", "3005432109"),
]

print("\n🧑‍🌾 Creando estudiantes de ejemplo...")
for nombre, tipo_doc, cedula, telefono in nombres_ejemplo:
    try:
        estudiante, created = Estudiante.objects.get_or_create(
            cedula=cedula,
            defaults={
                'nombre': nombre,
                'tipo_documento': tipo_doc,
                'telefono': telefono,
                'cliente': cliente_default
            }
        )
        if created:
            print(f"   ✅ {nombre} creado")
        else:
            print(f"   ℹ️ {nombre} ya existía")
        estudiantes_demo.append(estudiante)
    except Exception as e:
        print(f"   ⚠️ Error creando {nombre}: {str(e)[:50]}")
        continue

print(f"\n📊 Total de estudiantes: {len(estudiantes_demo)}")

# Simular progreso para cada estudiante
print("\n🎯 Simulando progreso de estudiantes...\n")

for estudiante in estudiantes_demo:
    print(f"\n👤 {estudiante.nombre}:")
    
    # Obtener o crear perfil
    perfil, _ = PerfilGamificacion.objects.get_or_create(estudiante=estudiante)
    
    # Simular actividad básica (entre 3 y 10 actividades)
    num_actividades = randint(3, 10)
    
    for i in range(num_actividades):
        # Simular completar módulos
        if i < num_actividades - 2:
            resultado = otorgar_puntos_modulo(estudiante)
            perfil.modulos_completados += 1
            perfil.save()
    
    # Simular algunos exámenes
    num_examenes = randint(1, 3)
    for i in range(num_examenes):
        puntaje = choice([70, 80, 85, 90, 95, 100])
        otorgar_puntos_examen(estudiante, puntaje)
        perfil.examenes_aprobados += 1
        perfil.save()
    
    # Algunos estudiantes completan un curso
    if randint(1, 100) > 50:
        otorgar_puntos_primer_curso(estudiante)
    
    # Simular racha aleatoria
    racha = randint(0, 15)
    perfil.racha_dias_actual = racha
    if racha > perfil.racha_dias_maxima:
        perfil.racha_dias_maxima = racha
    
    perfil.ultima_actividad = datetime.now() - timedelta(hours=randint(1, 48))
    perfil.save()
    
    # Actualizar nivel
    perfil.calcular_nivel()
    perfil.actualizar_racha()
    
    # Mostrar resultado
    badges_count = BadgeEstudiante.objects.filter(estudiante=estudiante).count()
    print(f"   📊 Nivel {perfil.nivel} | {perfil.puntos_totales} pts | {badges_count} badges | Racha: {perfil.racha_dias_actual} días")

# Otorgar algunos badges manualmente para demostración
print("\n\n🏆 Otorgando badges especiales de demostración...")

# Badge "Primer Paso" al primer estudiante
if estudiantes_demo:
    estudiante1 = estudiantes_demo[0]
    badge_primer_paso = Badge.objects.filter(nombre__icontains="Primer Paso").first()
    if badge_primer_paso:
        BadgeEstudiante.objects.get_or_create(
            estudiante=estudiante1,
            badge=badge_primer_paso
        )
        print(f"   ✅ {badge_primer_paso.icono} {badge_primer_paso.nombre} → {estudiante1.nombre}")

# Badge de nivel al estudiante con más puntos
if estudiantes_demo:
    # Obtener el estudiante con más puntos
    perfiles = PerfilGamificacion.objects.filter(
        estudiante__in=estudiantes_demo
    ).order_by('-puntos_totales')
    
    if perfiles.exists():
        top_perfil = perfiles.first()
        badge_nivel = Badge.objects.filter(
            tipo='NIVEL',
            nivel_requerido=top_perfil.nivel
        ).first()
        
        if badge_nivel:
            BadgeEstudiante.objects.get_or_create(
                estudiante=top_perfil.estudiante,
                badge=badge_nivel
            )
            print(f"   ✅ {badge_nivel.icono} {badge_nivel.nombre} → {top_perfil.estudiante.nombre}")

# Mostrar estadísticas finales
print("\n" + "="*70)
print("📊 ESTADÍSTICAS FINALES\n")

# Top 5 por puntos
print("🏆 TOP 5 POR PUNTOS:")
top_puntos = PerfilGamificacion.objects.select_related('estudiante').order_by('-puntos_totales')[:5]
for idx, perfil in enumerate(top_puntos, 1):
    nivel_emoji = ['🌱', '🌿', '🍃', '🌾', '🌳', '🌲', '🎋', '🌺', '💎', '👑'][min(perfil.nivel-1, 9)]
    badges_count = BadgeEstudiante.objects.filter(estudiante=perfil.estudiante).count()
    print(f"   {idx}. {nivel_emoji} {perfil.estudiante.nombre}: {perfil.puntos_totales} pts (Nivel {perfil.nivel}) - {badges_count} badges")

# Top 5 por racha
print("\n🔥 TOP 5 POR RACHA:")
top_racha = PerfilGamificacion.objects.select_related('estudiante').order_by('-racha_dias_actual')[:5]
for idx, perfil in enumerate(top_racha, 1):
    if perfil.racha_dias_actual > 0:
        print(f"   {idx}. {perfil.estudiante.nombre}: {perfil.racha_dias_actual} días consecutivos")

# Estadísticas generales
total_perfiles = PerfilGamificacion.objects.count()
total_badges_otorgados = BadgeEstudiante.objects.count()
total_transacciones = TransaccionPuntos.objects.count()

print("\n📈 ESTADÍSTICAS GENERALES:")
print(f"   Total de estudiantes con perfil: {total_perfiles}")
print(f"   Total de badges otorgados: {total_badges_otorgados}")
print(f"   Total de transacciones de puntos: {total_transacciones}")

# Badges más populares
print("\n🎖️ BADGES MÁS OBTENIDOS:")
from django.db.models import Count
top_badges = Badge.objects.filter(
    estudiantes__isnull=False
).annotate(
    total_obtenidos=Count('estudiantes')
).order_by('-total_obtenidos')[:5]

for badge in top_badges:
    print(f"   {badge.icono} {badge.nombre}: {badge.total_obtenidos} estudiantes")

if not top_badges:
    print("   (Ningún badge ha sido otorgado aún)")

print("\n" + "="*70)
print("✅ DATOS DE EJEMPLO CREADOS EXITOSAMENTE")
print("="*70 + "\n")

print("📝 PARA VER LOS RESULTADOS:")
print("   1. Accede al admin de Django")
print("   2. Ve a: Gamificación → Ranking")
print("   3. También puedes ver: Gamificación → Perfiles de Gamificación")
print("   4. Y revisar: Gamificación → Badges Obtenidos")
print("\n")
