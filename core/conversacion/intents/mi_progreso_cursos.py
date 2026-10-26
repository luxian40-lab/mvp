"""Intent `mi_progreso_cursos` de get_response_for_intent. Movido tal cual (fase G7)."""


def responder(intent, nombre_usuario, kwargs):
    from core.models import ProgresoEstudiante
    
    estudiante_id = kwargs.get('estudiante_id')
    if not estudiante_id:
        return "Error al identificar estudiante. ⚠️"
    
    from core.models import Estudiante
    estudiante = Estudiante.objects.get(id=estudiante_id)
    
    progresos = ProgresoEstudiante.objects.filter(estudiante=estudiante)
    
    if not progresos.exists():
        return """Tu Progreso

No tienes cursos todavía. 📚

Escribe "ver cursos" para empezar."""
    
    respuesta = "TU PROGRESO DE APRENDIZAJE\n\n"
    
    for prog in progresos:
        porcentaje = prog.porcentaje_avance()
        estado = "Completo" if prog.completado else f"⏳ {porcentaje}%"
        
        respuesta += f"{prog.curso.emoji} {prog.curso.nombre}\n"
        respuesta += f"   {estado}\n"
        
        if not prog.completado and prog.modulo_actual:
            respuesta += f"   📖 Módulo actual: {prog.modulo_actual.numero}\n"
        
        respuesta += "\n"
    
    respuesta += "Escribe \"continuar\" para seguir aprendiendo."
    return respuesta
