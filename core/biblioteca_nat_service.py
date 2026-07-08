"""Servicio Knowledge Hub — biblioteca Nat → RAG comercial."""

from __future__ import annotations

import logging
import os
import tempfile

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from core.models import BibliotecaConocimiento, Cliente

logger = logging.getLogger(__name__)

EXTENSIONES_ARCHIVO = frozenset({
    '.pdf', '.docx', '.txt', '.xlsx', '.xlsm', '.png', '.jpg', '.jpeg', '.webp',
    '.mp3', '.m4a', '.wav', '.mp4', '.webm',
})
EXTENSIONES_TEXTO_RAG = frozenset({'.pdf', '.docx', '.txt', '.xlsx', '.xlsm'})
CANAL_RAG = 'bot_comercial'


def slug_unico(cliente: Cliente, titulo: str, exclude_pk: int | None = None) -> str:
    base = slugify(titulo)[:160] or 'conocimiento'
    slug = base
    n = 1
    while BibliotecaConocimiento.objects.filter(cliente=cliente, slug=slug).exclude(pk=exclude_pk).exists():
        n += 1
        slug = f'{base}-{n}'
    return slug


def _tipo_rag(item: BibliotecaConocimiento) -> str:
    if item.categoria == 'faq':
        return 'faq'
    if item.categoria == 'productos':
        return 'producto'
    if item.categoria in ('normatividad', 'protocolos'):
        return 'informe_tecnico'
    return 'general'


def _nombre_rag(item: BibliotecaConocimiento) -> str:
    return f'bib_{item.pk}_{item.slug}'


def _texto_metadatos(item: BibliotecaConocimiento) -> str:
    lineas = [f'# {item.titulo}']
    if item.pregunta:
        lineas.append(f'Pregunta: {item.pregunta}')
    if item.texto_contenido:
        lineas.append(item.texto_contenido.strip())
    meta = []
    if item.cultivo:
        meta.append(f'Cultivo: {item.cultivo}')
    if item.problema:
        meta.append(f'Problema: {item.problema}')
    if item.region:
        meta.append(f'Región: {item.region}')
    if item.autor:
        meta.append(f'Autor: {item.autor}')
    if item.fuente:
        meta.append(f'Fuente: {item.get_fuente_display()}')
    if item.enlace_url:
        meta.append(f'Enlace: {item.enlace_url}')
    if meta:
        lineas.append('Metadatos: ' + ' | '.join(meta))
    return '\n\n'.join(lineas)


def _ruta_local_archivo(item: BibliotecaConocimiento) -> str | None:
    """Descarga a temporal local (S3 o disco) para extracción de texto."""
    if not item.archivo:
        return None
    try:
        if hasattr(item.archivo, 'path') and os.path.exists(item.archivo.path):
            return item.archivo.path
    except Exception:
        pass
    try:
        ext = os.path.splitext(item.archivo.name)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            for chunk in item.archivo.chunks():
                tmp.write(chunk)
            return tmp.name
    except Exception as exc:
        logger.error('[BibliotecaNat] Error descargando archivo id=%s: %s', item.pk, exc)
        return None


def _marcar_estado(item: BibliotecaConocimiento, *, estado: str, n_chunks: int = 0, error: str = '') -> None:
    item.chunks_indexados = n_chunks
    item.estado_rag = estado
    item.rag_error_detalle = (error or '')[:500]
    if estado == 'indexado':
        item.fecha_indexado = timezone.now()
        item.save(update_fields=['chunks_indexados', 'estado_rag', 'rag_error_detalle', 'fecha_indexado'])
    else:
        item.save(update_fields=['chunks_indexados', 'estado_rag', 'rag_error_detalle'])


