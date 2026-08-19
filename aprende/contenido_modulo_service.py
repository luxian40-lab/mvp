"""Contenido del módulo para el aula: secciones, pasos y multimedia (mismo origen que WhatsApp)."""

from __future__ import annotations

from dataclasses import dataclass, field

from core.models import Modulo, PasoModulo, SeccionModulo
from core.models_extras import ArchivoModulo

from .media_aula import MediaAula, media_desde_url


@dataclass
class PasoAula:
    orden: int
    tipo: str
    tipo_etiqueta: str
    contenido: str
    medias: list[MediaAula] = field(default_factory=list)
    es_evaluacion: bool = False
    es_entrega: bool = False
    solo_whatsapp: bool = False


@dataclass
class SeccionAula:
    orden: int
    titulo: str
    pasos: list[PasoAula] = field(default_factory=list)


_TIPO_ETIQUETA = {
    PasoModulo.TIPO_CONTENIDO: 'Contenido',
    PasoModulo.TIPO_EVAL_OPC: 'Evaluación',
    PasoModulo.TIPO_EVAL_ABIERTA: 'Pregunta abierta',
    PasoModulo.TIPO_RETO: 'Reto',
    PasoModulo.TIPO_ENTREGA: 'Entrega',
}


def _url_archivo_modulo(archivo: ArchivoModulo) -> str | None:
    if archivo.url_externa:
        return archivo.url_externa
    if archivo.archivo:
        return archivo.archivo.url
    return None


def _titulo_paso_media(paso: PasoModulo) -> str:
    return (paso.titulo or '').strip() or f'Material paso {paso.orden}'


def media_de_paso(paso: PasoModulo) -> MediaAula | None:
    return media_desde_url(_titulo_paso_media(paso), paso.media_url)


def media_pasos_modulo(modulo: Modulo) -> list[tuple[str, MediaAula]]:
    """Media de microcontenidos (PasoModulo) en secciones activas."""
    items: list[tuple[str, MediaAula]] = []
    pasos = (
        PasoModulo.objects.filter(modulo=modulo, activo=True, seccion__activa=True)
        .exclude(media_url='')
        .select_related('seccion')
        .order_by('seccion__orden', 'seccion__id', 'orden', 'id')
    )
    for paso in pasos:
        url = (paso.media_url or '').strip()
        if not url:
            continue
        titulo = _titulo_paso_media(paso)
        media = media_desde_url(titulo, url)
        if media:
            items.append((titulo, media))
    return items


def archivos_multimedia_modulo(modulo: Modulo) -> list[MediaAula]:
    items: list[MediaAula] = []
    for arch in ArchivoModulo.objects.filter(modulo=modulo, activo=True).order_by('orden', 'titulo'):
        url = _url_archivo_modulo(arch)
        media = media_desde_url(arch.titulo, url or '', arch.tipo)
        if media:
            items.append(media)
    return items


def secciones_modulo_aula(modulo: Modulo) -> list[SeccionAula]:
    """Secciones y microcontenidos (PasoModulo) tal como se configuran en admin."""
    out: list[SeccionAula] = []
    secciones = SeccionModulo.objects.filter(modulo=modulo, activa=True).order_by('orden', 'id')
    for sec in secciones:
        pasos_out: list[PasoAula] = []
        pasos = PasoModulo.objects.filter(seccion=sec, activo=True).order_by('orden', 'id')
        for paso in pasos:
            medias: list[MediaAula] = []
            media = media_de_paso(paso)
            if media:
                medias.append(media)
            contenido = (paso.contenido or '').strip()
            es_eval = paso.tipo in (
                PasoModulo.TIPO_EVAL_OPC,
                PasoModulo.TIPO_EVAL_ABIERTA,
                PasoModulo.TIPO_RETO,
            )
            es_entrega = paso.tipo == PasoModulo.TIPO_ENTREGA
            solo_wa = es_eval or es_entrega
            if contenido or medias or solo_wa:
                pasos_out.append(
                    PasoAula(
                        orden=paso.orden,
                        tipo=paso.tipo,
                        tipo_etiqueta=_TIPO_ETIQUETA.get(paso.tipo, paso.tipo),
                        contenido=contenido if not solo_wa else '',
                        medias=medias,
                        es_evaluacion=es_eval,
                        es_entrega=es_entrega,
                        solo_whatsapp=solo_wa,
                    )
                )
        titulo_sec = (sec.titulo or '').strip()
        if pasos_out or titulo_sec:
            out.append(
                SeccionAula(
                    orden=sec.orden,
                    titulo=titulo_sec or f'Sección {sec.orden}',
                    pasos=pasos_out,
                )
            )
    return out


def modulo_tiene_microcontenidos(modulo: Modulo) -> bool:
    return PasoModulo.objects.filter(modulo=modulo, activo=True, seccion__activa=True).exists()


def contexto_render_modulo_estudiante(
    modulo: Modulo,
    *,
    estudiante=None,
    quiz_intento=None,
    quiz_detalle=None,
) -> dict:
    """Contexto compartido entre vista estudiante y vista previa del profesor."""
    from aprende.quiz_aula_service import intento_previo, opciones_pregunta, preguntas_activas

    archivos_media = archivos_multimedia_modulo(modulo)
    secciones = secciones_modulo_aula(modulo)
    tiene_micro = modulo_tiene_microcontenidos(modulo)
    video_url = (
        modulo.get_video_url_publica()
        if modulo.video_url or modulo.video_archivo
        else modulo.video_url
    )
    video_media = (
        media_desde_url(f'Video — {modulo.titulo}', video_url or '', 'video')
        if video_url
        else None
    )
    pdf_media = (
        media_desde_url('Documento del módulo', modulo.archivo_pdf_url, 'pdf')
        if modulo.archivo_pdf_url
        else None
    )
    if estudiante is not None and quiz_intento is None:
        quiz_intento = intento_previo(estudiante, modulo)
    preguntas = preguntas_activas(modulo)
    quiz_items = [
        {'pregunta': p, 'opciones': opciones_pregunta(p)}
        for p in preguntas
    ]
    return {
        'estudiante': estudiante,
        'modulo': modulo,
        'secciones': secciones,
        'tiene_micro': tiene_micro,
        'archivos_media': archivos_media,
        'video_media': video_media,
        'video_medias': [video_media] if video_media else [],
        'pdf_media': pdf_media,
        'pdf_medias': [pdf_media] if pdf_media else [],
        'quiz_items': quiz_items,
        'quiz_intento': quiz_intento,
        'quiz_detalle': quiz_detalle,
    }
