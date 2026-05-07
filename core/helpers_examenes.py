"""
Helpers para validación de exámenes obligatorios y progreso de estudiantes
"""

from django.utils import timezone
from .models import Examen, Modulo, ProgresoEstudiante, ModuloCompletado


def puede_avanzar_modulo(estudiante, modulo_actual):
    """
    Verifica si el estudiante puede avanzar al siguiente módulo
    Valida examen obligatorio si está configurado
    
    Args:
        estudiante: Instancia de Estudiante
        modulo_actual: Instancia de Módulo actual
        
    Returns:
        tuple: (puede_avanzar: bool, mensaje: str, detalles: dict)
    """
    
    # Si no tiene examen obligatorio, puede avanzar libremente
    if not modulo_actual.examen_obligatorio:
        return True, "OK", {'razon': 'sin_examen_obligatorio'}
    
    # Buscar el último intento de examen de este módulo
    ultimo_examen = Examen.objects.filter(
        estudiante=estudiante,
        modulo=modulo_actual
    ).order_by('-fecha').first()
    
    # Si no hay intentos, no puede avanzar
    if not ultimo_examen:
        return False, f"Debes completar el examen del módulo '{modulo_actual.titulo}' para continuar", {
            'razon': 'sin_intento',
            'modulo': modulo_actual.titulo,
            'puntaje_minimo': modulo_actual.puntaje_minimo_aprobacion
        }
    
    # Verificar si aprobó
    if ultimo_examen.puntaje < modulo_actual.puntaje_minimo_aprobacion:
        return False, f"Necesitas {modulo_actual.puntaje_minimo_aprobacion}% para aprobar. Obtuviste {ultimo_examen.puntaje}%. Intenta de nuevo.", {
            'razon': 'no_aprobado',
            'puntaje_obtenido': ultimo_examen.puntaje,
            'puntaje_minimo': modulo_actual.puntaje_minimo_aprobacion,
            'diferencia': modulo_actual.puntaje_minimo_aprobacion - ultimo_examen.puntaje
        }
    
    # ¡Aprobó!
    return True, "Examen aprobado. Puedes continuar.", {
        'razon': 'aprobado',
        'puntaje': ultimo_examen.puntaje,
        'puntaje_minimo': modulo_actual.puntaje_minimo_aprobacion
    }


def obtener_siguiente_modulo(estudiante, curso):
    """
    Obtiene el siguiente módulo disponible para el estudiante
    Considera exámenes obligatorios y progreso
    
    Args:
        estudiante: Instancia de Estudiante
        curso: Instancia de Curso
        
    Returns:
        Modulo o None
    """
    # Obtener progreso del estudiante en el curso
    progreso, _ = ProgresoEstudiante.objects.get_or_create(
        estudiante=estudiante,
        curso=curso
    )
    
    # Si no tiene módulo actual, retornar el primero
    if not progreso.modulo_actual:
        primer_modulo = curso.modulos.filter(activo=True).order_by('numero').first()
        return primer_modulo
    
    modulo_actual = progreso.modulo_actual
    
    # Verificar si puede avanzar del módulo actual
    puede_avanzar, mensaje, detalles = puede_avanzar_modulo(estudiante, modulo_actual)
    
    if not puede_avanzar:
        # Debe repetir el módulo actual
        return modulo_actual
    
    # Buscar el siguiente módulo
    siguiente_modulo = curso.modulos.filter(
        activo=True,
        numero__gt=modulo_actual.numero
    ).order_by('numero').first()

    if siguiente_modulo:
        from .drip_schedule import drip_bloquea_siguiente_modulo

        if drip_bloquea_siguiente_modulo(progreso, modulo_actual):
            return modulo_actual

    return siguiente_modulo


def verificar_modulo_completado(estudiante, modulo):
    """
    Verifica si un módulo está realmente completado
    (contenido visto + examen aprobado si es obligatorio)
    
    Args:
        estudiante: Instancia de Estudiante
        modulo: Instancia de Módulo
        
    Returns:
        bool
    """
    # Verificar si está marcado como completado
    completado = ModuloCompletado.objects.filter(
        estudiante=estudiante,
        modulo=modulo
    ).exists()
    
    if not completado:
        return False
    
    # Si tiene examen obligatorio, verificar aprobación
    if modulo.examen_obligatorio:
        puede_avanzar, _, _ = puede_avanzar_modulo(estudiante, modulo)
        return puede_avanzar
    
    return True


