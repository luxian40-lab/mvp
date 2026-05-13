"""
Ritmo drip entre módulos: días de espera (curso + override por cliente)
y calendario por módulo (global en Modulo o por cliente en HabilitacionModuloDripCliente).
"""
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from django.utils import timezone

if TYPE_CHECKING:
    from .models import Curso, Estudiante, Modulo, ProgresoEstudiante


def dias_espera_efectivos(estudiante: Estudiante | None, curso: Curso | None) -> int:
    """
    Días de espera obligatorios entre módulos para este par estudiante-curso.
    Sin estudiante o sin cliente: solo aplica la configuración del curso.
    """
    if curso is None:
        return 0
    base = max(0, int(curso.dias_espera_entre_modulos or 0))
    if estudiante is None or not getattr(estudiante, 'cliente_id', None):
        return base
    from .models import ConfiguracionDripCliente

    cfg = (
        ConfiguracionDripCliente.objects.filter(
            cliente_id=estudiante.cliente_id,
            curso_id=curso.id,
            activo=True,
        )
        .only('dias_espera_entre_modulos')
        .first()
    )
    if cfg is None or cfg.dias_espera_entre_modulos is None:
        return base
    return max(0, int(cfg.dias_espera_entre_modulos))


def fecha_desbloqueo_drip(fecha_ultimo_avance, dias_espera: int):
    """
    Fecha calendario en que se desbloquea el siguiente módulo.
    Regla de negocio: el desbloqueo es por día (no por hora exacta).
    """
    if not fecha_ultimo_avance or dias_espera <= 0:
        return None
    return timezone.localdate(fecha_ultimo_avance) + timedelta(days=dias_espera)


def _siguiente_modulo_orden(curso, modulo_actual) -> Modulo | None:
    if modulo_actual is None or curso is None:
        return None
    return (
        curso.modulos.filter(numero__gt=modulo_actual.numero)
        .order_by('numero')
        .first()
    )


def habilitado_desde_efectivo(estudiante: Estudiante | None, modulo: Modulo | None):
    """
    datetime a partir del cual el módulo puede enviarse, o None = sin restricción de calendario.
    Prioridad: fila activa (cliente × curso × módulo) → Modulo.habilitado_desde.
    """
    if modulo is None:
        return None
    curso_id = modulo.curso_id
    if estudiante is not None and getattr(estudiante, 'cliente_id', None):
        from .models import HabilitacionModuloDripCliente

        row = (
            HabilitacionModuloDripCliente.objects.filter(
                cliente_id=estudiante.cliente_id,
                curso_id=curso_id,
                modulo_id=modulo.id,
                activo=True,
            )
            .only('habilitado_desde')
            .first()
        )
        if row is not None and row.habilitado_desde:
            return row.habilitado_desde
    return getattr(modulo, 'habilitado_desde', None) or None


def calendario_bloquea_modulo(estudiante: Estudiante | None, modulo: Modulo | None) -> bool:
    """True si aún no se cumple la fecha/hora de habilitación del módulo."""
    dt = habilitado_desde_efectivo(estudiante, modulo)
    if not dt:
        return False
    return timezone.now() < dt


def format_mensaje_bloqueo_drip(fecha_desbloqueo) -> str:
    """Mensaje WhatsApp: espera por días entre módulos (mismo tono que el drip histórico)."""
    if hasattr(fecha_desbloqueo, 'hour'):
        f_txt = timezone.localtime(fecha_desbloqueo).strftime('%d/%m/%Y')
    else:
        f_txt = fecha_desbloqueo.strftime('%d/%m/%Y')
    return (
        '🌱 *¡Excelente energía!*\n\n'
        'Estamos preparando tu siguiente sesión; aún no enviamos el siguiente módulo para que puedas asimilar lo aprendido.\n\n'
        f'Tu próxima lección se desbloquea el *{f_txt}*.\n'
        'Mientras tanto, repasa el material del módulo que acabas de completar.\n\n'
        'Cuando llegue esa fecha, responde *listo* y seguimos automáticamente.'
    )


def format_mensaje_bloqueo_calendario_modulo(habilitado_desde) -> str:
    """Mismo tono que el drip por días; la fecha incluye hora (calendario programado)."""
    f_txt = timezone.localtime(habilitado_desde).strftime('%d/%m/%Y a las %H:%M')
    return (
        '🌱 *¡Excelente energía!*\n\n'
        'Estamos preparando tu siguiente sesión; aún no enviamos el siguiente módulo para que puedas asimilar lo aprendido.\n\n'
        f'Tu próxima lección se desbloquea el *{f_txt}*.\n'
        'Mientras tanto, repasa el material del módulo que acabas de completar.\n\n'
        'Cuando llegue esa fecha, responde *listo* y seguimos automáticamente.'
    )


def mensaje_bloqueo_avance_siguiente_modulo(
    estudiante: Estudiante | None,
    progreso: ProgresoEstudiante,
    modulo_actual,
) -> str | None:
    """
    None = puede abrir el siguiente módulo (respecto a drip por días + calendario).
    Si aplica bloqueo, devuelve uno o dos párrafos (drip y/o calendario).
    Requiere que el módulo actual esté marcado como completado en ModuloCompletado.
    """
    from .models import ModuloCompletado

    if modulo_actual is None or progreso is None or progreso.curso_id is None:
        return None
    siguiente = _siguiente_modulo_orden(progreso.curso, modulo_actual)
    if siguiente is None:
        return None
    if not ModuloCompletado.objects.filter(
        progreso=progreso, modulo=modulo_actual
    ).exists():
        return None

    partes: list[str] = []
    d = dias_espera_efectivos(estudiante, progreso.curso)
    if d > 0 and progreso.fecha_ultimo_avance:
        fecha_desbloqueo = fecha_desbloqueo_drip(progreso.fecha_ultimo_avance, d)
        if fecha_desbloqueo and timezone.localdate() < fecha_desbloqueo:
            partes.append(format_mensaje_bloqueo_drip(fecha_desbloqueo))

    cal_dt = habilitado_desde_efectivo(estudiante, siguiente)
    if cal_dt and timezone.now() < cal_dt:
        partes.append(format_mensaje_bloqueo_calendario_modulo(cal_dt))

    if not partes:
        return None
    return '\n\n'.join(partes)


def drip_bloquea_siguiente_modulo(progreso: ProgresoEstudiante, modulo_actual) -> bool:
    """
    True si el módulo actual ya quedó completado pero aún no se puede abrir el siguiente:
    por días de espera y/o por fecha programada del siguiente módulo.
    """
    return bool(
        mensaje_bloqueo_avance_siguiente_modulo(
            progreso.estudiante if progreso else None,
            progreso,
            modulo_actual,
        )
    )
