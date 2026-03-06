"""
Función para continuar con un curso específico seleccionado
"""

def continuar_curso_seleccionado(estudiante_id: int, indice_curso: int, mensaje_original: str):
    """
    Continúa con un curso específico seleccionado por el usuario.
    Busca cursos activos del cliente del estudiante y crea progreso si no existe.
    
    Args:
        estudiante_id: ID del estudiante
        indice_curso: Índice del curso (1, 2, 3, etc)
        mensaje_original: Mensaje original del usuario
    """
    from .models import Estudiante, Curso, ProgresoEstudiante, ModuloCompletado
    
    try:
        estudiante = Estudiante.objects.select_related('cliente').get(id=estudiante_id)
    except Estudiante.DoesNotExist:
        return "Error: No se encontró tu perfil de estudiante."
    
    # Obtener TODOS los cursos activos del cliente (mismo orden que enviar_lista_cursos)
    org = estudiante.cliente
    if org:
        cursos = Curso.objects.filter(cliente=org, activo=True).order_by('orden', 'nombre')
    else:
        cursos = Curso.objects.filter(activo=True).order_by('orden', 'nombre')
    
    cursos_list = list(cursos)
    
    # Validar índice
    if indice_curso < 1 or indice_curso > len(cursos_list):
        return f"Número inválido. Tienes {len(cursos_list)} cursos disponibles. Escribe un número del 1 al {len(cursos_list)}."
    
    # Obtener el curso seleccionado
    curso_seleccionado = cursos_list[indice_curso - 1]
    
    # Buscar o crear progreso para este curso
    progreso, creado = ProgresoEstudiante.objects.get_or_create(
        estudiante=estudiante,
        curso=curso_seleccionado,
        defaults={'completado': False}
    )
    
    if progreso.completado:
        return (
            f"✅ Ya completaste *{curso_seleccionado.nombre}*\n\n"
            f"🎓 Tu certificado está disponible.\n\n"
            f"Escribe *menú* para ver las opciones o selecciona otro curso."
        )
    
    # Obtener módulo actual
    modulo_actual = progreso.modulo_actual
    if not modulo_actual:
        modulo_actual = curso_seleccionado.modulos.order_by('numero').first()
        if not modulo_actual:
            return f"El curso {curso_seleccionado.nombre} no tiene módulos configurados."
        progreso.modulo_actual = modulo_actual
        progreso.save()
    
    mensaje_lower = mensaje_original.strip().lower()
    
    # Si el mensaje es SOLO un número, mostrar el módulo actual sin avanzar
    if mensaje_original.strip().isdigit():
        avance = progreso.porcentaje_avance()
        
        respuesta = f"""✅ {'Iniciando' if creado else 'Retomando'} *{curso_seleccionado.emoji or '📚'} {curso_seleccionado.nombre}*

📍 Módulo actual: {modulo_actual.numero}. {modulo_actual.titulo}
📈 Avance: {avance}%

{modulo_actual.contenido}


Cuando termines, escribe: *"listo"*"""
        
        # Agregar multimedia si hay
        from .response_templates import obtener_video_url
        video_url = obtener_video_url(modulo_actual)
        if video_url:
            respuesta += f"\n\n[MEDIA:{video_url}]"
        
        return respuesta
    
    # Si escribieron "listo" o "siguiente", avanzar al siguiente módulo
    palabras_completar = ['listo', 'siguiente', 'ok', 'dale', 'avanzar', 'sigue', 'continuar']
    
    if any(palabra in mensaje_lower for palabra in palabras_completar):
        # Marcar módulo actual como completado
        try:
            ModuloCompletado.objects.get_or_create(
                progreso=progreso,
                modulo=modulo_actual
            )
        except Exception as e:
            print(f"Error al completar módulo: {e}")
        
        # Buscar siguiente módulo
        siguiente_modulo = curso_seleccionado.modulos.filter(
            numero__gt=modulo_actual.numero
        ).order_by('numero').first()
        
        if siguiente_modulo:
            progreso.modulo_actual = siguiente_modulo
            progreso.save()
            
            from .response_templates import obtener_video_url
            video_url = obtener_video_url(siguiente_modulo)
            
            respuesta = f"""✅ ¡Completaste {modulo_actual.titulo}!

📚 Siguiente: Módulo {siguiente_modulo.numero} - {siguiente_modulo.titulo}

{siguiente_modulo.contenido}"""
            
            if video_url:
                respuesta += f"\n\n🎥 Video educativo:\n{video_url}"
            
            respuesta += "\n\n\nCuando termines, escribe: *\"listo\"*"
            
            return respuesta
        else:
            progreso.completado = True
            progreso.save()
            
            return f"""🎉 ¡FELICITACIONES!

Has completado el curso: {curso_seleccionado.nombre}

🏆 Tu certificado se está generando.

Escribe *menú* para ver las opciones."""
    
    return f"Escribe *listo* cuando termines el módulo o *menú* para volver."
