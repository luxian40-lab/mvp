"""
Ritmo drip entre módulos: valor efectivo por estudiante/curso (curso + override por cliente).
"""
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from django.utils import timezone

if TYPE_CHECKING:
    from .models import Curso, Estudiante, ProgresoEstudiante


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


def drip_bloquea_siguiente_modulo(progreso: ProgresoEstudiante, modulo_actual) -> bool:
    """
    True si el módulo actual ya quedó completado pero aún no cumple la espera para el siguiente.
    Alineado con la lógica de views/response_templates al procesar 'listo'.
    """
    from .models import ModuloCompletado

    d = dias_espera_efectivos(progreso.estudiante, progreso.curso)
    if d <= 0 or modulo_actual is None:
        return False
    ya_completo = ModuloCompletado.objects.filter(
        progreso=progreso,
        modulo=modulo_actual,
    ).exists()
    if not ya_completo or not progreso.fecha_ultimo_avance:
        return False
    fecha_desbloqueo = fecha_desbloqueo_drip(progreso.fecha_ultimo_avance, d)
    if fecha_desbloqueo is None:
        return False
    return timezone.localdate() < fecha_desbloqueo
