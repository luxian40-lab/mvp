"""Interruptor del alta nueva de Estudiante. Apagado por defecto."""
import os


def alta_v2_activa() -> bool:
    """True solo con ADMIN_ESTUDIANTE_ALTA_V2 en settings o en el entorno.

    Sin setting y sin variable, queda el formulario anterior.
    """
    from django.conf import settings

    if hasattr(settings, 'ADMIN_ESTUDIANTE_ALTA_V2'):
        return bool(settings.ADMIN_ESTUDIANTE_ALTA_V2)
    raw = os.environ.get('ADMIN_ESTUDIANTE_ALTA_V2', '')
    return raw.strip().lower() in ('1', 'true', 'yes', 'on')
