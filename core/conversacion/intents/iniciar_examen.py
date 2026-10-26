"""Intent `iniciar_examen` de get_response_for_intent. Movido tal cual (fase G7)."""


def responder(intent, nombre_usuario, kwargs):
    from core.models import ProgresoEstudiante, Examen
    
    estudiante_id = kwargs.get('estudiante_id')
    if not estudiante_id:
        return "Error al identificar estudiante. ⚠️"
    
    from core.models import Estudiante
    estudiante = Estudiante.objects.get(id=estudiante_id)
    
    # Buscar progreso activo
    progreso = ProgresoEstudiante.objects.filter(
        estudiante=estudiante,
        completado=False
    ).first()
    
    if not progreso:
        return """Aún no tienes un curso asignado para tomar examen. 📚

Tu organización te asignará un curso pronto. Si crees que es un error, escribe *ayuda* para contactar soporte."""
    
    # Verificar que haya completado todos los módulos
    from core.modulo_publicacion import modulos_publicados_wa_qs, total_modulos_publicados_wa

    total_modulos = total_modulos_publicados_wa(progreso.curso)
    pub_ids = set(modulos_publicados_wa_qs(progreso.curso).values_list('id', flat=True))
    modulos_completados = progreso.modulos_completados.filter(modulo_id__in=pub_ids).count()
    
    if modulos_completados < total_modulos:
        return f"""⚠️ Aún no puedes tomar el examen.

Debes completar los {total_modulos} módulos primero.
Has completado: {modulos_completados}/{total_modulos}

Escribe "continuar" para seguir con tus lecciones."""
    
    # Obtener examen
    try:
        examen = progreso.curso.examen
    except:
        return "Este curso no tiene examen configurado todavía. ⚠️"
    
    # Iniciar examen (guardar en contexto)
    primera_pregunta = examen.preguntas.order_by('numero').first()
    
    respuesta = f"""{progreso.curso.emoji} EXAMEN FINAL

{examen.instrucciones}

📝 Total de preguntas: {examen.preguntas.count()}
Puntaje mínimo: {examen.puntaje_minimo}%

---

Pregunta 1:
{primera_pregunta.pregunta}

Responde con tu mejor explicación.
   (El tutor evaluará tu respuesta)"""
    
    return respuesta
