"""Sesión de menú por línea. El mismo teléfono no mezcla la 1 con la 2."""
from __future__ import annotations


def phone_id_sesion() -> str:
    from core.sandbox_canal import phone_id_de_salida

    return (phone_id_de_salida() or '').strip()


def sesion_de(telefono: str, **defaults):
    """Fila de esta línea. Si solo hay la histórica sin phone_id, la adopta la principal."""
    from core.models import SandboxCanalSesion
    from core.sandbox_canal import sandbox_phone_id

    tel = (telefono or '').strip()
    if not tel:
        raise ValueError('sin telefono')
    phone_id = phone_id_sesion()
    found = SandboxCanalSesion.objects.filter(telefono=tel, phone_id=phone_id).first()
    if found:
        return found
    principal = sandbox_phone_id()
    if phone_id and phone_id == principal:
        legacy = SandboxCanalSesion.objects.filter(telefono=tel, phone_id='').first()
        if legacy:
            legacy.phone_id = phone_id
            legacy.save(update_fields=['phone_id'])
            return legacy
    datos = {'modo': 'menu'}
    datos.update(defaults)
    sesion, _ = SandboxCanalSesion.objects.get_or_create(
        telefono=tel,
        phone_id=phone_id,
        defaults=datos,
    )
    return sesion
