# -*- coding: utf-8 -*-
"""Module Builder WA — lógica de estructura (sin envío WhatsApp)."""
from __future__ import annotations

from django.conf import settings
from django.db import transaction
from django.db.models import Max

from .models import PasoModulo, SeccionModulo
from .module_structure import detectar_secciones_intercaladas, mensaje_error_intercalado


def module_builder_habilitado(request=None) -> bool:
    """
    Flag opt-in. settings.EKI_MODULE_BUILDER_BETA (DEBUG→True local).
    Superusuario puede forzar con ?builder=1 si el flag está OFF.
    """
    if getattr(settings, 'EKI_MODULE_BUILDER_BETA', False):
        return True
    if request is not None:
        user = getattr(request, 'user', None)
        if user and user.is_authenticated and getattr(user, 'is_superuser', False):
            if request.GET.get('builder') == '1' or request.POST.get('builder') == '1':
                return True
    return False


def media_preview_kind(url: str) -> str:
    """Clasifica URL para miniatura en el builder: image|video|file|text."""
    u = (url or '').strip().lower().split('?', 1)[0]
    if not u:
        return 'text'
    if u.endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif')):
        return 'image'
    if u.endswith(('.mp4', '.m4v', '.mov', '.webm')):
        return 'video'
    return 'file'


def arbol_modulo(modulo) -> tuple[list[dict], list]:
    """Árbol secciones → micros para la UI builder."""
    secciones = list(
        SeccionModulo.objects.filter(modulo=modulo, activa=True).order_by('orden', 'id')
    )
    pasos = list(
        PasoModulo.objects.filter(modulo=modulo, activo=True)
        .select_related('seccion')
        .order_by('orden', 'id')
    )
    by_sec: dict[int, list] = {s.id: [] for s in secciones}
    huerfanos = []
    for p in pasos:
        p.preview_kind = media_preview_kind(p.media_url or '')
        if p.seccion_id in by_sec:
            by_sec[p.seccion_id].append(p)
        else:
            huerfanos.append(p)
    out = []
    for s in secciones:
        micros = by_sec.get(s.id) or []
        out.append(
            {
                'seccion': s,
                'n_micros': len(micros),
                'micros': micros,
            }
        )
    return out, huerfanos


def agregar_seccion(modulo, titulo: str = '') -> SeccionModulo:
    max_o = (
        SeccionModulo.objects.filter(modulo=modulo).aggregate(m=Max('orden')).get('m') or 0
    )
    return SeccionModulo.objects.create(
        modulo=modulo,
        orden=max_o + 1,
        titulo=(titulo or '').strip() or f'Bloque {max_o + 1}',
        activa=True,
    )


def _renumerar_pasos(pasos_en_orden: list[PasoModulo]) -> None:
    """Asigna orden 1..n respetando UniqueConstraint."""
    if not pasos_en_orden:
        return
    with transaction.atomic():
        base = (
            PasoModulo.objects.filter(modulo_id=pasos_en_orden[0].modulo_id)
            .aggregate(m=Max('orden'))
            .get('m')
            or 0
        ) + 1000
        for i, p in enumerate(pasos_en_orden):
            PasoModulo.objects.filter(pk=p.pk).update(orden=base + i)
        for i, p in enumerate(pasos_en_orden, start=1):
            PasoModulo.objects.filter(pk=p.pk).update(orden=i)


def agregar_micro(
    modulo,
    seccion: SeccionModulo,
    *,
    titulo: str = '',
    contenido: str = '',
    media_url: str = '',
    media_wa_apto=None,
    activo: bool = True,
) -> PasoModulo:
    """Inserta un micro al final de la sección (mantiene bloques contiguos)."""
    if seccion.modulo_id != modulo.id:
        raise ValueError('La sección no pertenece al módulo')
    with transaction.atomic():
        pasos = list(
            PasoModulo.objects.filter(modulo=modulo)
            .select_related('seccion')
            .order_by('orden', 'id')
        )
        nuevo = PasoModulo(
            modulo=modulo,
            seccion=seccion,
            orden=999999,
            titulo=(titulo or '').strip()[:200],
            contenido=(contenido or '').strip(),
            media_url=(media_url or '').strip(),
            media_wa_apto=media_wa_apto,
            activo=activo,
            tipo=PasoModulo.TIPO_CONTENIDO,
            requiere_listo_para_avanzar=True,
        )
        insert_at = len(pasos)
        last_of_sec = None
        for i, p in enumerate(pasos):
            if p.seccion_id == seccion.id:
                last_of_sec = i
        if last_of_sec is not None:
            insert_at = last_of_sec + 1
        else:
            insert_at = 0
            for i, p in enumerate(pasos):
                so = getattr(p.seccion, 'orden', 0) or 0
                if so < (seccion.orden or 0):
                    insert_at = i + 1
        pasos.insert(insert_at, nuevo)
        # Guardar nuevo + renumerar
        base = (PasoModulo.objects.filter(modulo=modulo).aggregate(m=Max('orden')).get('m') or 0) + 1000
        for i, p in enumerate(pasos):
            p.orden = base + i
            if p.pk:
                PasoModulo.objects.filter(pk=p.pk).update(orden=p.orden)
            else:
                p.save()
        for i, p in enumerate(pasos, start=1):
            PasoModulo.objects.filter(pk=p.pk).update(orden=i)
            p.orden = i
        hall = detectar_secciones_intercaladas(
            list(PasoModulo.objects.filter(modulo=modulo, activo=True).order_by('orden', 'id'))
        )
        if hall:
            raise ValueError(mensaje_error_intercalado(hall))
        return nuevo


