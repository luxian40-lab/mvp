def procesar_respuesta_abierta_ia(estudiante, respuesta_usuario):
    """
    Procesa una respuesta abierta generada por IA usando el Evaluador IA.
    Evalúa comprensión real del módulo con empatía.
    Args:
        estudiante: instancia de Estudiante
        respuesta_usuario: texto libre enviado por el estudiante
    Returns:
        tuple: (es_valida: bool, mensaje_feedback: str)
    """
    # Intentar evaluar con IA
    try:
        from .tutor_ia_modulo import evaluar_respuesta_modulo
        from .models import Modulo
        ctx = estudiante.contexto_temporal or {}
        modulo_id = ctx.get('modulo_id')
        pregunta_original = ctx.get('pregunta_tutor', '')
        
        if modulo_id:
            modulo = Modulo.objects.get(id=modulo_id)
            aprobado, feedback = evaluar_respuesta_modulo(
                modulo, respuesta_usuario, pregunta_original,
                estudiante_nombre=estudiante.nombre or "Estudiante"
            )
            estudiante.estado_onboarding = 'completado'
            estudiante.contexto_temporal = None
            estudiante.save()
            return aprobado, feedback
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"⚠️ Evaluador IA falló: {e}")
    
    # Fallback: siempre motivar
    estudiante.estado_onboarding = 'completado'
    estudiante.save()
    mensaje = (
        "✅ ¡Gracias por tu respuesta!\n\n"
        "Tu reflexión es muy valiosa para tu aprendizaje.\n\n"
        "Sigue avanzando y no dudes en preguntar si tienes dudas.\n\n"
        "💡 Recuerda: lo importante es que apliques lo aprendido en tu día a día."
    )
    return True, mensaje
"""
Sistema de mini exámenes por módulo
"""
from .models import PreguntaModulo, ModuloCompletado, Estudiante
from django.utils import timezone
import random


def tiene_pregunta_modulo(modulo):
    """Verifica si el módulo tiene pregunta activa"""
    return PreguntaModulo.objects.filter(modulo=modulo, activa=True).exists()


def obtener_pregunta_modulo(modulo):
    """Obtiene una pregunta aleatoria del módulo"""
    preguntas = list(PreguntaModulo.objects.filter(modulo=modulo, activa=True))
    if not preguntas:
        return None
    return random.choice(preguntas)


def formatear_pregunta(pregunta):
    """
    Formatea la pregunta para WhatsApp con opciones
    
    Args:
        pregunta: instancia de PreguntaModulo
    
    Returns:
        str: mensaje formateado
    """
    mensaje = f"""📝 *PREGUNTA DE VALIDACIÓN*

{pregunta.pregunta}

🔹 A) {pregunta.opcion_a}
🔹 B) {pregunta.opcion_b}"""
    
    if pregunta.opcion_c:
        mensaje += f"\n🔹 C) {pregunta.opcion_c}"
    
    if pregunta.opcion_d:
        mensaje += f"\n🔹 D) {pregunta.opcion_d}"
    
    mensaje += "\n\n💡 Responde con la letra correcta (A, B, C o D)"
    
    return mensaje


