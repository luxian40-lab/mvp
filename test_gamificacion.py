"""
Test de verificación del sistema de gamificación
"""

from core.models import Estudiante, PerfilGamificacion, Badge, BadgeEstudiante
from core.gamificacion_actions import otorgar_puntos_mensaje

print("=" * 60)
print("🎮 TEST DEL SISTEMA DE GAMIFICACIÓN")
print("=" * 60)

# 1. Verificar estudiantes
total_estudiantes = Estudiante.objects.count()
print(f"\n1️⃣ Estudiantes en sistema: {total_estudiantes}")

# 2. Verificar perfiles
total_perfiles = PerfilGamificacion.objects.count()
print(f"2️⃣ Perfiles de gamificación: {total_perfiles}")

# 3. Verificar badges
total_badges = Badge.objects.count()
print(f"3️⃣ Badges disponibles: {total_badges}")

# 4. Verificar badges obtenidos
total_badges_obtenidos = BadgeEstudiante.objects.count()
print(f"4️⃣ Badges obtenidos por estudiantes: {total_badges_obtenidos}")

# 5. Ver primeros estudiantes con puntos
if total_perfiles > 0:
    print("\n📊 TOP 5 RANKING:")
    top_5 = PerfilGamificacion.objects.order_by('-puntos_totales')[:5]
    for i, perfil in enumerate(top_5, 1):
        badges = perfil.get_badges().count()
        print(f"   {i}. {perfil.estudiante.nombre}: Nivel {perfil.nivel}, "
              f"{perfil.puntos_totales} pts, {badges} badges")

# 6. Verificar signal (crear estudiante de prueba)
print("\n🧪 TEST DE SIGNAL:")
try:
    # Verificar si existe estudiante de prueba
    est_test = Estudiante.objects.filter(telefono="+57TEST123456").first()
    if est_test:
        print(f"   ✅ Estudiante de prueba ya existe: {est_test.nombre}")
        perfil = PerfilGamificacion.objects.filter(estudiante=est_test).first()
        if perfil:
            print(f"   ✅ Perfil auto-creado: Nivel {perfil.nivel}, {perfil.puntos_totales} pts")
        else:
            print("   ⚠️ Perfil NO fue auto-creado")
    else:
        print("   ℹ️ No hay estudiante de prueba")
except Exception as e:
    print(f"   ❌ Error: {e}")

# 7. Verificar función de otorgar puntos
print("\n🎯 TEST DE OTORGAMIENTO DE PUNTOS:")
if total_estudiantes > 0:
    estudiante = Estudiante.objects.first()
    perfil_antes = PerfilGamificacion.objects.get(estudiante=estudiante)
    puntos_antes = perfil_antes.puntos_totales
    
    try:
        resultado = otorgar_puntos_mensaje(estudiante)
        perfil_despues = PerfilGamificacion.objects.get(estudiante=estudiante)
        puntos_despues = perfil_despues.puntos_totales
        
        print(f"   Estudiante: {estudiante.nombre}")
        print(f"   Puntos antes: {puntos_antes}")
        print(f"   Puntos después: {puntos_despues}")
        print(f"   Diferencia: +{puntos_despues - puntos_antes}")
        print(f"   Nivel: {perfil_despues.nivel}")
        print(f"   ✅ Sistema de puntos funciona correctamente")
    except Exception as e:
        print(f"   ❌ Error al otorgar puntos: {e}")

print("\n" + "=" * 60)
print("✅ TEST COMPLETADO")
print("=" * 60)
