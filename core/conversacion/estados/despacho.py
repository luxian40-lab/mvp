"""Qué handler atiende cada estado del motor de curso.

BARRERAS se busca por `estado_chat` durante el onboarding: el handler siempre
corta el turno. AGENTES se busca por `estado_onboarding` en la cadena de
agentes: el handler deja `texto_respuesta` para el envío común del cuerpo.
"""
from core.conversacion.estados import (
    asistente,
    cedula,
    confirmando_datos,
    correccion_legado,
    curso_finalizado,
    empleabilidad,
    modulo,
    pregunta_abierta_final,
    reto,
    seleccion_curso,
)

BARRERAS = {
    'ESPERANDO_CEDULA': cedula.manejar,
    # Sí: activa y entrega el primer módulo. Modificar: ticket de soporte. Otro: reenvía la plantilla.
    'CONFIRMANDO_DATOS': confirmando_datos.manejar,
    # Corrección legado: vuelve a ACTIVO y dice «Listo», o abre ticket si pide ayuda.
    'ESPERANDO_AYUDA_MODIFICAR': correccion_legado.manejar,
    'ESPERANDO_CORRECCION_DATOS': correccion_legado.manejar,
}

AGENTES = {
    # Radar: código secreto del aliado. Con la empleabilidad en pausa, agente_de no lo despacha.
    'esperando_codigo_empleabilidad': empleabilidad.manejar,
    # Después del certificado: solo avisa si hay un curso nuevo.
    'curso_finalizado': curso_finalizado.manejar,
    # Asistente (compañero): hasta 2 preguntas antes del reto.
    'esperando_respuesta_asistente': asistente.manejar,
    # Respuesta abierta final, calificada por la facilitadora.
    'esperando_respuesta_pregunta_abierta_final': pregunta_abierta_final.manejar,
    # Facilitadora: evalúa la respuesta al reto (texto, audio o foto de evidencia).
    'esperando_respuesta_reto': reto.manejar,
    # Examen clásico del módulo: valida la letra, avanza o cierra el curso.
    'esperando_respuesta_modulo': modulo.manejar,
    # Lista numerada de cursos (B2B con 2+ cursos). Con estado_chat ACTIVO la atiende antes la copia
    # del bloque ACTIVO; esta atiende a quien llega con un estado_chat legado.
    'esperando_seleccion_curso': seleccion_curso.manejar,
}


def agente_de(estado_onboarding):
    """Handler de la cadena de agentes, o None para la rama por defecto del cuerpo."""
    if estado_onboarding == 'esperando_codigo_empleabilidad':
        from core.empleabilidad_pausa import empleabilidad_en_pausa

        if empleabilidad_en_pausa():
            return None
    return AGENTES.get(estado_onboarding)
