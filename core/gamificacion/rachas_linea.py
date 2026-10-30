"""Racha diaria de la línea Meta.

Un día cuenta si la persona escribió algo (curso, asesor o menú). La racha y las
insignias no se mandan como mensaje propio: quedan en aviso_pendiente y
sandbox_canal las antepone a la siguiente respuesta.

Si el número es Estudiante, la racha es la de PerfilGamificacion y los hitos son
los Badge tipo RACHA activos del admin. Los contadores de SandboxCanalSesion solo
sirven de puerta "una vez al día" y de respaldo para números sin Estudiante.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from django.db import transaction
from django.db.models import F
from django.utils import timezone

logger = logging.getLogger(__name__)


def texto_racha(dias: int) -> str:
    return f"🔥 Racha: {dias} días seguidos aprendiendo con eki"


def _texto_insignia(badge) -> str:
    return f"Nueva insignia: *{badge.nombre}*"


def _texto_proxima_insignia(dias: int) -> str:
    from core.gamificacion import Badge

    badge = (
        Badge.objects.filter(tipo='RACHA', activo=True, es_secreto=False, valor_requerido__gt=dias)
        .order_by('valor_requerido')
        .first()
    )
    if badge is None:
        return ''
    faltan = badge.valor_requerido - dias
    return f"Próxima insignia: {badge.nombre} (faltan {faltan} {'día' if faltan == 1 else 'días'})"


def agregar_aviso(telefono: str, linea: str) -> None:
    """Suma una línea al aviso pendiente (sin crear sesión si no existe)."""
    from core.models import SandboxCanalSesion
    from core.sandbox_canal import sandbox_via_meta

    linea = (linea or '').strip()
    if not telefono or not linea or not sandbox_via_meta():
        return
    fila = SandboxCanalSesion.objects.filter(telefono=telefono).only('aviso_pendiente').first()
    if fila is None or linea in (fila.aviso_pendiente or ''):
        return
    nuevo = f"{fila.aviso_pendiente}\n{linea}".strip() if fila.aviso_pendiente else linea
    SandboxCanalSesion.objects.filter(pk=fila.pk).update(aviso_pendiente=nuevo[:300])


def tomar_aviso_pendiente(telefono: str) -> str:
    """Devuelve y limpia el aviso; si dos envíos compiten, solo uno lo lleva."""
    from core.models import SandboxCanalSesion

    fila = (
        SandboxCanalSesion.objects.filter(telefono=telefono)
        .exclude(aviso_pendiente='')
        .values_list('pk', 'aviso_pendiente')
        .first()
    )
    if not fila:
        return ''
    pk, aviso = fila
    tomado = SandboxCanalSesion.objects.filter(pk=pk, aviso_pendiente=aviso).update(aviso_pendiente='')
    return aviso if tomado else ''


def _racha_del_perfil(telefono: str):
    """(días, badges nuevos) desde PerfilGamificacion, o None si no hay Estudiante."""
    from core.gamificacion import PerfilGamificacion
    from core.models import Estudiante

    est = Estudiante.objects.filter(telefono=telefono).order_by('id').first()
    if est is None:
        return None
    with transaction.atomic():
        perfil, _ = PerfilGamificacion.objects.get_or_create(estudiante=est)
        perfil = PerfilGamificacion.objects.select_for_update().get(pk=perfil.pk)
        perfil.actualizar_racha()
    return perfil.racha_dias_actual, list(getattr(perfil, 'badges_racha_nuevos', []))


def registrar_actividad_linea(telefono: str) -> int | None:
    """
    Marca el día como activo. Devuelve la racha nueva si este mensaje abrió el día,
    None si ya había actividad hoy.
    """
    from core.models import SandboxCanalSesion

    if not telefono:
        return None
    hoy = timezone.localdate()
    ayer = hoy - timedelta(days=1)
    seguidos = SandboxCanalSesion.objects.filter(telefono=telefono, racha_ultimo_dia=ayer).update(
        racha_actual=F('racha_actual') + 1, racha_ultimo_dia=hoy
    )
    if not seguidos:
        reiniciados = (
            SandboxCanalSesion.objects.filter(telefono=telefono)
            .exclude(racha_ultimo_dia=hoy)
            .update(racha_actual=1, racha_ultimo_dia=hoy)
        )
        if not reiniciados:
            return None
    fila = SandboxCanalSesion.objects.filter(telefono=telefono).values('pk', 'racha_actual', 'racha_maxima').first()
    if not fila:
        return None
    dias = fila['racha_actual']
    nuevos = []
    try:
        del_perfil = _racha_del_perfil(telefono)
    except Exception:
        logger.exception('racha_linea_perfil_fail tel=%s', telefono)
        del_perfil = None
    if del_perfil is not None:
        dias, nuevos = del_perfil
    SandboxCanalSesion.objects.filter(pk=fila['pk']).update(
        racha_actual=dias, racha_maxima=max(dias, fila['racha_maxima'])
    )

    lineas: list[str] = []
    if dias >= 2:
        lineas.append(texto_racha(dias))
    lineas.extend(_texto_insignia(b) for b in nuevos)
    if dias >= 2 and not nuevos:
        try:
            proxima = _texto_proxima_insignia(dias)
        except Exception:
            proxima = ''
        if proxima:
            lineas.append(proxima)
    for linea in lineas:
        agregar_aviso(telefono, linea)
    return dias
