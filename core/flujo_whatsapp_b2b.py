"""
Flujo WhatsApp B2B: sin menú 1-2-3.

El orden lo marca la campaña (curso_destino); el estudiante avanza con *listo*.
Sandbox / estudiantes sin cliente conservan el menú numerado legacy.
"""
from __future__ import annotations

from typing import Any

INTENTS_SIN_MENU_NUMERADO = frozenset({
    'opcion_2',
    'opcion_numerica',
    'ver_cursos',
    'tareas',
    'inscribir_curso',
})


def es_estudiante_b2b(estudiante) -> bool:
    return bool(getattr(estudiante, 'cliente_id', None))


def es_keyword_retomar(texto_norm: str) -> bool:
    return texto_norm in {'menu', 'inicio', 'hola'}


def salir_seleccion_curso_legacy(estudiante) -> None:
    """Sale del estado legacy de lista numerada de cursos."""
    update_fields = []
    ctx = dict(estudiante.contexto_temporal or {})
    if 'tipo' in ctx:
        ctx.pop('tipo', None)
        estudiante.contexto_temporal = ctx or None
        update_fields.append('contexto_temporal')
    if estudiante.estado_onboarding == 'esperando_seleccion_curso':
        estudiante.estado_onboarding = 'completado'
        update_fields.append('estado_onboarding')
    if update_fields:
        estudiante.save(update_fields=update_fields)


def texto_ayuda_comandos(estudiante) -> str:
    nombre = (getattr(estudiante, 'nombre', '') or 'estudiante').split()[0]
    return (
        f"Hola {nombre}.\n\n"
        "📚 *listo* — continuar tu lección\n"
        "📊 *progreso* — ver tu avance\n"
        "✏️ *corregir datos* — actualizar nombre, municipio o cédula\n"
        "🆘 *ayuda* — soporte"
    )


def resolver_progreso_b2b(estudiante):
    """Progreso activo según campaña / catálogo del cliente (sin elegir por número)."""
    from .selector_curso import asegurar_inscripcion_catalogo_cliente

    if not es_estudiante_b2b(estudiante):
        return None
    return asegurar_inscripcion_catalogo_cliente(estudiante)


def mensaje_curso_por_campana(estudiante) -> str:
    from .selector_curso import asegurar_inscripcion_catalogo_cliente

    salir_seleccion_curso_legacy(estudiante)
    prog = asegurar_inscripcion_catalogo_cliente(estudiante)
    org = estudiante.cliente.nombre if estudiante.cliente else 'tu organización'
    if prog and prog.curso:
        return (
            f"📚 Tu programa en *{org}* avanza por campaña.\n\n"
            f"Curso actual: *{prog.curso.nombre}*\n\n"
            "Escribe *listo* para continuar tu lección.\n"
            "Escribe *progreso* para ver tu avance.\n"
            "Escribe *ayuda* si necesitas soporte."
        )
    return (
        f"Tu organización (*{org}*) activará tu curso por campaña.\n\n"
        "Escribe *ayuda* si tienes dudas."
    )


def mensaje_digitos_sin_menu(estudiante) -> str:
    """Cuando un B2B escribe 1, 2, 3 o un número de curso sin menú."""
    base = mensaje_curso_por_campana(estudiante)
    return f"{base}\n\n_Tip: no hace falta elegir con números; escribe *listo* para seguir._"


def respuesta_b2b_sin_menu(estudiante, intent: str, nombre_usuario: str, kwargs: dict[str, Any]) -> str | None:
    """Intercepta intents de menú/lista para estudiantes con cliente (B2B)."""
    if not es_estudiante_b2b(estudiante):
        return None

    if intent in INTENTS_SIN_MENU_NUMERADO:
        return mensaje_curso_por_campana(estudiante)

    if intent == 'opcion_3':
        return _texto_ayuda_b2b(nombre_usuario)

    if intent == 'numero_invalido':
        return (
            "Ese número no aplica en tu programa.\n\n"
            "Escribe *listo* para continuar, *progreso* para tu avance o *ayuda* para soporte."
        )

    if intent == 'saludo':
        salir_seleccion_curso_legacy(estudiante)
        return None

    return None


def respuesta_tras_keyword_menu(estudiante, nombre: str, mensaje_original: str = '') -> str:
    """B2B retoma con continuar_leccion; sandbox conserva saludo con menú 1-2-3."""
    from .response_templates import get_response_for_intent

    if es_estudiante_b2b(estudiante):
        salir_seleccion_curso_legacy(estudiante)
        return get_response_for_intent(
            'continuar_leccion',
            nombre,
            estudiante_id=estudiante.id,
            mensaje_original=mensaje_original,
        )
    return get_response_for_intent('saludo', nombre, estudiante_id=estudiante.id)


def _texto_ayuda_b2b(nombre_usuario: str) -> str:
    return f"""🆘 ¿NECESITAS AYUDA, {nombre_usuario}?

Estoy aquí para apoyarte con tu aprendizaje.

Puedes preguntarme:
💬 Dudas sobre el contenido del curso
📊 Tu progreso escribiendo *progreso*
📖 Cómo seguir: escribe *listo*

También puedes:
• Escribir *corregir datos* para actualizar tu información
• Escribir *listo* para retomar tu lección

✍️ ¿En qué te puedo ayudar?"""
