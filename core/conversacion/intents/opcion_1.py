"""Intent `opcion_1` de get_response_for_intent. Movido tal cual (fase G7)."""


def responder(intent, nombre_usuario, kwargs):
    from core.models import ProgresoEstudiante
    
    estudiante_id = kwargs.get('estudiante_id')
    if not estudiante_id:
        return "Error al identificar estudiante. ⚠️"
    
    from core.models import Estudiante
    from core.selector_curso import asegurar_inscripcion_catalogo_cliente
    estudiante = Estudiante.objects.get(id=estudiante_id)
    if getattr(estudiante, 'cliente_id', None):
        asegurar_inscripcion_catalogo_cliente(estudiante)

    # Obtener o crear perfil de gamificación
    from core.gamificacion import PerfilGamificacion, BadgeEstudiante
    perfil, _ = PerfilGamificacion.objects.get_or_create(estudiante=estudiante)
    
    progresos = ProgresoEstudiante.objects.filter(estudiante=estudiante)
    
    if not progresos.exists():
        return f"""📊 TU PROGRESO

👋 Hola {estudiante.nombre}, aún no tienes un curso asignado.

Tu organización te asignará un curso pronto. Si crees que es un error, escribe *ayuda* para contactar soporte."""
    
    respuesta = "📊 TU PROGRESO DE APRENDIZAJE\n\n"
    
    # Mostrar gamificación
    nivel_index = min(perfil.nivel - 1, 9)  # Proteger índice
    nivel_emoji = ["🌱", "🌿", "🍃", "🌾", "🌳", "🌲", "🎋", "🌺", "💎", "👑"][nivel_index]
    respuesta += f"🎮 {nivel_emoji} Nivel {perfil.nivel} | ⭐ {perfil.puntos_totales} puntos"
    
    respuesta += "\n"
    
    # Barra de progreso del nivel
    porcentaje_nivel = perfil.porcentaje_nivel()
    barras_llenas = int(porcentaje_nivel / 10)
    barra = "█" * barras_llenas + "░" * (10 - barras_llenas)
    respuesta += f"[{barra}] {porcentaje_nivel}% al nivel {perfil.nivel + 1}\n\n"
    
    # Badges obtenidos
    badges = BadgeEstudiante.objects.filter(estudiante=estudiante).select_related('badge').order_by('-fecha_obtenido')[:3]
    if badges.exists():
        respuesta += "🏆 Últimos logros: "
        respuesta += " ".join([f"{b.badge.icono}" for b in badges])
        respuesta += f" ({BadgeEstudiante.objects.filter(estudiante=estudiante).count()} total)\n\n"
    
    respuesta += "📚 TUS CURSOS:\n\n"
    
    for prog in progresos:
        porcentaje = prog.porcentaje_avance()
        estado = "✅ Completo" if prog.completado else f"⏳ En progreso"
        
        respuesta += f"{prog.curso.emoji} {prog.curso.nombre}\n"
        respuesta += f"   Avance: {porcentaje}% {estado}\n"
        
        if not prog.completado and prog.modulo_actual:
            respuesta += f"   📖 Módulo actual: {prog.modulo_actual.numero} - {prog.modulo_actual.titulo}\n"
        
        respuesta += "\n"
    
    if getattr(estudiante, 'cliente_id', None):
        respuesta += "Pulse continuar, para seguir aprendiendo.\n\n[SEND_BUTTON:continuemos]"
    else:
        respuesta += "Escribe *CONTINUAR* para seguir tu lección\n"
        respuesta += "O escribe *MENÚ* para volver al inicio"
    return respuesta