def reintentar_examen(estudiante, modulo):
    """
    Permite al estudiante reintentar un examen
    Resetea el estado del examen pero mantiene el historial
    
    Args:
        estudiante: Instancia de Estudiante
        modulo: Instancia de Módulo
        
    Returns:
        dict con información del reintento
    """
    # Contar intentos previos
    intentos_previos = Examen.objects.filter(
        estudiante=estudiante,
        modulo=modulo
    ).count()
    
    # Obtener el último intento
    ultimo_intento = Examen.objects.filter(
        estudiante=estudiante,
        modulo=modulo
    ).order_by('-fecha').first()
    
    return {
        'puede_reintentar': True,
        'intentos_previos': intentos_previos,
        'ultimo_puntaje': ultimo_intento.puntaje if ultimo_intento else 0,
        'puntaje_minimo': modulo.puntaje_minimo_aprobacion,
        'mensaje': f'Tienes {intentos_previos} intento(s) previo(s). ¡Sigue intentando!'
    }


def obtener_modulos_bloqueados(estudiante, curso):
    """
    Obtiene lista de módulos bloqueados por exámenes no aprobados
    
    Args:
        estudiante: Instancia de Estudiante
        curso: Instancia de Curso
        
    Returns:
        list de dict con módulos bloqueados y razones
    """
    modulos_bloqueados = []
    modulos = curso.modulos.filter(activo=True).order_by('numero')
    
    for modulo in modulos:
        if modulo.examen_obligatorio:
            puede_avanzar, mensaje, detalles = puede_avanzar_modulo(estudiante, modulo)
            
            if not puede_avanzar:
                modulos_bloqueados.append({
                    'modulo': modulo,
                    'numero': modulo.numero,
                    'titulo': modulo.titulo,
                    'mensaje': mensaje,
                    'detalles': detalles
                })
    
    return modulos_bloqueados


def calcular_progreso_curso_real(estudiante, curso):
    """
    Calcula el progreso real del curso considerando exámenes obligatorios
    No cuenta módulos "completados" si no han aprobado el examen
    
    Args:
        estudiante: Instancia de Estudiante
        curso: Instancia de Curso
        
    Returns:
        dict con información de progreso
    """
    total_modulos = curso.modulos.filter(activo=True).count()
    
    if total_modulos == 0:
        return {
            'total_modulos': 0,
            'modulos_completados': 0,
            'porcentaje': 0,
            'modulos_bloqueados': 0
        }
    
    # Contar solo módulos realmente completados
    modulos_completados_count = 0
    for modulo in curso.modulos.filter(activo=True):
        if verificar_modulo_completado(estudiante, modulo):
            modulos_completados_count += 1
    
    # Módulos bloqueados
    bloqueados = obtener_modulos_bloqueados(estudiante, curso)
    
    porcentaje = int((modulos_completados_count / total_modulos) * 100)
    
    return {
        'total_modulos': total_modulos,
        'modulos_completados': modulos_completados_count,
        'porcentaje': porcentaje,
        'modulos_bloqueados': len(bloqueados),
        'bloqueados_detalles': bloqueados
    }


def notificar_examen_no_aprobado(estudiante, modulo, puntaje):
    """
    Envía notificación al estudiante cuando no aprueba un examen obligatorio
    
    Args:
        estudiante: Instancia de Estudiante
        modulo: Instancia de Módulo
        puntaje: Puntaje obtenido
        
    Returns:
        bool: True si se envió notificación
    """
    from .whatsapp_sender import enviar_mensaje_whatsapp
    
    diferencia = modulo.puntaje_minimo_aprobacion - puntaje
    
    mensaje = f"""
📝 RESULTADO DEL EXAMEN

{estudiante.nombre}, completaste el examen de:
📚 {modulo.titulo}

Tu calificación: {puntaje}%
Mínimo requerido: {modulo.puntaje_minimo_aprobacion}%

❌ No alcanzaste el puntaje mínimo.
Te faltan {diferencia} puntos para aprobar.

💪 ¡No te desanimes!
Puedes repasar el contenido e intentar de nuevo.

Escribe "reintentar examen" para volver a intentarlo.
"""
    
    try:
        enviar_mensaje_whatsapp(estudiante.telefono, mensaje)
        return True
    except Exception as e:
        print(f"Error enviando notificación: {e}")
        return False


