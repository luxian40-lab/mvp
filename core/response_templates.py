"""
Plantillas de respuesta para cada intent - Agro Colombiano.
Permite personalizar respuestas sin cambiar la lógica del webhook.
"""
from django.conf import settings
from django.utils import timezone


def obtener_video_url(leccion_o_modulo):
    """
    Genera URL pública del video si existe.
    
    Args:
        leccion_o_modulo: Instancia de Leccion o Modulo con video_archivo o video_url
        
    Returns:
        str: URL completa del video o None
    """
    # Prioridad 1: Archivo subido
    if hasattr(leccion_o_modulo, 'video_archivo') and leccion_o_modulo.video_archivo:
        # URL relativa del archivo
        ruta_relativa = f"{settings.MEDIA_URL}{leccion_o_modulo.video_archivo.name}"
        
        # En desarrollo: localhost, en producción: dominio real
        if settings.DEBUG:
            base_url = 'http://localhost:8000'
        else:
            # Obtener dominio de ALLOWED_HOSTS
            base_url = f"https://{settings.ALLOWED_HOSTS[0]}" if settings.ALLOWED_HOSTS else ''
        
        return f"{base_url}{ruta_relativa}"
    
    # Prioridad 2: URL externa (YouTube/Vimeo)
    if hasattr(leccion_o_modulo, 'video_url') and leccion_o_modulo.video_url:
        return leccion_o_modulo.video_url
    
    return None


