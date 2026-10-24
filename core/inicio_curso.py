"""Primera entrega de un curso: saludo de Formador y Compañero, y el módulo 1.

Solo la inscripción desde el carrusel deja el saludo pendiente. Quien ya iba
en el curso antes no tiene la marca y su «listo» avanza como siempre.
Confirmar los datos y pulsar continuar en el carrusel dejan la misma marca de entregado.
El módulo 1 no se cierra en ese turno.
"""
from __future__ import annotations

MARCA = 'inicio_curso_id'
PENDIENTE = 'inicio_pendiente_curso_id'


def inicio_ya_entregado(estudiante, curso_id: int) -> bool:
    ctx = getattr(estudiante, 'contexto_temporal', None) or {}
    return ctx.get(MARCA) == curso_id


def inicio_pendiente(estudiante, curso_id: int) -> bool:
    ctx = getattr(estudiante, 'contexto_temporal', None) or {}
    return ctx.get(PENDIENTE) == curso_id


def marcar_inicio_pendiente(ctx: dict, curso_id: int) -> dict:
    """Sobre el contexto que ya se va a guardar; no hace save."""
    ctx[PENDIENTE] = curso_id
    return ctx


def marcar_inicio_entregado(estudiante, curso_id: int) -> None:
    estudiante.refresh_from_db(fields=['contexto_temporal'])
    ctx = dict(estudiante.contexto_temporal or {})
    if ctx.get(MARCA) == curso_id and ctx.get(PENDIENTE) != curso_id:
        return
    ctx[MARCA] = curso_id
    if ctx.get(PENDIENTE) == curso_id:
        ctx.pop(PENDIENTE)
    estudiante.contexto_temporal = ctx
    estudiante.save(update_fields=['contexto_temporal'])


def falta_primera_entrega(estudiante, progreso, modulo) -> bool:
    """Inscrito desde el carrusel, todavía en el módulo 1, sin haberlo mostrado."""
    if modulo is None or progreso is None:
        return False
    if not inicio_pendiente(estudiante, progreso.curso_id):
        return False
    if inicio_ya_entregado(estudiante, progreso.curso_id):
        return False
    from core.models import ModuloCompletado

    if ModuloCompletado.objects.filter(progreso=progreso).exists():
        return False
    primero = progreso.curso.modulos.order_by('numero').values_list('numero', flat=True).first()
    if primero is None or modulo.numero != primero:
        return False
    return (progreso.paso_actual_modulo or 1) <= 1


def mensaje_primera_entrega(estudiante, progreso, modulo) -> str:
    """Saludo y el módulo actual. No marca el módulo como completado."""
    from core.tutor_ia_modulo import generar_presentacion_agentes

    nombre = getattr(estudiante, 'nombre', None) or 'Estudiante'
    msg_tutor, msg_asistente = generar_presentacion_agentes(
        modulo.curso.nombre,
        estudiante_nombre=nombre,
        nombre_tutor='Formador',
        nombre_asistente='Compañero',
        curso=modulo.curso,
    )
    partes = [msg_tutor, msg_asistente]
    cliente = getattr(estudiante, 'cliente', None)
    usar_puntos = bool(getattr(cliente, 'usar_gamificacion', True)) if cliente is not None else True
    if usar_puntos:
        partes.append(
            '*Nuestra experiencia de formación funciona a través de puntos*\n\n'
            'A medida que avance en el curso, tendrá retos que evaluar.\n\n'
            '¡Vamos a aprender y avanzar juntos!'
        )
    partes.append('*Comenzamos con el primer módulo de su curso...*')
    partes.extend(_partes_del_modulo(progreso, modulo))
    marcar_inicio_entregado(estudiante, progreso.curso_id)
    return '[MULTI_MSG]' + '[SEP]'.join(p for p in partes if p)


def _partes_del_modulo(progreso, modulo) -> list[str]:
    from core.module_steps import (
        entregar_bloque_secciones_desde_paso,
        modulo_usa_pasos,
        pasos_activos_qs,
        reset_progreso_pasos_modulo,
        texto_legacy_whatsapp,
    )

    if modulo_usa_pasos(modulo) and pasos_activos_qs(modulo).exists():
        reset_progreso_pasos_modulo(progreso, save=True)
        bloque = entregar_bloque_secciones_desde_paso(progreso, modulo, 1) or ''
        bruto = bloque[len('[MULTI_MSG]'):] if bloque.startswith('[MULTI_MSG]') else bloque
        return [p for p in bruto.split('[SEP]') if p]
    titulo = f"📖 *Módulo {modulo.numero}: {modulo.titulo}*"
    cuerpo = (texto_legacy_whatsapp(modulo) or (modulo.descripcion or '')).strip()
    texto = f"{titulo}\n\n{cuerpo}" if cuerpo else titulo
    return [texto]
