# -*- coding: utf-8 -*-
"""Lecturas del Module Builder. No guarda y no envía WhatsApp."""
from __future__ import annotations

from django.db.models import Q
from django.utils import timezone

from core.media_upload_servicio import topes_bytes


def texto_topes() -> str:
    t = topes_bytes()
    return (
        f'Video máx. {t["video"] // (1024 * 1024)} MB, '
        f'imagen {t["imagen"] // (1024 * 1024)} MB, '
        f'audio {t["audio"] // (1024 * 1024)} MB. '
        'H.264 Main y AAC.'
    )


def _motivo_omision(paso) -> str:
    from core.media_encode_async import estado_encode_paso
    from core.modulo_publicacion import detalle_problema_media_paso

    url = (getattr(paso, 'media_url', None) or '').strip()
    if not url:
        return ''
    if getattr(paso, 'pk', None):
        enc = estado_encode_paso(paso.pk, paso=paso) or {}
        if enc.get('status') in ('pending', 'running'):
            return 'El archivo se está preparando. Se envía solo el texto.'
    if getattr(paso, 'media_wa_apto', None) is False:
        prob = detalle_problema_media_paso(paso)
        detalle = (prob or {}).get('detalle') or 'El archivo no es apto para WhatsApp.'
        return f'{detalle} Se envía solo el texto. {texto_topes()}'
    return ''


def entrega_real_paso(paso) -> dict:
    """La misma decisión que partes_mensaje_paso: si el archivo sale o se omite."""
    from core.module_steps import partes_mensaje_paso

    url = (getattr(paso, 'media_url', None) or '').strip()
    texto = (getattr(paso, 'contenido', None) or '').strip()
    motivo = _motivo_omision(paso)
    omite = bool(url and motivo)
    partes = partes_mensaje_paso(paso, getattr(getattr(paso, 'modulo', None), 'curso', None))
    return {
        'id': paso.pk,
        'orden': getattr(paso, 'orden', None),
        'activo': bool(getattr(paso, 'activo', True)),
        'texto': texto,
        'tiene_archivo': bool(url) and not omite,
        'omite_archivo': omite,
        'motivo': motivo,
        'mixto': bool(url and texto),
        'partes': len([p for p in partes if p and not str(p).startswith('[DELAY')]),
    }


def recepcion_secciones(arbol) -> list[dict]:
    salida = []
    for bloque in arbol:
        sec = bloque['seccion']
        mensajes = []
        for paso in bloque.get('micros') or []:
            fila = entrega_real_paso(paso)
            fila['seccion_id'] = sec.pk
            mensajes.append(fila)
        salida.append({
            'seccion_id': sec.pk,
            'titulo': sec.titulo,
            'mensajes': mensajes,
        })
    return salida


def avisos_antes_de_publicar(modulo, arbol) -> list[str]:
    """Avisos de lectura. No bloquean publicar ni escriben."""
    from core.media_encode_async import estado_encode_paso

    avisos: list[str] = []
    if not (getattr(modulo, 'titulo', None) or '').strip():
        avisos.append('El módulo no tiene nombre.')
    for bloque in arbol:
        sec = bloque['seccion']
        micros = list(bloque.get('micros') or [])
        activos_con_contenido = [
            m for m in micros
            if m.activo and ((m.contenido or '').strip() or (m.media_url or '').strip())
        ]
        if micros and not activos_con_contenido:
            avisos.append(
                f'La sección «{sec.titulo}» no tiene mensajes activos con contenido.'
            )
        for m in micros:
            if not m.activo:
                avisos.append(f'El mensaje {m.orden} está sin activar.')
            if (m.contenido or '').strip() and (m.media_url or '').strip():
                avisos.append(f'El mensaje {m.orden} tiene texto y archivo juntos.')
            if m.pk:
                enc = estado_encode_paso(m.pk, paso=m) or {}
                if enc.get('status') in ('pending', 'running'):
                    avisos.append(f'El video del mensaje {m.orden} se está preparando.')
    return avisos


