# -*- coding: utf-8 -*-
"""Campos generales del módulo editables desde Module Builder (entrega, drip, examen)."""
from __future__ import annotations

from datetime import datetime

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from core.models import Modulo, SeccionModulo


def _parse_habilitado_desde(raw: str):
    raw = (raw or '').strip()
    if not raw:
        return None
    dt = parse_datetime(raw)
    if dt is None and 'T' in raw:
        try:
            dt = datetime.strptime(raw[:16], '%Y-%m-%dT%H:%M')
        except ValueError:
            return None
    if dt is None:
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def aplicar_titulo_modulo(modulo: Modulo, titulo: str) -> bool:
    titulo = (titulo or '').strip()
    if not titulo:
        return False
    modulo.titulo = titulo[:200]
    modulo.save(update_fields=['titulo'])
    return True


def aplicar_secciones_desde_post(modulo: Modulo, post) -> int:
    actualizadas = 0
    prefix = 'seccion_'
    suffix = '_titulo'
    for key in post:
        if not key.startswith(prefix) or not key.endswith(suffix):
            continue
        mid = key[len(prefix): -len(suffix)]
        if not mid.isdigit():
            continue
        nuevo = (post.get(key) or '').strip()
        if not nuevo:
            continue
        sec = SeccionModulo.objects.filter(pk=int(mid), modulo=modulo).first()
        if not sec:
            continue
        if sec.titulo != nuevo[:200]:
            sec.titulo = nuevo[:200]
            sec.save(update_fields=['titulo'])
            actualizadas += 1
    return actualizadas


def parsear_habilitado_desde(raw):
    """API pública: string datetime-local o ISO → aware datetime o None."""
    return _parse_habilitado_desde(raw)


def _debe_aplicar_calendario_desde_post(post) -> bool:
    """Solo tocar drip en guardado explícito del Builder, no en POST parciales."""
    if 'modulo_habilitado_desde' not in post:
        return False
    action = (post.get('action') or '').strip()
    if action in ('save_modulo', 'save_modulo_meta'):
        return True
    if post.get('persist_general') == '1':
        return True
    return False


def aplicar_config_general_desde_post(modulo: Modulo, post) -> list[str]:
    """Persiste campos «General y entrega» del Builder. Devuelve nombres de campos tocados."""
    touched: list[str] = []
    update_fields: list[str] = []

    descripcion = post.get('modulo_descripcion')
    if descripcion is not None:
        modulo.descripcion = descripcion
        update_fields.append('descripcion')
        touched.append('descripción')

    modo = post.get('modulo_modo_entrega')
    if modo is not None and modo in dict(Modulo.MODOS_ENTREGA):
        modulo.modo_entrega = modo
        update_fields.append('modo_entrega')
        touched.append('modo de entrega')

    if 'modulo_publicado_wa' in post:
        modulo.publicado_wa = post.get('modulo_publicado_wa') in ('1', 'on', 'true', 'True')
        update_fields.append('publicado_wa')
        touched.append('publicado WA')

    dur_raw = post.get('modulo_duracion_dias')
    if dur_raw is not None and str(dur_raw).strip().isdigit():
        modulo.duracion_dias = max(0, int(dur_raw))
        update_fields.append('duracion_dias')
        touched.append('duración')

    if _debe_aplicar_calendario_desde_post(post):
        raw_hab = post.get('modulo_habilitado_desde')
        parsed_hab = _parse_habilitado_desde(raw_hab)
        if (raw_hab or '').strip() and parsed_hab is None:
            raise ValueError(
                f'Fecha drip inválida: «{(raw_hab or "")[:40]}». '
                'Use el selector de fecha y hora del Builder.'
            )
        modulo.habilitado_desde = parsed_hab
        update_fields.append('habilitado_desde')
        touched.append('calendario')

    fac = post.get('modulo_facilitador_checkpoint')
    if fac is not None and fac in dict(Modulo._meta.get_field('facilitador_checkpoint').choices):
        modulo.facilitador_checkpoint = fac
        update_fields.append('facilitador_checkpoint')
        touched.append('checkpoint facilitadora')

    if 'modulo_examen_obligatorio' in post:
        modulo.examen_obligatorio = post.get('modulo_examen_obligatorio') in (
            '1',
            'on',
            'true',
            'True',
        )
        update_fields.append('examen_obligatorio')
        touched.append('examen')

    punt_raw = post.get('modulo_puntaje_minimo_aprobacion')
    if punt_raw is not None and str(punt_raw).strip().isdigit():
        modulo.puntaje_minimo_aprobacion = min(100, max(0, int(punt_raw)))
        update_fields.append('puntaje_minimo_aprobacion')
        touched.append('puntaje mínimo')

    if update_fields:
        modulo.save(update_fields=update_fields)
    return touched


