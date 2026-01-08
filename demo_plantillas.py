"""
Script de Demostración - Sistema de Plantillas y Reportes
Crea datos de ejemplo para probar todas las funcionalidades nuevas
"""

import os
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()

from core.models import Plantilla
from datetime import datetime

def crear_plantillas_ejemplo():
    """Crea plantillas de ejemplo de cada categoría"""
    
    plantillas = [
        {
            'nombre_interno': 'Bienvenida Curso Aguacate',
            'categoria': 'bienvenida',
            'cuerpo_mensaje': '''¡Hola {nombre}! 👋

Bienvenido al curso de Cultivo de Aguacate Hass 🥑

Aprenderás todo lo necesario para tener una cosecha exitosa.

Escribe "empezar" cuando estés listo para comenzar.''',
            'activa': True
        },
        {
            'nombre_interno': 'Motivación Estudiante Inactivo',
            'categoria': 'motivacional',
            'cuerpo_mensaje': '''Hola {nombre} 💪

Notamos que llevas algunos días sin avanzar en el curso {curso}.

¡No te rindas! Cada módulo completado te acerca más a ser un experto.

Escribe "continuar" para retomar donde lo dejaste.

¿Tienes alguna duda? Estamos aquí para ayudarte. 🌱''',
            'activa': True
        },
        {
            'nombre_interno': 'Recordatorio Examen Disponible',
            'categoria': 'recordatorio',
            'cuerpo_mensaje': '''Hola {nombre} ⏰

Tienes un examen disponible para el curso {curso}.

Has completado todos los módulos, ¡es hora de demostrar lo que aprendiste!

Escribe "examen" para comenzar.

¡Mucho éxito! 🎯''',
            'activa': True
        },
        {
            'nombre_interno': 'Felicitación Módulo Completado',
            'categoria': 'motivacional',
            'cuerpo_mensaje': '''¡Excelente trabajo {nombre}! 🎉

Has completado exitosamente un módulo más del curso {curso}.

Tu dedicación y esfuerzo están dando frutos. 🌟

Escribe "siguiente" para continuar con el siguiente módulo.''',
            'activa': True
        },
        {
            'nombre_interno': 'Información Técnica Riego',
            'categoria': 'educativo',
            'cuerpo_mensaje': '''Hola {nombre} 📚

📖 Información sobre Riego del Aguacate:

🔹 Frecuencia: 2-3 veces por semana
🔹 Cantidad: 20-30 litros por árbol
🔹 Mejor horario: Temprano en la mañana
🔹 Evitar: Encharcamientos

¿Tienes dudas? Escribe tu pregunta.''',
            'activa': True
        },
        {
            'nombre_interno': 'Promoción Nuevo Curso Café',
            'categoria': 'promocional',
            'cuerpo_mensaje': '''¡Nuevo Curso Disponible! ☕

{nombre}, nos complace anunciar nuestro curso de Café Arábigo.

🌱 5 módulos completos
📝 Examen de certificación
👨‍🌾 Técnicas profesionales

Escribe "curso cafe" para más información.''',
            'activa': True
        },
        {
            'nombre_interno': 'Información Contacto Soporte',
            'categoria': 'informativo',
            'cuerpo_mensaje': '''Hola {nombre} ℹ️

Si necesitas ayuda, nuestro equipo está disponible:

📱 WhatsApp: {telefono}
⏰ Horario: Lunes a Viernes, 8am-6pm
📧 Email: soporte@eki.com

También puedes escribir "ayuda" en cualquier momento.''',
            'activa': True
        },
        {
            'nombre_interno': 'Plantilla Borrador Pruebas',
            'categoria': 'otro',
            'cuerpo_mensaje': '''Esta es una plantilla de prueba.

No está activa, por lo que no aparecerá en las opciones de envío.

Úsala para experimentar con el sistema.''',
            'activa': False  # Esta está INACTIVA para demostrar el filtro
        }
    ]
    
    print("🚀 Creando plantillas de ejemplo...\n")
    
    creadas = 0
    actualizadas = 0
    
    for p_data in plantillas:
        plantilla, created = Plantilla.objects.get_or_create(
            nombre_interno=p_data['nombre_interno'],
            defaults=p_data
        )
        
        if created:
            creadas += 1
            status = "✅ CREADA"
            emoji = dict(Plantilla.CATEGORIA_CHOICES)[p_data['categoria']]
        else:
            # Actualizar si ya existe
            for key, value in p_data.items():
                setattr(plantilla, key, value)
            plantilla.save()
            actualizadas += 1
            status = "🔄 ACTUALIZADA"
            emoji = plantilla.get_categoria_display()
        
        print(f"{status} - {emoji} - {plantilla.nombre_interno}")
    
    print(f"\n📊 Resumen:")
    print(f"   ✨ Plantillas creadas: {creadas}")
    print(f"   🔄 Plantillas actualizadas: {actualizadas}")
    print(f"   📝 Total en sistema: {Plantilla.objects.count()}")
    print(f"   ✅ Activas: {Plantilla.objects.filter(activa=True).count()}")
    print(f"   ❌ Inactivas: {Plantilla.objects.filter(activa=False).count()}")
    
    print("\n" + "="*60)
    print("🎯 PRUEBAS RECOMENDADAS:")
    print("="*60)
    print("\n1. 📝 CREAR PLANTILLA:")
    print("   → http://localhost:8000/admin/core/plantilla/add/")
    print("   → Llena el formulario")
    print("   → Observa la vista previa personalizada")
    print("   → Guarda y revisa las estadísticas")
    
    print("\n2. 📋 VER TODAS LAS PLANTILLAS:")
    print("   → http://localhost:8000/admin/core/plantilla/")
    print("   → Observa las categorías con emojis")
    print("   → Prueba los filtros (categoría, activa)")
    print("   → Usa la búsqueda")
    
    print("\n3. 📤 ENVIAR PLANTILLA:")
    print("   → Selecciona una plantilla")
    print("   → Acción: 'Enviar plantilla a estudiantes'")
    print("   → Selecciona estudiantes destinatarios")
    print("   → Aplica")
    
    print("\n4. 📄 DUPLICAR PLANTILLA:")
    print("   → Selecciona una plantilla")
    print("   → Acción: 'Duplicar plantilla(s)'")
    print("   → Se creará una copia para modificar")
    
    print("\n5. 📊 EXPORTAR REPORTES:")
    print("   → Estudiantes: http://localhost:8000/admin/core/estudiante/")
    print("     - Selecciona estudiantes")
    print("     - Acción: 'Exportar estudiantes a Excel'")
    print("")
    print("   → Conversaciones: http://localhost:8000/admin/core/whatsapplog/")
    print("     - Selecciona conversaciones")
    print("     - Acción: 'Exportar conversaciones a Excel'")
    print("")
    print("   → Progreso: http://localhost:8000/admin/core/progresoestudiante/")
    print("     - Selecciona registros de progreso")
    print("     - Acción: 'Exportar progreso a Excel'")
    
    print("\n6. ✏️ EDITAR PLANTILLA:")
    print("   → Click en cualquier plantilla")
    print("   → Modifica el mensaje")
    print("   → Observa cómo cambia la vista previa")
    print("   → Guarda y verifica 'Fecha modificación'")
    
    print("\n7. 🔍 BUSCAR PLANTILLA:")
    print("   → En el listado de plantillas")
    print("   → Usa la caja de búsqueda")
    print("   → Busca por nombre o palabras en el mensaje")
    
    print("\n8. 🎯 FILTRAR PLANTILLAS:")
    print("   → Usa los filtros de la derecha:")
    print("     • Por categoría (Educativo, Motivacional, etc.)")
    print("     • Por estado (Activa/Inactiva)")
    print("     • Por fecha de creación")
    
    print("\n" + "="*60)
    print("📚 DOCUMENTACIÓN:")
    print("="*60)
    print("\n1. Guía Completa:")
    print("   → GUIA_PLANTILLAS_Y_REPORTES.md")
    print("   → 10 secciones detalladas")
    print("   → Casos de uso y mejores prácticas")
    
    print("\n2. Guía Rápida:")
    print("   → GUIA_RAPIDA_ADMIN.md")
    print("   → Referencia visual de 1 página")
    print("   → Atajos y checklist diario")
    
    print("\n3. Resumen Técnico:")
    print("   → RESUMEN_MEJORAS_PLANTILLAS_REPORTES.md")
    print("   → Detalles de implementación")
    print("   → Métricas y beneficios")
    
    print("\n" + "="*60)
    print("✨ ¡SISTEMA LISTO PARA USAR!")
    print("="*60)
    print(f"\n🕐 Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("🌐 URL Admin: http://localhost:8000/admin/")
    print("👤 Usuario: admin (configurar si aún no existe)")
    print("\n")

if __name__ == "__main__":
    try:
        crear_plantillas_ejemplo()
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        print("\n⚠️ Asegúrate de que:")
        print("   1. El servidor Django NO esté corriendo")
        print("   2. Las migraciones estén aplicadas (python manage.py migrate)")
        print("   3. Estés en el directorio correcto")
