"""
Función para continuar con un curso específico seleccionado
"""

def continuar_curso_seleccionado(estudiante_id: int, indice_curso: int, mensaje_original: str):
    """
    Continúa con un curso específico seleccionado por el usuario
    
    Args:
        estudiante_id: ID del estudiante
        indice_curso: Índice del curso (1, 2, 3, etc)
        mensaje_original: Mensaje original del usuario
    """
    from .models import Estudiante, ProgresoEstudiante, ModuloCompletado
    
    estudiante = Estudiante.objects.get(id=estudiante_id)
    
    # Obtener cursos activos ordenados
    progresos_activos = ProgresoEstudiante.objects.filter(
        estudiante=estudiante,
        completado=False
    ).order_by('-fecha_inicio')
    
    # Validar índice
    if indice_curso < 1 or indice_curso > progresos_activos.count():
        return f"❌ Número inválido. Tienes {progresos_activos.count()} cursos activos. Escribe un número del 1 al {progresos_activos.count()}."
    
    # Obtener el progreso seleccionado
    progreso = list(progresos_activos)[indice_curso - 1]
    
    # Obtener módulo actual
    modulo_actual = progreso.modulo_actual
    if not modulo_actual:
        # Si no hay módulo actual, tomar el primero
        modulo_actual = progreso.curso.modulos.order_by('numero').first()
        progreso.modulo_actual = modulo_actual
        progreso.save()
    
    # Si escribieron "listo" o "siguiente", avanzar al siguiente módulo
    mensaje_lower = mensaje_original.lower()
    palabras_completar = ['listo', 'siguiente', 'ok', 'dale', 'avanzar', 'sigue']
    
    if any(palabra in mensaje_lower for palabra in palabras_completar):
        # Marcar módulo actual como completado
        ModuloCompletado.objects.get_or_create(
            progreso=progreso,
            modulo=modulo_actual
        )
        
        # Buscar siguiente módulo
        siguiente_modulo = progreso.curso.modulos.filter(
            numero__gt=modulo_actual.numero
        ).order_by('numero').first()
        
        if siguiente_modulo:
            # Avanzar al siguiente módulo
            progreso.modulo_actual = siguiente_modulo
            progreso.save()
            
            # Obtener video URL si existe
            from .response_templates import obtener_video_url
            video_url_absoluta = obtener_video_url(siguiente_modulo)
            
            respuesta = f"""✅ ¡Completaste {modulo_actual.titulo}!

📚 Siguiente: Módulo {siguiente_modulo.numero} - {siguiente_modulo.titulo}

{siguiente_modulo.contenido}"""
            
            if video_url_absoluta:
                respuesta += f"\n\n🎥 Video educativo:\n{video_url_absoluta}"
            
            respuesta += "\n\n---\nCuando termines, escribe: *\"listo\"*\nO pregúntame dudas sobre este tema."
            
            return respuesta
        else:
            # Completó el último módulo
            progreso.completado = True
            progreso.save()
            
            return f"""🎉 ¡FELICIDADES!

Has completado el curso: {progreso.curso.nombre}

🏆 Certificado disponible
📊 Escribe \"mi progreso\" para ver tus logros
📚 Escribe \"ver cursos\" para un nuevo curso"""
    
    # Mostrar módulo actual
    from .response_templates import obtener_video_url
    video_url_absoluta = obtener_video_url(modulo_actual)
    
    respuesta = f"""📖 Continuando: {progreso.curso.emoji} {progreso.curso.nombre}

Módulo {modulo_actual.numero}: {modulo_actual.titulo}

{modulo_actual.contenido}"""
    
    if video_url_absoluta:
        respuesta += f"\n\n🎥 Video educativo:\n{video_url_absoluta}"
    
    respuesta += "\n\n---\nCuando termines, escribe: *\"listo\"*\nO pregúntame dudas sobre este tema."
    
    return respuesta