def validar_respuesta(estudiante, respuesta_letra):
    """
    Valida la respuesta del estudiante al mini examen
    
    Args:
        estudiante: instancia de Estudiante
        respuesta_letra: 'A', 'B', 'C' o 'D'
    
    Returns:
        tuple: (es_correcta: bool, mensaje_respuesta: str, modulo_completado: ModuloCompletado)
    """
    # Obtener contexto temporal
    if not estudiante.contexto_temporal:
        return False, "❌ Error: No hay pregunta pendiente", None
    
    modulo_id = estudiante.contexto_temporal.get('modulo_id')
    pregunta_id = estudiante.contexto_temporal.get('pregunta_id')
    progreso_id = estudiante.contexto_temporal.get('progreso_id')
    
    if not all([modulo_id, pregunta_id, progreso_id]):
        return False, "❌ Error: Contexto incompleto", None
    
    # Obtener pregunta y progreso
    from .models import Modulo, ProgresoEstudiante
    try:
        pregunta = PreguntaModulo.objects.get(id=pregunta_id)
        modulo = Modulo.objects.get(id=modulo_id)
        progreso = ProgresoEstudiante.objects.get(id=progreso_id)
    except (PreguntaModulo.DoesNotExist, Modulo.DoesNotExist, ProgresoEstudiante.DoesNotExist):
        return False, "❌ Error: Datos no encontrados", None
    
    # Normalizar respuesta
    respuesta_letra = respuesta_letra.upper().strip()
    
    # Validar formato
    opciones_validas = ['A', 'B']
    if pregunta.opcion_c:
        opciones_validas.append('C')
    if pregunta.opcion_d:
        opciones_validas.append('D')
    
    if respuesta_letra not in opciones_validas:
        return False, f"❌ Opción inválida. Responde: {', '.join(opciones_validas)}", None
    
    # Verificar si es correcta
    es_correcta = (respuesta_letra == pregunta.respuesta_correcta.upper())
    
    # Obtener perfil ANTES de crear módulo completado
    from .gamificacion import PerfilGamificacion
    perfil, _ = PerfilGamificacion.objects.get_or_create(estudiante=estudiante)
    nivel_antes = perfil.nivel
    
    # Crear registro de módulo completado
    # IMPORTANTE: Esto dispara el signal post_save que otorga +50 puntos automáticamente
    modulo_completado, created = ModuloCompletado.objects.get_or_create(
        progreso=progreso,
        modulo=modulo,
        defaults={
            'pregunta_respondida': pregunta,
            'respuesta_dada': respuesta_letra,
            'respuesta_correcta': es_correcta
        }
    )
    
    # Si ya existía, actualizar
    if not created:
        modulo_completado.pregunta_respondida = pregunta
        modulo_completado.respuesta_dada = respuesta_letra
        modulo_completado.respuesta_correcta = es_correcta
        modulo_completado.save()
    
    # REFRESCAR perfil después del signal (que ya otorgó +50 pts)
    perfil.refresh_from_db()
    
    # Ahora agregar el bonus si respondió correctamente
    if es_correcta:
        perfil.agregar_puntos(10, f"📝 Respuesta correcta: {modulo.titulo}")
        perfil.refresh_from_db()
    
    # Verificar si subió de nivel DESPUÉS de todos los puntos
    subio_nivel = perfil.nivel > nivel_antes
    
    # Limpiar contexto temporal
    estudiante.contexto_temporal = None
    estudiante.estado_onboarding = 'completado'
    estudiante.save()
    
    # Generar mensaje de respuesta
    if es_correcta:
        mensaje = f"""✅ *¡CORRECTO!* 🎉

⭐ +50 puntos por módulo
⭐ +10 puntos bonus por respuesta correcta
💰 Total: {perfil.puntos_totales} pts"""
        
        # Si subió de nivel, celebrar!
        if subio_nivel:
            nivel_index = min(perfil.nivel - 1, 9)
            nivel_emoji = ["🌱", "🌿", "🍃", "🌾", "🌳", "🌲", "🎋", "🌺", "💎", "👑"][nivel_index]
            mensaje += f"\n\n🎉 *¡SUBISTE DE NIVEL!* {nivel_emoji} Nivel {perfil.nivel}"
        
        if pregunta.explicacion:
            mensaje += f"\n\n💡 {pregunta.explicacion}"
    
    else:
        # Respuesta incorrecta
        respuesta_correcta_texto = {
            'A': pregunta.opcion_a,
            'B': pregunta.opcion_b,
            'C': pregunta.opcion_c if pregunta.opcion_c else None,
            'D': pregunta.opcion_d if pregunta.opcion_d else None
        }.get(pregunta.respuesta_correcta.upper())
        
        mensaje = f"""❌ *Respuesta incorrecta*

✅ La respuesta correcta era: *{pregunta.respuesta_correcta.upper()}) {respuesta_correcta_texto}*

⭐ +50 puntos por completar módulo
💰 Total: {perfil.puntos_totales} pts"""
        
        if pregunta.explicacion:
            mensaje += f"\n\n💡 {pregunta.explicacion}"
        
        mensaje += "\n\n🔄 ¡No te preocupes! Cada error es una oportunidad de aprender."
    
    return es_correcta, mensaje, modulo_completado


def guardar_contexto_pregunta(estudiante, modulo, pregunta, progreso):
    """
    Guarda el contexto temporal para que el estudiante responda la pregunta
    
    Args:
        estudiante: instancia de Estudiante
        modulo: instancia de Modulo
        pregunta: instancia de PreguntaModulo
        progreso: instancia de ProgresoEstudiante
    """
    estudiante.contexto_temporal = {
        'modulo_id': modulo.id,
        'pregunta_id': pregunta.id,
        'progreso_id': progreso.id,
        'tipo': 'pregunta_modulo'
    }
    estudiante.estado_onboarding = 'esperando_respuesta_modulo'
    estudiante.save()
