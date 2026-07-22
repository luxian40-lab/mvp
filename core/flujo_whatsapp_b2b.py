"""
Flujo WhatsApp B2B: sin menú 1-2-3 global (progreso / cursos / ayuda).

Con un solo curso activo: avanza con *listo* (orden por campaña/catálogo).
Con varios cursos activos del mismo cliente: menú numerado para elegir cuál seguir.
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


def progresos_activos_qs(estudiante):
    """Progresos incompletos en cursos activos (mismo estudiante / cliente)."""
    from .models import ProgresoEstudiante

    return (
        ProgresoEstudiante.objects.filter(
            estudiante=estudiante,
            completado=False,
            curso__activo=True,
        )
        .select_related('curso', 'modulo_actual')
        .order_by('-fecha_inicio')
    )


def tiene_varios_cursos_activos(estudiante) -> bool:
    return progresos_activos_qs(estudiante).count() >= 2


def salir_seleccion_curso_legacy(estudiante) -> None:
    """Sale del estado de lista numerada de cursos."""
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


def armar_menu_seleccion_cursos(estudiante, prefijo: str = '') -> str:
    """
    Menú numerado cuando el B2B tiene 2+ progresos activos.
    Deja al estudiante en esperando_seleccion_curso para que el dígito elija curso.
    """
    progresos = list(progresos_activos_qs(estudiante))
    if len(progresos) < 2:
        return mensaje_curso_por_campana(estudiante)

    org = estudiante.cliente.nombre if estudiante.cliente else 'tu organización'
    partes = []
    if prefijo:
        partes.append(prefijo.rstrip())
    else:
        partes.append(f"📚 Tienes varios cursos activos en *{org}*:")

    lineas = [partes[0], '']
    for idx, prog in enumerate(progresos, 1):
        emoji = (prog.curso.emoji or '📚').strip()
        porcentaje = prog.porcentaje_avance()
        lineas.append(f"{idx}️⃣ {emoji} {prog.curso.nombre}")
        lineas.append(f"   📊 Avance: {porcentaje}%")
        if prog.modulo_actual:
            lineas.append(
                f"   📖 Módulo actual: {prog.modulo_actual.numero} - {prog.modulo_actual.titulo}"
            )
        lineas.append('')

    lineas.append("Escribe el *número* del curso que quieres seguir (ej.: *1* o *2*).")
    lineas.append("También puedes escribir *listo* y luego elegir, o *progreso* / *ayuda*.")

    estudiante.estado_onboarding = 'esperando_seleccion_curso'
    ctx = dict(estudiante.contexto_temporal or {})
    ctx['tipo'] = 'seleccion_curso'
    ctx.pop('curso_activo_id', None)
    estudiante.contexto_temporal = ctx
    estudiante.save(update_fields=['estado_onboarding', 'contexto_temporal'])

    return '\n'.join(lineas)


def texto_ayuda_comandos(estudiante) -> str:
    nombre = (getattr(estudiante, 'nombre', '') or 'estudiante').split()[0]
    base = (
        f"Hola {nombre}.\n\n"
        "📚 *listo* — continuar tu lección\n"
        "📊 *progreso* — ver tu avance\n"
        "✏️ *corregir datos* — actualizar nombre, municipio o cédula\n"
        "🆘 *ayuda* — soporte\n"
        "🖥️ *aula* — enlace al aula web"
    )
    if tiene_varios_cursos_activos(estudiante):
        base += "\n📖 *cursos* — elegir entre tus cursos activos"
    return base


def resolver_progreso_b2b(estudiante):
    """Progreso activo según campaña / catálogo (solo cuando hay un curso claro)."""
    from .selector_curso import asegurar_inscripcion_catalogo_cliente

    if not es_estudiante_b2b(estudiante):
        return None
    if tiene_varios_cursos_activos(estudiante):
        return None
    return asegurar_inscripcion_catalogo_cliente(estudiante)


def mensaje_curso_por_campana(estudiante) -> str:
    from .selector_curso import asegurar_inscripcion_catalogo_cliente

    if tiene_varios_cursos_activos(estudiante):
        return armar_menu_seleccion_cursos(estudiante)

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
    """Cuando un B2B con un solo curso escribe 1/2/3 sin menú de selección."""
    if tiene_varios_cursos_activos(estudiante):
        return armar_menu_seleccion_cursos(estudiante)
    base = mensaje_curso_por_campana(estudiante)
    return f"{base}\n\n_Tip: no hace falta elegir con números; escribe *listo* para seguir._"


def respuesta_b2b_sin_menu(estudiante, intent: str, nombre_usuario: str, kwargs: dict[str, Any]) -> str | None:
    """Intercepta intents de menú/lista para estudiantes con cliente (B2B)."""
    if not es_estudiante_b2b(estudiante):
        return None

    # Varios cursos: menú de elección (no el tip “sin números”)
    if tiene_varios_cursos_activos(estudiante):
        if intent in INTENTS_SIN_MENU_NUMERADO - {'opcion_numerica'}:
            return armar_menu_seleccion_cursos(estudiante)
        if intent == 'opcion_numerica':
            # Dejar que continuar_curso_seleccionado / estado de selección manejen el dígito
            return None
        if intent == 'opcion_3':
            return _texto_ayuda_b2b(nombre_usuario)
        if intent == 'numero_invalido':
            return armar_menu_seleccion_cursos(estudiante)
        if intent == 'saludo':
            return None
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
    """B2B retoma con continuar_leccion (menú si hay varios cursos); sandbox saludo 1-2-3."""
    from .response_templates import get_response_for_intent

    if es_estudiante_b2b(estudiante):
        if tiene_varios_cursos_activos(estudiante):
            return armar_menu_seleccion_cursos(
                estudiante,
                prefijo=f"🌱 Hola {nombre.split()[0] if nombre else 'estudiante'}.",
            )
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
• Escribir *cursos* si tienes más de un curso activo

✍️ ¿En qué te puedo ayudar?"""
