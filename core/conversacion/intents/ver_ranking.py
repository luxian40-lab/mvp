"""Intent `ver_ranking` de get_response_for_intent. Movido tal cual (fase G7)."""


def responder(intent, nombre_usuario, kwargs):
    from core.gamificacion import PerfilGamificacion, BadgeEstudiante
    from django.db.models import Count
    
    # Top 5 por puntos
    top_puntos = PerfilGamificacion.objects.select_related('estudiante').order_by('-puntos_totales')[:5]
    
    # Estadísticas del estudiante actual
    estudiante_id = kwargs.get('estudiante_id')
    mi_perfil = None
    mi_posicion = None
    
    if estudiante_id:
        from core.models import Estudiante
        estudiante = Estudiante.objects.get(id=estudiante_id)
        mi_perfil, _ = PerfilGamificacion.objects.get_or_create(estudiante=estudiante)
        
        # Calcular posición
        mejores = PerfilGamificacion.objects.filter(puntos_totales__gt=mi_perfil.puntos_totales).count()
        mi_posicion = mejores + 1
    
    respuesta = "🏆 RANKING DE ESTUDIANTES eki\n\n"
    respuesta += "📊 TOP 5 POR PUNTOS:\n"
    
    for idx, perfil in enumerate(top_puntos, 1):
        nivel_index = min(perfil.nivel - 1, 9)  # Proteger índice
        nivel_emoji = ["🌱", "🌿", "🍃", "🌾", "🌳", "🌲", "🎋", "🌺", "💎", "👑"][nivel_index]
        medalla = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][idx - 1]
        respuesta += f"{medalla} {perfil.estudiante.nombre}\n"
        respuesta += f"   {nivel_emoji} Nivel {perfil.nivel} | ⭐ {perfil.puntos_totales} pts\n"
    
    if mi_perfil:
        respuesta += f"📍 TU POSICIÓN: #{mi_posicion}\n"
        respuesta += f"⭐ {mi_perfil.puntos_totales} puntos | Nivel {mi_perfil.nivel}\n"
    
    respuesta += "\n✨ Completa cursos y módulos para subir en el ranking!"
    
    return respuesta
