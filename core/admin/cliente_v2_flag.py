"""Interruptor del admin nuevo de Cliente. Apagado por defecto."""
import os


def admin_clientes_v2_activo() -> bool:
    """True solo con ADMIN_CLIENTES_V2=1 (entorno) o el setting del mismo nombre.

    El setting gana si existe (los tests lo fijan con override_settings).
    Sin setting y sin variable, queda el ModelAdmin anterior.
    """
    from django.conf import settings

    try:
        valor = settings.ADMIN_CLIENTES_V2
    except AttributeError:
        valor = None
    if valor is not None:
        return bool(valor)
    raw = os.environ.get('ADMIN_CLIENTES_V2', '')
    return raw.strip().lower() in ('1', 'true', 'yes', 'on')