def indexar_item(item: BibliotecaConocimiento) -> int:
    """Indexa un ítem publicado en Chroma (RAG comercial)."""
    from core.rag_comercial_manager import rag_comercial_manager

    if item.estado_publicacion != 'publicado':
        _marcar_estado(item, estado='pendiente', error='')
        return 0

    if not rag_comercial_manager.disponible:
        _marcar_estado(
            item,
            estado='error',
            error='ChromaDB no disponible en el servidor. Contacte soporte eki.',
        )
        return 0

    nombre = _nombre_rag(item)
    tipo = _tipo_rag(item)
    cliente_id = item.cliente_scope_id
    errores: list[str] = []

    try:
        rag_comercial_manager.eliminar_documento(cliente_id, CANAL_RAG, nombre)
    except Exception:
        pass

    n_chunks = 0

    # 1) Archivo (PDF, Word, Excel…)
    if item.archivo:
        ruta = _ruta_local_archivo(item)
        if not ruta:
            errores.append('No se pudo leer el archivo (revisar permisos S3 o volver a subirlo).')
        else:
            ext = os.path.splitext(ruta)[1].lower()
            try:
                if ext in EXTENSIONES_TEXTO_RAG:
                    n_chunks = rag_comercial_manager.procesar_documento(
                        cliente_id, CANAL_RAG, ruta, nombre, tipo,
                    )
                    if n_chunks == 0:
                        errores.append(
                            'El archivo no tiene texto extraíble (PDF escaneado, Excel vacío o Word sin contenido). '
                            'Agregue un resumen en la pestaña Artículo y guarde de nuevo.',
                        )
                else:
                    errores.append(
                        f'Formato {ext} no se indexa solo por archivo. '
                        'Escriba un resumen en la pestaña Artículo (título + texto).',
                    )
            except Exception as exc:
                logger.exception('[BibliotecaNat] Error procesando archivo %s: %s', item.pk, exc)
                errores.append(f'Error al procesar archivo: {exc}')
            finally:
                try:
                    if ruta and not hasattr(item.archivo, 'path'):
                        os.unlink(ruta)
                except Exception:
                    pass

    # 2) Texto / FAQ / enlace / resumen complementario
    if n_chunks == 0:
        texto = _texto_metadatos(item)
        if len((texto or '').strip()) >= 15:
            try:
                n_chunks = rag_comercial_manager.procesar_texto(
                    cliente_id, CANAL_RAG, texto, nombre, tipo,
                )
                if n_chunks == 0:
                    errores.append('El texto del artículo es demasiado corto para indexar.')
            except Exception as exc:
                logger.exception('[BibliotecaNat] Error indexando texto %s: %s', item.pk, exc)
                errores.append(f'Error al indexar texto: {exc}')
        elif not item.archivo:
            errores.append('Sin archivo ni texto suficiente. Complete el contenido o adjunte un PDF/DOCX/TXT/Excel.')

    if n_chunks > 0:
        _marcar_estado(item, estado='indexado', n_chunks=n_chunks, error='')
        return n_chunks

    detalle = errores[0] if errores else 'No se generaron fragmentos indexables.'
    _marcar_estado(item, estado='error', n_chunks=0, error=detalle)
    logger.warning('[BibliotecaNat] Indexación fallida id=%s: %s', item.pk, detalle)
    return 0


def encolar_indexacion(item_id: int) -> None:
    def _run():
        try:
            if getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False):
                import threading

                def _bg():
                    try:
                        item = BibliotecaConocimiento.objects.filter(pk=item_id).first()
                        if item:
                            indexar_item(item)
                    except Exception:
                        logger.exception('[BibliotecaNat] Fallo indexación id=%s', item_id)

                threading.Thread(
                    target=_bg, daemon=True, name=f'bib-nat-{item_id}',
                ).start()
            else:
                from core.tasks import indexar_biblioteca_nat_por_id

                indexar_biblioteca_nat_por_id.delay(item_id)
        except Exception:
            logger.exception('[BibliotecaNat] Fallo encolando indexación id=%s', item_id)
            try:
                item = BibliotecaConocimiento.objects.filter(pk=item_id).first()
                if item:
                    indexar_item(item)
            except Exception:
                logger.exception('[BibliotecaNat] Fallback sync falló id=%s', item_id)

    transaction.on_commit(_run)