def get_response_for_intent(intent: str, nombre_usuario: str = "Estudiante", **kwargs) -> str:
    """
    Retorna una respuesta templada según el intent.
    
    Args:
        intent: categoría detectada (saludo, progreso, tareas, ayuda, etc.)
        nombre_usuario: nombre del estudiante (para personalizar)
        kwargs: datos adicionales (progreso, siguiente_tarea, etc.)
    
    Returns:
        mensaje: respuesta en formato texto
    """
    
    # Saludos
    if intent == 'saludo':
        return f"""Hola {nombre_usuario} 👋

Soy tu tutor agrícola de Eki.

Estoy aquí para enseñarte con cursos de agricultura colombiana.

¿Qué quieres hacer?

1️⃣ Ver mi progreso
2️⃣ Ver cursos disponibles
3️⃣ Continuar con mi curso

Escribe el número."""
    
    # Cambiar nombre
    if intent == 'cambiar_nombre':
        return """Para cambiar tu nombre, escribe:

Mi nombre es [Tu Nombre]

Ejemplo:
- Mi nombre es Juan Pérez
- Mi nombre es María González"""
    
    # Confirmar cambio de nombre
    if intent == 'confirmar_cambio_nombre':
        nuevo_nombre = kwargs.get('nuevo_nombre', 'Usuario')
        return f"""✅ Listo, ahora te llamaré {nuevo_nombre}.

¿Quieres continuar?
Escribe "continuar", "ver cursos" o "mi progreso"."""
    
    # Opción 1: Ver mi progreso en cursos
    if intent == 'opcion_1':
        # Delegar a la función de mi_progreso_cursos que ya maneja esto
        from .models import ProgresoEstudiante
        
        estudiante_id = kwargs.get('estudiante_id')
        if not estudiante_id:
            return "Error al identificar estudiante. ⚠️"
        
        from .models import Estudiante
        estudiante = Estudiante.objects.get(id=estudiante_id)
        
        # Obtener o crear perfil de gamificación
        from .gamificacion import PerfilGamificacion, BadgeEstudiante
        perfil, _ = PerfilGamificacion.objects.get_or_create(estudiante=estudiante)
        
        progresos = ProgresoEstudiante.objects.filter(estudiante=estudiante)
        
        if not progresos.exists():
            return """📚 Tu Progreso de Aprendizaje

Aún no tienes cursos.

Escribe "ver cursos" para empezar tu educación agrícola.

Cursos disponibles:
🥑 Aguacate Hass
☕ Café Arábigo"""
        
        respuesta = "📊 TU PROGRESO DE APRENDIZAJE\n\n"
        
        # Mostrar gamificación
        nivel_emoji = ["🌱", "🌿", "🍃", "🌾", "🌳", "🌲", "🎋", "🌺", "💎", "👑"][perfil.nivel - 1]
        respuesta += f"🎮 {nivel_emoji} Nivel {perfil.nivel} | ⭐ {perfil.puntos_totales} puntos"
        
        # Mostrar racha si está activa
        if perfil.racha_dias_actual > 0:
            fuego = "🔥" * min(perfil.racha_dias_actual, 5)
            respuesta += f" | {fuego} {perfil.racha_dias_actual} días seguidos"
        
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
        
        respuesta += "Escribe \"continuar\" para seguir con tu lección."
        return respuesta
    
    # Opción 2: Ver cursos disponibles
    if intent == 'opcion_2':
        from .models import Curso
        cursos_activos = Curso.objects.filter(activo=True).order_by('orden')
        
        if not cursos_activos.exists():
            return "No hay cursos disponibles en este momento. ⚠️"
        
        respuesta = "📚 CURSOS DISPONIBLES EN EKI\n\n"
        respuesta += "Selecciona el número del curso:\n\n"
        
        for idx, curso in enumerate(cursos_activos, 1):
            respuesta += f"{idx}. {curso.emoji} {curso.nombre}\n"
            respuesta += f"   📅 Duración: {curso.duracion_semanas} semanas\n"
            respuesta += f"   📖 Módulos: {curso.modulos.count()}\n"
            respuesta += f"   {curso.descripcion[:60]}...\n\n"
        
        respuesta += "✏️ Para inscribirte, escribe:\n"
        respuesta += "\"tomar 1\", \"tomar 2\", \"tomar 3\", etc."
        return respuesta
    
    # Opción 3: Continuar con curso actual
    if intent == 'opcion_3':
        from .models import ProgresoEstudiante
        
        estudiante_id = kwargs.get('estudiante_id')
        if not estudiante_id:
            return "Error al identificar estudiante. ⚠️"
        
        from .models import Estudiante
        estudiante = Estudiante.objects.get(id=estudiante_id)
        
        # Buscar progreso activo (el más reciente por fecha_inicio)
        progreso = ProgresoEstudiante.objects.filter(
            estudiante=estudiante,
            completado=False
        ).order_by('-fecha_inicio').first()
        
        if not progreso:
            return """❌ No tienes cursos activos.

Escribe "ver cursos" para inscribirte en uno.

Cursos disponibles:
🥑 Aguacate Hass (5 módulos)
☕ Café Arábigo (5 módulos)"""
        
        # Obtener módulo actual
        modulo = progreso.modulo_actual
        if not modulo:
            modulo = progreso.curso.modulos.order_by('numero').first()
            progreso.modulo_actual = modulo
            progreso.save()
        
        # Mostrar contenido del módulo
        respuesta = f"📖 {progreso.curso.emoji} {progreso.curso.nombre}\n\n"
        respuesta += f"Módulo {modulo.numero}: {modulo.titulo}\n\n"
        respuesta += f"{modulo.contenido}\n\n"
        
        # Agregar video si existe
        video_url = obtener_video_url(modulo)
        if video_url:
            respuesta += "🎥 Video educativo:\n"
            respuesta += f"{video_url}\n\n"
        
        respuesta += "---\n\n"
        respuesta += f"Cuando termines esta lección, escribe:\n"
        respuesta += f"   \"completar módulo {modulo.numero}\"\n\n"
        respuesta += "O pregúntame dudas sobre este tema."
        
        return respuesta
    
    # Progreso (sin pasar por menú) - Redirigir a opcion_1
    if intent == 'progreso':
        return get_response_for_intent('opcion_1', nombre_usuario, kwargs)
    
    # Tareas/Cursos (sin pasar por menú) - Redirigir a ver_cursos
    if intent == 'tareas':
        return get_response_for_intent('ver_cursos', nombre_usuario, **kwargs)
    
    # Ver ranking de gamificación
    if intent == 'ver_ranking':
        from .gamificacion import PerfilGamificacion, BadgeEstudiante
        from django.db.models import Count
        
        # Top 5 por puntos
        top_puntos = PerfilGamificacion.objects.select_related('estudiante').order_by('-puntos_totales')[:5]
        
        # Top 5 por racha actual
        top_racha = PerfilGamificacion.objects.select_related('estudiante').filter(racha_dias_actual__gt=0).order_by('-racha_dias_actual')[:5]
        
        # Estadísticas del estudiante actual
        estudiante_id = kwargs.get('estudiante_id')
        mi_perfil = None
        mi_posicion = None
        
        if estudiante_id:
            from .models import Estudiante
            estudiante = Estudiante.objects.get(id=estudiante_id)
            mi_perfil, _ = PerfilGamificacion.objects.get_or_create(estudiante=estudiante)
            
            # Calcular posición
            mejores = PerfilGamificacion.objects.filter(puntos_totales__gt=mi_perfil.puntos_totales).count()
            mi_posicion = mejores + 1
        
        respuesta = "🏆 RANKING DE ESTUDIANTES EKI\n\n"
        respuesta += "📊 TOP 5 POR PUNTOS:\n"
        
        for idx, perfil in enumerate(top_puntos, 1):
            nivel_emoji = ["🌱", "🌿", "🍃", "🌾", "🌳", "🌲", "🎋", "🌺", "💎", "👑"][perfil.nivel - 1]
            medalla = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][idx - 1]
            respuesta += f"{medalla} {perfil.estudiante.nombre}\n"
            respuesta += f"   {nivel_emoji} Nivel {perfil.nivel} | ⭐ {perfil.puntos_totales} pts\n"
        
        if top_racha.exists():
            respuesta += "\n🔥 TOP 5 POR RACHA:\n"
            for idx, perfil in enumerate(top_racha, 1):
                fuego = "🔥" * min(perfil.racha_dias_actual, 3)
                respuesta += f"{idx}. {perfil.estudiante.nombre}\n"
                respuesta += f"   {fuego} {perfil.racha_dias_actual} días seguidos\n"
        
        if mi_perfil:
            respuesta += f"\n━━━━━━━━━━━━━━━━━━━━\n"
            respuesta += f"📍 TU POSICIÓN: #{mi_posicion}\n"
            respuesta += f"⭐ {mi_perfil.puntos_totales} puntos | Nivel {mi_perfil.nivel}\n"
            
            if mi_perfil.racha_dias_actual > 0:
                fuego = "🔥" * min(mi_perfil.racha_dias_actual, 3)
                respuesta += f"{fuego} {mi_perfil.racha_dias_actual} días de racha\n"
        
        respuesta += "\n✨ Completa cursos y módulos para subir en el ranking!"
        
        return respuesta
    
    # Ayuda (sin pasar por menú)
    if intent == 'ayuda':
        return """AYUDA - SISTEMA DE CURSOS EKI

COMANDOS PRINCIPALES:

- Ver cursos: "ver cursos"
- Inscribirme: "inscribir 1" o "tomar 2"
- Continuar curso: "continuar"
- Mi progreso: "mi progreso"
- Ranking: "ranking" o "top"
- Terminar lección: "listo" o "siguiente"
- Cambiar nombre: "cambiar nombre"
- Volver al menú: "menú" o "inicio"

GAMIFICACIÓN:
🎮 Ganas puntos al completar módulos
🏆 Desbloqueas badges por logros
📈 Subes de nivel con experiencia
🔥 Mantén tu racha de estudio

También puedes:
   • Preguntar sobre temas: "¿cómo regar aguacate?"
   • Pedir ayuda en cualquier momento

Estoy aquí para enseñarte agricultura colombiana paso a paso."""
    
    # ========== SISTEMA DE CURSOS ==========
    
    # Número inválido (detectado por usuario)
    if intent == 'numero_invalido':
        return """❌ Ese número no es válido.

Las opciones son:

1️⃣  Ver mi progreso
2️⃣  Ver cursos disponibles
3️⃣  Continuar mi curso actual

Escribe solo UN número (1, 2 o 3)"""
    
    # Ver cursos disponibles
    if intent == 'ver_cursos':
        from .models import Curso
        cursos_activos = Curso.objects.filter(activo=True).order_by('orden')
        
        if not cursos_activos.exists():
            return "No hay cursos disponibles en este momento. ⚠️"
        
        respuesta = "CURSOS DISPONIBLES EN EKI\n\n"
        respuesta += "Selecciona el número del curso:\n\n"
        
        for idx, curso in enumerate(cursos_activos, 1):
            respuesta += f"{idx}. {curso.emoji} {curso.nombre}\n"
            respuesta += f"   📅 {curso.duracion_semanas} semanas\n"
            respuesta += f"   📖 {curso.modulos.count()} módulos\n\n"
        
        respuesta += "Para inscribirte, escribe:\n"
        respuesta += "   Solo el número: \"1\""
        return respuesta
    
    # Inscribirse en curso
    if intent == 'inscribir_curso':
        mensaje_original = kwargs.get('mensaje_original', '').lower().strip()
        from .models import Curso, ProgresoEstudiante, Estudiante
        import re
        
        curso = None
        
        # Detectar "tomar 1", "inscribir 1", "inscribir 2", etc
        match = re.search(r'(tomar|inscribir|inscribirme)\s*(\d+)', mensaje_original)
        if match:
            numero_curso = int(match.group(2))
            cursos_activos = Curso.objects.filter(activo=True).order_by('orden')
            if 1 <= numero_curso <= cursos_activos.count():
                curso = list(cursos_activos)[numero_curso - 1]
        # Detectar si es solo un número (como fallback)
        elif re.match(r'^(\d+)$', mensaje_original):
            numero_curso = int(mensaje_original)
            cursos_activos = Curso.objects.filter(activo=True).order_by('orden')
            if 1 <= numero_curso <= cursos_activos.count():
                curso = list(cursos_activos)[numero_curso - 1]
        else:
            # Fallback: detectar por nombre (por si escriben el nombre)
            if 'aguacate' in mensaje_original or 'hass' in mensaje_original:
                curso = Curso.objects.filter(nombre__icontains='aguacate', activo=True).first()
            elif 'cafe' in mensaje_original or 'café' in mensaje_original:
                curso = Curso.objects.filter(nombre__icontains='cafe', activo=True).first()
        
        if not curso:
            return """No encontré ese curso. 🤔
            
Escribe "2" para ver cursos disponibles."""
        
        estudiante_id = kwargs.get('estudiante_id')
        if not estudiante_id:
            return "Error al identificar estudiante. ⚠️"
        
        estudiante = Estudiante.objects.get(id=estudiante_id)
        
        # Verificar si ya está inscrito
        progreso_existente = ProgresoEstudiante.objects.filter(
            estudiante=estudiante,
            curso=curso
        ).first()
        
        if progreso_existente:
            porcentaje = progreso_existente.porcentaje_avance()
            modulo_actual = progreso_existente.modulo_actual
            
            if progreso_existente.completado:
                return f"""Ya completaste {curso.emoji} {curso.nombre}
                
¡Felicidades! Terminaste el curso al 100%

Puedes:
   • Escribir "examen" para volver a tomar el examen
   • Escribir "ver cursos" para tomar otro curso"""
            
            # Actualizar fecha para que sea el curso más reciente
            from django.utils import timezone
            progreso_existente.fecha_inicio = timezone.now()
            progreso_existente.save()
            
            return f"""✅ Retomando {curso.emoji} {curso.nombre}
            
Módulo actual: {modulo_actual.numero}. {modulo_actual.titulo}
📈 Tu avance: {porcentaje}%

Escribe "continuar" para seguir con tu lección."""
        
        # Inscribir al estudiante
        primer_modulo = curso.modulos.order_by('numero').first()
        progreso = ProgresoEstudiante.objects.create(
            estudiante=estudiante,
            curso=curso,
            modulo_actual=primer_modulo
        )
        
        return f"""✅ {curso.emoji} ¡Inscripción exitosa!

Te inscribiste en: {curso.nombre}

📚 Total: {curso.modulos.count()} módulos
⏱️ Duración: {curso.duracion_semanas} semanas

---

Módulo 1: {primer_modulo.titulo}

{primer_modulo.contenido}

---

Cuando termines, escribe: *"listo"*
O pregúntame dudas sobre este tema."""
    
    # Continuar con lección
    if intent == 'continuar_leccion':
        from .models import ProgresoEstudiante, ModuloCompletado
        
        estudiante_id = kwargs.get('estudiante_id')
        if not estudiante_id:
            return "Error al identificar estudiante. ⚠️"
        
        from .models import Estudiante
        estudiante = Estudiante.objects.get(id=estudiante_id)
        
        mensaje_original = kwargs.get('mensaje_original', '').lower()
        
        # Buscar todos los progresos activos (no completados)
        progresos_activos = ProgresoEstudiante.objects.filter(
            estudiante=estudiante,
            completado=False
        ).order_by('-fecha_inicio')
        
        if not progresos_activos.exists():
            return """No tienes cursos activos. 📚

Escribe "ver cursos" para inscribirte en uno."""
        
        # Siempre continuar con el curso MÁS RECIENTE (primer progreso ordenado por -fecha_inicio)
        # Ya no preguntar, continuar directo
        progreso = progresos_activos.first()
        
        if not progreso:
            return """No tienes cursos activos. 📚

Escribe "ver cursos" para inscribirte en uno."""
        
        # Obtener módulo actual
        modulo_actual = progreso.modulo_actual
        if not modulo_actual:
            # Si no hay módulo actual, tomar el primero
            modulo_actual = progreso.curso.modulos.order_by('numero').first()
            progreso.modulo_actual = modulo_actual
            progreso.save()
        
        # Si escribieron "listo" o "siguiente", significa que terminaron el módulo actual
        # Completarlo y avanzar al siguiente
        palabras_completar = ['listo', 'siguiente', 'ok', 'dale', 'avanzar', 'sigue']
        if any(palabra in mensaje_original for palabra in palabras_completar):
            # Obtener perfil ANTES de completar módulo
            from .gamificacion import PerfilGamificacion
            perfil, _ = PerfilGamificacion.objects.get_or_create(estudiante=estudiante)
            nivel_antes = perfil.nivel
            
            # Marcar módulo actual como completado
            # Esto dispara la señal que otorga 50 puntos automáticamente
            ModuloCompletado.objects.get_or_create(
                progreso=progreso,
                modulo=modulo_actual
            )
            
            # Refrescar perfil para ver si subió de nivel
            perfil.refresh_from_db()
            subio_nivel = perfil.nivel > nivel_antes
            
            # Buscar siguiente módulo
            siguiente_modulo = progreso.curso.modulos.filter(numero=modulo_actual.numero + 1).first()
            
            if siguiente_modulo:
                # Actualizar progreso al siguiente módulo
                progreso.modulo_actual = siguiente_modulo
                progreso.save()
                
                porcentaje = progreso.porcentaje_avance()
                
                # Mostrar el siguiente módulo automáticamente
                video_url = obtener_video_url(siguiente_modulo)
                mensaje = f"""✅ ¡Módulo {modulo_actual.numero} completado!
⭐ +50 puntos | Total: {perfil.puntos_totales} pts"""
                
                # Si subió de nivel, celebrar!
                if subio_nivel:
                    nivel_emoji = ["🌱", "🌿", "🍃", "🌾", "🌳", "🌲", "🎋", "🌺", "💎", "👑"][perfil.nivel - 1]
                    mensaje += f"\n\n🎉 ¡SUBISTE DE NIVEL! {nivel_emoji} Nivel {perfil.nivel}"
                
                mensaje += f"""

Progreso del curso: {porcentaje}%

━━━━━━━━━━━━━━━━━━━━

📖 Módulo {siguiente_modulo.numero}: {siguiente_modulo.titulo}

{siguiente_modulo.contenido}

━━━━━━━━━━━━━━━━━━━━

Cuando termines, escribe: *"listo"*
O pregúntame dudas sobre este tema."""
                
                if video_url:
                    mensaje += f"\n\n🎥 Video educativo:\n{video_url}"
                
                return mensaje
            
            else:
                # Completó todos los módulos
                # Marcar curso como completado
                progreso.completado = True
                progreso.fecha_finalizacion = timezone.now()
                progreso.save()
                
                # Refrescar perfil para ver badges obtenidos
                perfil.refresh_from_db()
                
                porcentaje = progreso.porcentaje_avance()
                
                # Buscar badges obtenidos por este curso
                from .gamificacion import BadgeEstudiante
                badges_nuevos = BadgeEstudiante.objects.filter(
                    estudiante=estudiante,
                    badge__tipo='CURSO'
                ).order_by('-fecha_obtenido')[:2]
                
                mensaje = f"""✅ ¡Módulo {modulo_actual.numero} completado!
⭐ +50 puntos

🎉 ¡COMPLETASTE EL CURSO!
🏆 +200 puntos BONUS

Total: {perfil.puntos_totales} pts | Nivel {perfil.nivel}"""
                
                # Mostrar badges obtenidos
                if badges_nuevos.exists():
                    mensaje += "\n\n🏅 LOGROS DESBLOQUEADOS:"
                    for badge_est in badges_nuevos:
                        mensaje += f"\n{badge_est.badge.icono} {badge_est.badge.nombre}"
                
                # Si subió de nivel, celebrar!
                if subio_nivel:
                    nivel_emoji = ["🌱", "🌿", "🍃", "🌾", "🌳", "🌲", "🎋", "🌺", "💎", "👑"][perfil.nivel - 1]
                    mensaje += f"\n\n✨ ¡SUBISTE A {nivel_emoji} NIVEL {perfil.nivel}!"
                
                mensaje += f"""

━━━━━━━━━━━━━━━━━━━━

Progreso: {porcentaje}%

¿Quieres hacer el examen final?

Escribe *"examen"* o *"si"*
Escribe *"ver cursos"* para tomar otro curso
Escribe *"mi progreso"* para ver tu avance"""
                
                return mensaje
        
        # Si escribieron solo "continuar" (primera vez o retomando), mostrar el módulo actual
        else:
            video_url = obtener_video_url(modulo_actual)
            respuesta = f"""{progreso.curso.emoji} {progreso.curso.nombre}

Módulo {modulo_actual.numero}: {modulo_actual.titulo}

{modulo_actual.contenido}

---

Cuando termines esta lección, escribe:
   *"listo"* o *"siguiente"*

O pregúntame dudas sobre este tema."""
            
            if video_url:
                respuesta += f"\n\n🎥 Video educativo:\n{video_url}"
            
            return respuesta
    
    # Ver mi progreso en cursos
    if intent == 'mi_progreso_cursos':
        from .models import ProgresoEstudiante
        
        estudiante_id = kwargs.get('estudiante_id')
        if not estudiante_id:
            return "Error al identificar estudiante. ⚠️"
        
        from .models import Estudiante
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
    
    # Iniciar examen
    if intent == 'iniciar_examen':
        from .models import ProgresoEstudiante, Examen
        
        estudiante_id = kwargs.get('estudiante_id')
        if not estudiante_id:
            return "Error al identificar estudiante. ⚠️"
        
        from .models import Estudiante
        estudiante = Estudiante.objects.get(id=estudiante_id)
        
        # Buscar progreso activo
        progreso = ProgresoEstudiante.objects.filter(
            estudiante=estudiante,
            completado=False
        ).first()
        
        if not progreso:
            return """No tienes cursos activos para tomar examen. 📚

Escribe "ver cursos" para inscribirte."""
        
        # Verificar que haya completado todos los módulos
        total_modulos = progreso.curso.modulos.count()
        modulos_completados = progreso.modulos_completados.count()
        
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
    
    return f"Hola {nombre_usuario}, ¿cómo te puedo ayudar con tu aprendizaje agropecuario? 🌱"