def formato_habilitado_desde_input(val) -> str:
    if not val:
        return ''
    if timezone.is_naive(val):
        val = timezone.make_aware(val, timezone.get_current_timezone())
    local = timezone.localtime(val)
    return local.strftime('%Y-%m-%dT%H:%M')


def partes_habilitado_desde_input(val) -> tuple[str, str]:
    """Fecha y hora separadas para inputs type=date / type=time en el Builder."""
    combined = formato_habilitado_desde_input(val)
    if not combined or 'T' not in combined:
        return '', ''
    fecha, hora = combined.split('T', 1)
    return fecha, hora[:5] if hora else ''


def _paso_ids_en_post(post, solo_paso_id: int | None = None) -> set[int]:
    if solo_paso_id is not None:
        return {solo_paso_id}
    ids: set[int] = set()
    for key in post:
        if not key.startswith('paso_'):
            continue
        parts = key.split('_', 2)
        if len(parts) >= 2 and parts[1].isdigit():
            ids.add(int(parts[1]))
    return ids


def aplicar_pasos_desde_post(
    modulo: Modulo,
    post,
    *,
    solo_paso_id: int | None = None,
) -> int:
    """Persiste micros desde campos paso_<id>_*. Devuelve cantidad tocada."""
    from core.module_builder import actualizar_micro
    from core.models import PasoModulo

    guardados = 0
    for pid in sorted(_paso_ids_en_post(post, solo_paso_id)):
        paso = PasoModulo.objects.filter(pk=pid, modulo=modulo).first()
        if not paso:
            continue
        titulo = post.get(f'paso_{pid}_titulo')
        contenido = post.get(f'paso_{pid}_contenido')
        activo_key = f'paso_{pid}_activo'
        media_url_clear = post.get(f'paso_{pid}_clear_media') == '1'
        update_kwargs = {}
        if titulo is not None:
            update_kwargs['titulo'] = titulo
        if contenido is not None:
            update_kwargs['contenido'] = contenido
        if activo_key in post:
            activo_raw = post.get(activo_key)
            update_kwargs['activo'] = activo_raw in ('1', 'on', 'true', 'True')
        if update_kwargs:
            actualizar_micro(paso, **update_kwargs)
        if media_url_clear and (paso.media_url or '').strip():
            paso.media_url = ''
            paso.media_wa_apto = None
            paso.save(update_fields=['media_url', 'media_wa_apto'])
            from core.media_encode_async import limpiar_estado_encode_paso

            limpiar_estado_encode_paso(paso.pk)
        guardados += 1
    return guardados


def persistir_builder_desde_post(
    modulo: Modulo,
    post,
    *,
    solo_paso_id: int | None = None,
    require_titulo_modulo: bool = False,
    include_modulo_titulo: bool = True,
    include_secciones: bool = True,
    include_config_general: bool = True,
) -> list[str]:
    """
    Un solo punto de persistencia: módulo, secciones, general y micros.
    Subidas usan include_modulo_titulo=False para no pisar el nombre del módulo.
    replace_media además omite secciones (solo el paso subido).
    """
    partes: list[str] = []

    if include_modulo_titulo:
        titulo_mod = post.get('modulo_titulo')
        if titulo_mod is not None:
            titulo_mod = titulo_mod.strip()
            if not titulo_mod:
                if require_titulo_modulo:
                    raise ValueError('El nombre del módulo no puede quedar vacío.')
            else:
                aplicar_titulo_modulo(modulo, titulo_mod)
                partes.append('nombre')

    if include_secciones:
        n_sec = aplicar_secciones_desde_post(modulo, post)
        if n_sec:
            partes.append(f'{n_sec} sección(es)')

    if include_config_general:
        cfg = aplicar_config_general_desde_post(modulo, post)
        if cfg:
            if 'calendario' in cfg:
                partes.append('calendario')
            if any(x != 'calendario' for x in cfg):
                partes.append('configuración')

    n_pasos = aplicar_pasos_desde_post(modulo, post, solo_paso_id=solo_paso_id)
    if n_pasos:
        partes.append(f'{n_pasos} micro(s)')

    return partes