def crear_desde_formulario(org: Cliente, data: dict, archivo=None, user=None) -> BibliotecaConocimiento:
    titulo = (data.get('titulo') or '').strip()
    if not titulo:
        raise ValueError('El título es obligatorio.')

    formato = (data.get('formato') or 'archivo').strip()
    if formato not in dict(BibliotecaConocimiento.FORMATO_CHOICES):
        raise ValueError('Formato no válido.')

    if formato == 'archivo' and not archivo:
        raise ValueError('Adjunte un archivo.')
    if formato == 'faq':
        if not (data.get('pregunta') or '').strip() or not (data.get('texto_contenido') or '').strip():
            raise ValueError('Indique pregunta y respuesta para la FAQ.')
    if formato in ('texto', 'enlace') and not (data.get('texto_contenido') or '').strip():
        raise ValueError('Escriba el contenido del artículo.')

    if archivo:
        ext = '.' + archivo.name.rsplit('.', 1)[-1].lower() if '.' in archivo.name else ''
        if ext not in EXTENSIONES_ARCHIVO:
            raise ValueError(f'Formato de archivo no soportado ({ext}).')

    item = BibliotecaConocimiento(
        cliente=org,
        titulo=titulo,
        slug=slug_unico(org, titulo),
        categoria=(data.get('categoria') or 'general').strip(),
        formato=formato,
        pregunta=(data.get('pregunta') or '').strip()[:500],
        texto_contenido=(data.get('texto_contenido') or '').strip(),
        enlace_url=(data.get('enlace_url') or '').strip()[:500],
        cultivo=(data.get('cultivo') or '').strip()[:80],
        problema=(data.get('problema') or '').strip()[:120],
        region=(data.get('region') or '').strip()[:120],
        nivel=(data.get('nivel') or 'basico').strip(),
        fuente=(data.get('fuente') or 'cliente').strip(),
        autor=(data.get('autor') or '').strip()[:120],
        estado_publicacion=(data.get('estado_publicacion') or 'publicado').strip(),
        subido_por=user,
    )
    if archivo:
        item.archivo = archivo
    item.save()
    encolar_indexacion(item.pk)
    return item


def actualizar_item(item: BibliotecaConocimiento, data: dict, archivo=None) -> BibliotecaConocimiento:
    titulo = (data.get('titulo') or item.titulo).strip()
    if not titulo:
        raise ValueError('El título es obligatorio.')

    item.titulo = titulo
    item.categoria = (data.get('categoria') or item.categoria).strip()
    item.pregunta = (data.get('pregunta') or '').strip()[:500]
    item.texto_contenido = (data.get('texto_contenido') or item.texto_contenido or '').strip()
    item.enlace_url = (data.get('enlace_url') or '').strip()[:500]
    item.cultivo = (data.get('cultivo') or '').strip()[:80]
    item.problema = (data.get('problema') or '').strip()[:120]
    item.region = (data.get('region') or '').strip()[:120]
    item.nivel = (data.get('nivel') or item.nivel).strip()
    item.fuente = (data.get('fuente') or item.fuente).strip()
    item.autor = (data.get('autor') or '').strip()[:120]
    item.estado_publicacion = (data.get('estado_publicacion') or item.estado_publicacion).strip()
    if archivo:
        ext = '.' + archivo.name.rsplit('.', 1)[-1].lower() if '.' in archivo.name else ''
        if ext not in EXTENSIONES_ARCHIVO:
            raise ValueError(f'Formato no soportado ({ext}).')
        item.archivo = archivo
    item.estado_rag = 'pendiente'
    item.rag_error_detalle = ''
    item.save()
    encolar_indexacion(item.pk)
    return item


def listar_biblioteca(org: Cliente, *, categoria: str = '', cultivo: str = '', q: str = ''):
    qs = BibliotecaConocimiento.objects.filter(cliente=org).exclude(estado_publicacion='archivado')
    if categoria:
        qs = qs.filter(categoria=categoria)
    if cultivo:
        qs = qs.filter(cultivo__icontains=cultivo)
    if q:
        qs = qs.filter(titulo__icontains=q)
    return qs.order_by('-fecha_creacion')


def reindexar_publicados(org: Cliente) -> tuple[int, int]:
    """Reindexa todos los publicados. Devuelve (ok, error)."""
    ok = err = 0
    for item in BibliotecaConocimiento.objects.filter(cliente=org, estado_publicacion='publicado'):
        if indexar_item(item) > 0:
            ok += 1
        else:
            err += 1
    return ok, err


def reindexar_item(item: BibliotecaConocimiento) -> int:
    item.estado_rag = 'pendiente'
    item.rag_error_detalle = ''
    item.save(update_fields=['estado_rag', 'rag_error_detalle'])
    return indexar_item(item)
