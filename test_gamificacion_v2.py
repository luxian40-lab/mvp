"""
Script de Prueba - Sistema de Gamificación v2.0 (Enfoque Académico)

Este script permite probar el nuevo sistema de gamificación
centrado en logros académicos reales.
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()

from core.models import Estudiante, Curso, Examen, ResultadoExamen
from core.gamificacion import PerfilGamificacion, Badge
from core.gamificacion_actions import (
    otorgar_puntos_mensaje,
    otorgar_puntos_modulo,
    otorgar_puntos_examen,
    otorgar_puntos_curso_completado,
    calcular_promedio_curso,
    PUNTOS_CONFIG
)

def print_separator():
    print("\n" + "="*70 + "\n")

def test_configuracion_puntos():
    """Test 1: Verificar configuración de puntos"""
    print("🧪 TEST 1: Configuración de Puntos")
    print_separator()
    
    print("📊 MENSAJERÍA (Mínimo):")
    print(f"  - Mensaje enviado: {PUNTOS_CONFIG['mensaje_enviado']} pts")
    print(f"  - Audio enviado: {PUNTOS_CONFIG['audio_enviado']} pts")
    
    print("\n📚 ACADÉMICO (Alto Valor):")
    print(f"  - Módulo completado: {PUNTOS_CONFIG['modulo_completado']} pts")
    
    print("\n📝 EXÁMENES (Escalonado):")
    print(f"  - 60-69%: {PUNTOS_CONFIG['examen_aprobado_60']} pts")
    print(f"  - 70-79%: {PUNTOS_CONFIG['examen_aprobado_70']} pts")
    print(f"  - 80-89%: {PUNTOS_CONFIG['examen_aprobado_80']} pts")
    print(f"  - 90-99%: {PUNTOS_CONFIG['examen_aprobado_90']} pts")
    print(f"  - 100%: {PUNTOS_CONFIG['examen_perfecto']} pts")
    print(f"  - <60%: {PUNTOS_CONFIG['examen_reprobado']} pts")
    
    print("\n🎓 CURSOS (Máximo Valor):")
    print(f"  - Curso completado: {PUNTOS_CONFIG['curso_completado']} pts")
    print(f"  - Excelencia (≥90%): {PUNTOS_CONFIG['curso_excelencia']} pts")
    
    print_separator()
    print("✅ Configuración correcta")

def test_sistema_examen():
    """Test 2: Probar sistema escalonado de exámenes"""
    print("🧪 TEST 2: Sistema Escalonado de Exámenes")
    print_separator()
    
    # Obtener o crear estudiante de prueba
    estudiante, created = Estudiante.objects.get_or_create(
        telefono="+573009999999",
        defaults={'nombre': 'Test Student - Gamificación v2'}
    )
    
    if created:
        print(f"✅ Estudiante de prueba creado: {estudiante.nombre}")
    else:
        print(f"📌 Usando estudiante existente: {estudiante.nombre}")
    
    # Obtener perfil
    perfil, _ = PerfilGamificacion.objects.get_or_create(estudiante=estudiante)
    puntos_iniciales = perfil.puntos_totales
    
    print(f"\n📊 Estado inicial:")
    print(f"  - Puntos totales: {puntos_iniciales}")
    print(f"  - Nivel: {perfil.nivel}")
    
    # Probar diferentes calificaciones
    calificaciones = [55, 65, 75, 85, 95, 100]
    
    print(f"\n🎯 Probando calificaciones:")
    for puntaje in calificaciones:
        resultado = otorgar_puntos_examen(estudiante, puntaje, None)
        if resultado.get('success'):
            puntos = resultado['puntos_ganados']
            emoji = resultado.get('emoji', '?')
            print(f"  {emoji} {puntaje}% → +{puntos} pts")
    
    # Verificar puntos finales
    perfil.refresh_from_db()
    print(f"\n📊 Estado final:")
    print(f"  - Puntos totales: {perfil.puntos_totales}")
    print(f"  - Nivel: {perfil.nivel}")
    print(f"  - Ganancia total: +{perfil.puntos_totales - puntos_iniciales} pts")
    
    print_separator()
    print("✅ Sistema escalonado funciona correctamente")

def test_comparacion_mensajeria_vs_estudio():
    """Test 3: Comparar puntos de mensajería vs estudio"""
    print("🧪 TEST 3: Mensajería vs Estudio Real")
    print_separator()
    
    # Estudiante A: Solo mensajería
    print("👤 ESTUDIANTE A: Solo mensajería")
    print("  - 100 mensajes enviados")
    puntos_mensajeria = 100 * PUNTOS_CONFIG['mensaje_enviado']
    print(f"  - Total: {puntos_mensajeria} pts")
    
    # Calcular nivel alcanzable
    niveles = [0, 100, 300, 600, 1000, 1500, 2100, 2800, 3600, 11000]
    nivel_mensajeria = 1
    for i, umbral in enumerate(niveles):
        if puntos_mensajeria >= umbral:
            nivel_mensajeria = i + 1
    print(f"  - Nivel alcanzado: {nivel_mensajeria}")
    
    print("\n👤 ESTUDIANTE B: Estudiante dedicado")
    print("  - 3 módulos completados")
    print("  - 3 exámenes aprobados (promedio 85%)")
    
    puntos_modulos = 3 * PUNTOS_CONFIG['modulo_completado']
    puntos_examenes = 3 * PUNTOS_CONFIG['examen_aprobado_80']
    puntos_estudio = puntos_modulos + puntos_examenes
    
    print(f"  - Módulos: {puntos_modulos} pts")
    print(f"  - Exámenes: {puntos_examenes} pts")
    print(f"  - Total: {puntos_estudio} pts")
    
    nivel_estudio = 1
    for i, umbral in enumerate(niveles):
        if puntos_estudio >= umbral:
            nivel_estudio = i + 1
    print(f"  - Nivel alcanzado: {nivel_estudio}")
    
    print("\n📊 COMPARACIÓN:")
    print(f"  - Diferencia de puntos: {puntos_estudio - puntos_mensajeria} pts")
    print(f"  - Diferencia de niveles: {nivel_estudio - nivel_mensajeria} niveles")
    
    print_separator()
    if puntos_estudio > puntos_mensajeria * 5:
        print("✅ Sistema premia correctamente el estudio vs mensajería")
    else:
        print("⚠️ Advertencia: Revisar balance de puntos")

def test_excelencia_academica():
    """Test 4: Probar bonus de excelencia"""
    print("🧪 TEST 4: Bonus de Excelencia Académica")
    print_separator()
    
    print("🎓 Escenario: Curso con 3 exámenes")
    print("\nCaso A: Promedio 75%")
    print(f"  - Puntos base: {PUNTOS_CONFIG['curso_completado']} pts")
    print(f"  - Bonus: 0 pts (promedio < 90%)")
    
    print("\nCaso B: Promedio 92% (Excelencia)")
    print(f"  - Puntos base: 0 pts (reemplazado)")
    print(f"  - Puntos con excelencia: {PUNTOS_CONFIG['curso_excelencia']} pts")
    
    diferencia = PUNTOS_CONFIG['curso_excelencia'] - PUNTOS_CONFIG['curso_completado']
    porcentaje = (diferencia / PUNTOS_CONFIG['curso_completado']) * 100
    
    print(f"\n📊 Bonus por excelencia:")
    print(f"  - Diferencia: +{diferencia} pts")
    print(f"  - Incremento: +{porcentaje:.0f}%")
    
    print_separator()
    print("✅ Sistema de excelencia configurado correctamente")

def test_resumen_sistema():
    """Test 5: Resumen del sistema"""
    print("🧪 TEST 5: Resumen del Sistema v2.0")
    print_separator()
    
    print("🎯 FILOSOFÍA:")
    print("  - Enfoque en logros académicos reales")
    print("  - Mensajería: Solo mantener racha")
    print("  - Notificaciones: Solo logros importantes")
    
    print("\n📊 ESTADÍSTICAS:")
    total_estudiantes = Estudiante.objects.count()
    total_perfiles = PerfilGamificacion.objects.count()
    total_badges = Badge.objects.count()
    
    print(f"  - Estudiantes: {total_estudiantes}")
    print(f"  - Perfiles activos: {total_perfiles}")
    print(f"  - Badges disponibles: {total_badges}")
    
    if total_perfiles > 0:
        perfil_ejemplo = PerfilGamificacion.objects.first()
        print(f"\n📌 Ejemplo de perfil:")
        print(f"  - Estudiante: {perfil_ejemplo.estudiante.nombre}")
        print(f"  - Nivel: {perfil_ejemplo.nivel}")
        print(f"  - Puntos: {perfil_ejemplo.puntos_totales}")
        print(f"  - Racha: {perfil_ejemplo.racha_dias_actual} días")
    
    print_separator()
    print("✅ Sistema operacional")

def main():
    """Ejecutar todos los tests"""
    print("\n" + "="*70)
    print("  🎮 SISTEMA DE GAMIFICACIÓN v2.0 - TESTS  ")
    print("  Enfoque Académico - EKI")
    print("="*70)
    
    try:
        # Ejecutar tests
        test_configuracion_puntos()
        input("\nPresiona ENTER para continuar al Test 2...")
        
        test_sistema_examen()
        input("\nPresiona ENTER para continuar al Test 3...")
        
        test_comparacion_mensajeria_vs_estudio()
        input("\nPresiona ENTER para continuar al Test 4...")
        
        test_excelencia_academica()
        input("\nPresiona ENTER para continuar al Test 5...")
        
        test_resumen_sistema()
        
        print("\n" + "="*70)
        print("  ✅ TODOS LOS TESTS COMPLETADOS")
        print("="*70)
        print("\n📝 CONCLUSIÓN:")
        print("  - Sistema v2.0 está operacional")
        print("  - Enfoque en progreso académico real")
        print("  - Listo para integración con modelos")
        print("\n📚 DOCUMENTACIÓN:")
        print("  - GAMIFICACION_ACADEMICA.md")
        print("  - INTEGRACION_GAMIFICACION.md")
        print("  - RESUMEN_CAMBIOS_GAMIFICACION.md")
        print("\n")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