def buscar_personas(consulta: str, limite: int = 8) -> list[dict]:
    """Nombre, organización o teléfono. Nunca cédula."""
    from core.models import Estudiante

    q = (consulta or '').strip()
    if len(q) < 2:
        return []
    qs = (
        Estudiante.objects.filter(
            Q(nombre__icontains=q)
            | Q(telefono__icontains=q)
            | Q(cliente__nombre__icontains=q)
        )
        .select_related('cliente')
        .order_by('nombre', 'id')[:limite]
    )
    return [
        {
            'id': est.pk,
            'nombre': est.nombre,
            'telefono': est.telefono,
            'organizacion': est.cliente.nombre if est.cliente_id else '',
        }
        for est in qs
    ]


def _fmt(dt) -> str:
    if not dt:
        return ''
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return timezone.localtime(dt).strftime('%d/%m/%Y %H:%M')


def _capa(estudiante, modulo, disponible: bool) -> tuple[str, str]:
    """Nombra la capa que ya decidió el calendario. No recalcula la regla."""
    from core.drip_schedule import estudiante_autorizado_en_modulo, habilitado_desde_efectivo
    from core.models import HabilitacionModuloDripCliente, HabilitacionModuloEstudiante

    if not estudiante_autorizado_en_modulo(estudiante, modulo):
        return 'personas habilitadas a mano', ''
    efectivo = habilitado_desde_efectivo(estudiante, modulo)
    if not efectivo:
        if disponible:
            return 'sin fecha de calendario', ''
        return 'calendario', ''
    marca = _fmt(efectivo)
    fila_persona = (
        HabilitacionModuloEstudiante.objects.filter(
            estudiante_id=estudiante.id,
            curso_id=modulo.curso_id,
            modulo_id=modulo.id,
            activo=True,
        )
        .only('habilitado_desde')
        .first()
    )
    if fila_persona is not None and fila_persona.habilitado_desde == efectivo:
        return 'fecha de esta persona', marca
    if getattr(estudiante, 'cliente_id', None):
        fila_org = (
            HabilitacionModuloDripCliente.objects.filter(
                cliente_id=estudiante.cliente_id,
                curso_id=modulo.curso_id,
                modulo_id=modulo.id,
                activo=True,
            )
            .only('habilitado_desde')
            .first()
        )
        if fila_org is not None and fila_org.habilitado_desde == efectivo:
            return 'fecha de la organización', marca
    if getattr(modulo, 'habilitado_desde', None) == efectivo:
        return 'fecha del módulo', marca
    return 'calendario', marca


def veredicto_persona(modulo, estudiante) -> dict:
    from core.drip_schedule import (
        dias_espera_efectivos,
        drip_bloquea_siguiente_modulo,
        mensaje_bloqueo_avance_siguiente_modulo,
        modulo_disponible_por_calendario,
    )
    from core.models import Modulo, ProgresoEstudiante

    progreso = (
        ProgresoEstudiante.objects.filter(
            estudiante_id=estudiante.id,
            curso_id=modulo.curso_id,
        )
        .select_related('estudiante', 'curso')
        .first()
    )
    if progreso is None:
        return {
            'inscrito': False,
            'texto': 'No está inscrito en este curso',
        }
    disponible = modulo_disponible_por_calendario(estudiante, modulo)
    capa, fecha = _capa(estudiante, modulo, disponible)
    anterior = (
        Modulo.objects.filter(curso_id=modulo.curso_id, numero__lt=modulo.numero)
        .order_by('-numero')
        .first()
    )
    mensaje = ''
    bloquea = False
    if anterior is not None:
        bloquea = drip_bloquea_siguiente_modulo(progreso, anterior)
        texto = mensaje_bloqueo_avance_siguiente_modulo(estudiante, progreso, anterior)
        mensaje = texto or ''
    if disponible:
        veredicto = f'Hoy recibe este módulo. Lo permite: {capa}.'
    else:
        cuando = f' ({fecha})' if fecha else ''
        veredicto = f'Hoy no recibe este módulo. Lo bloquea: {capa}{cuando}.'
    if fecha:
        veredicto = f'{veredicto} Fecha de esa capa: {fecha}.'
    return {
        'inscrito': True,
        'disponible': disponible,
        'capa': capa,
        'fecha': fecha,
        'veredicto': veredicto,
        'mensaje_listo': mensaje,
        'drip_bloquea_siguiente': bloquea,
        'ritmo_dias': dias_espera_efectivos(estudiante, modulo.curso),
    }