def notificar_examen_aprobado(estudiante, modulo, puntaje):
    """
    Envía notificación al estudiante cuando aprueba un examen
    
    Args:
        estudiante: Instancia de Estudiante
        modulo: Instancia de Módulo
        puntaje: Puntaje obtenido
        
    Returns:
        bool: True si se envió notificación
    """
    from .whatsapp_sender import enviar_mensaje_whatsapp
    
    # Emoji según el puntaje
    if puntaje == 100:
        emoji_resultado = "🏆"
        mensaje_extra = "¡PERFECTO! 100%"
    elif puntaje >= 90:
        emoji_resultado = "⭐"
        mensaje_extra = "¡Excelente trabajo!"
    elif puntaje >= 80:
        emoji_resultado = "✅"
        mensaje_extra = "¡Muy bien!"
    else:
        emoji_resultado = "✅"
        mensaje_extra = "¡Aprobado!"
    
    mensaje = f"""
{emoji_resultado} ¡EXAMEN APROBADO!

{estudiante.nombre}, completaste exitosamente:
📚 {modulo.titulo}

Tu calificación: {puntaje}%
{mensaje_extra}

🎉 Puedes continuar con el siguiente módulo.

Escribe "siguiente" para avanzar.
"""
    
    try:
        enviar_mensaje_whatsapp(estudiante.telefono, mensaje)
        return True
    except Exception as e:
        print(f"Error enviando notificación: {e}")
        return False


def contexto_temporal_tras_cerrar_agente(progreso=None, ctx_previo=None):
    """
    Al cerrar reto/facilitadora, no borrar del todo el contexto: conservar curso_activo_id.
    Si continuar_leccion pierde el foco (p. ej. varios ProgresoEstudiante activos),
    puede elegir otro curso todavía en módulo 3 y repetir compañero + facilitadora.
    """
    out = {}
    cid = None
    if progreso is not None:
        cid = getattr(progreso, "curso_id", None)
    if not cid and ctx_previo:
        cid = ctx_previo.get("curso_activo_id")
    if cid:
        out["curso_activo_id"] = int(cid)
    if ctx_previo and "_ts_leccion" in ctx_previo:
        out["_ts_leccion"] = ctx_previo["_ts_leccion"]
    return out or None


def debe_activar_checkpoint_reto_ia(numero_modulo: int, total_modulos: int, usar_agentes_ia_curso: bool) -> bool:
    """
    Punto único de verdad: tras qué módulos activar compañero + facilitadora (reto).
    Debe coincidir con la rama de examen en views (esperando_respuesta_modulo).
    """
    if not usar_agentes_ia_curso:
        return False
    es_ultimo_modulo = numero_modulo == total_modulos and total_modulos >= 1
    es_modulo_intermedio_post5 = (
        total_modulos > 5
        and numero_modulo > 5
        and numero_modulo % 3 == 0
        and not es_ultimo_modulo
    )
    return (
        numero_modulo == 3
        or (numero_modulo == total_modulos and total_modulos >= 5)
        or es_modulo_intermedio_post5
    )


def es_modulo_checkpoint_reto_ia(modulo, total_modulos: int, usar_agentes_ia_curso: bool) -> bool:
    """
    Igual que la regla numérica, pero con override por módulo (admin: checkpoint facilitadora).
    """
    from .models import Modulo

    if not usar_agentes_ia_curso or not modulo:
        return False
    pref = getattr(modulo, 'facilitador_checkpoint', None) or Modulo.FACILITADOR_CP_AUTO
    try:
        numero = int(modulo.numero)
    except (TypeError, ValueError):
        return False
    if pref == Modulo.FACILITADOR_CP_NO:
        return False
    if pref == Modulo.FACILITADOR_CP_SI:
        return True
    return debe_activar_checkpoint_reto_ia(numero, total_modulos, True)