def mover_micro(paso: PasoModulo, direction: str) -> bool:
    from .orden_bloques import intercambiar_orden

    ok = intercambiar_orden(paso, direction)
    if not ok:
        return False
    hall = detectar_secciones_intercaladas(
        list(
            PasoModulo.objects.filter(modulo_id=paso.modulo_id, activo=True).order_by(
                'orden', 'id'
            )
        )
    )
    if hall:
        # revert
        intercambiar_orden(paso, 'down' if direction == 'up' else 'up')
        raise ValueError(mensaje_error_intercalado(hall))
    return True


def reordenar_micros_en_seccion(modulo, seccion: SeccionModulo, paso_ids: list[int]) -> None:
    """
    Reordena micros solo dentro de su sección (riel anti-intercalado).
    paso_ids = orden nuevo de los activos de esa sección; deben coincidir en set.
    """
    if seccion.modulo_id != modulo.id:
        raise ValueError('La sección no pertenece al módulo')
    ids = [int(x) for x in paso_ids]
    actuales = list(
        PasoModulo.objects.filter(
            modulo=modulo, seccion=seccion, activo=True
        ).order_by('orden', 'id')
    )
    actual_ids = [p.id for p in actuales]
    if sorted(ids) != sorted(actual_ids):
        raise ValueError('El orden de micros no coincide con los de esta sección.')
    by_id = {p.id: p for p in actuales}
    nuevos_bloque = [by_id[i] for i in ids]

    with transaction.atomic():
        secciones = list(
            SeccionModulo.objects.filter(modulo=modulo, activa=True).order_by('orden', 'id')
        )
        pasos_otros = {
            s.id: list(
                PasoModulo.objects.filter(modulo=modulo, seccion=s, activo=True).order_by(
                    'orden', 'id'
                )
            )
            for s in secciones
            if s.id != seccion.id
        }
        secuencia: list[PasoModulo] = []
        for s in secciones:
            if s.id == seccion.id:
                secuencia.extend(nuevos_bloque)
            else:
                secuencia.extend(pasos_otros.get(s.id) or [])
        # Incluir inactivos al final sin romper UniqueConstraint
        inactivos = list(
            PasoModulo.objects.filter(modulo=modulo, activo=False).order_by('orden', 'id')
        )
        _renumerar_pasos(secuencia + inactivos)
        hall = detectar_secciones_intercaladas(
            list(
                PasoModulo.objects.filter(modulo=modulo, activo=True).order_by('orden', 'id')
            )
        )
        if hall:
            raise ValueError(mensaje_error_intercalado(hall))


def reordenar_secciones(modulo, seccion_ids: list[int]) -> None:
    """Reordena secciones activas; los micros de cada una viajan juntos (riel)."""
    ids = [int(x) for x in seccion_ids]
    secciones = list(
        SeccionModulo.objects.filter(modulo=modulo, activa=True).order_by('orden', 'id')
    )
    actual_ids = [s.id for s in secciones]
    if sorted(ids) != sorted(actual_ids):
        raise ValueError('El orden de secciones no coincide con las activas del módulo.')
    by_id = {s.id: s for s in secciones}
    ordenadas = [by_id[i] for i in ids]

    with transaction.atomic():
        base = (
            SeccionModulo.objects.filter(modulo=modulo).aggregate(m=Max('orden')).get('m')
            or 0
        ) + 1000
        for i, s in enumerate(ordenadas):
            SeccionModulo.objects.filter(pk=s.pk).update(orden=base + i)
        for i, s in enumerate(ordenadas, start=1):
            SeccionModulo.objects.filter(pk=s.pk).update(orden=i)
            s.orden = i

        secuencia: list[PasoModulo] = []
        for s in ordenadas:
            secuencia.extend(
                list(
                    PasoModulo.objects.filter(
                        modulo=modulo, seccion=s, activo=True
                    ).order_by('orden', 'id')
                )
            )
        inactivos = list(
            PasoModulo.objects.filter(modulo=modulo, activo=False).order_by('orden', 'id')
        )
        _renumerar_pasos(secuencia + inactivos)
        hall = detectar_secciones_intercaladas(
            list(
                PasoModulo.objects.filter(modulo=modulo, activo=True).order_by('orden', 'id')
            )
        )
        if hall:
            raise ValueError(mensaje_error_intercalado(hall))


def desactivar_micro(paso: PasoModulo) -> None:
    paso.activo = False
    paso.save(update_fields=['activo'])


def diagnostico_estructura(modulo) -> dict:
    activos = list(
        PasoModulo.objects.filter(modulo=modulo, activo=True).order_by('orden', 'id')
    )
    hall = detectar_secciones_intercaladas(activos)
    return {
        'intercalado': bool(hall),
        'hallazgos': hall,
        'mensaje': mensaje_error_intercalado(hall) if hall else '',
        'n_secciones': SeccionModulo.objects.filter(modulo=modulo, activa=True).count(),
        'n_micros': len(activos),
    }
