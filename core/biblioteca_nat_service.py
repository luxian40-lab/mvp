"""Servicio Knowledge Hub — biblioteca Nat → RAG comercial."""

from __future__ import annotations

import logging
import os
import re
import tempfile

from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from core.models import BibliotecaConocimiento, Cliente

logger = logging.getLogger(__name__)

EXTENSIONES_ARCHIVO = frozenset({
    '.pdf', '.docx', '.txt', '.xlsx', '.xlsm', '.png', '.jpg', '.jpeg', '.webp',
    '.mp3', '.m4a', '.wav', '.mp4', '.webm',
})
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


def indexar_item(item: BibliotecaConocimiento) -> int:
    """Indexa un ítem publicado en Chroma (RAG comercial)."""
    from core.rag_comercial_manager import rag_comercial_manager

    if item.estado_publicacion != 'publicado':
        item.estado_rag = 'pendiente'
        item.save(update_fields=['estado_rag'])
        return 0

    if not rag_comercial_manager.disponible:
        item.estado_rag = 'error'
        item.save(update_fields=['estado_rag'])
        return 0

    nombre = _nombre_rag(item)
    tipo = _tipo_rag(item)
    cliente_id = item.cliente_scope_id

    try:
        rag_comercial_manager.eliminar_documento(cliente_id, CANAL_RAG, nombre)
    except Exception:
        pass

    n_chunks = 0
    try:
        if item.formato == 'archivo' and item.archivo:
            ruta = _ruta_local_archivo(item)
            if ruta:
                n_chunks = rag_comercial_manager.procesar_documento(
                    cliente_id, CANAL_RAG, ruta, nombre, tipo,
                )
        else:
            texto = _texto_metadatos(item)
            if texto.strip():
                n_chunks = rag_comercial_manager.procesar_texto(
                    cliente_id, CANAL_RAG, texto, nombre, tipo,
                )
    except Exception as exc:
        logger.exception('[BibliotecaNat] Error indexando %s: %s', item.pk, exc)
        item.estado_rag = 'error'
        item.save(update_fields=['estado_rag'])
        return 0

    item.chunks_indexados = n_chunks
    item.estado_rag = 'indexado' if n_chunks > 0 else 'error'
    item.fecha_indexado = timezone.now()
    item.save(update_fields=['chunks_indexados', 'estado_rag', 'fecha_indexado'])
    return n_chunks


def _ruta_local_archivo(item: BibliotecaConocimiento) -> str | None:
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
    except Exception:
        return None


def encolar_indexacion(item_id: int) -> None:
    def _run():
        try:
            item = BibliotecaConocimiento.objects.filter(pk=item_id).first()
            if item:
                indexar_item(item)
        except Exception:
            logger.exception('[BibliotecaNat] Fallo indexación id=%s', item_id)

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


def reindexar_publicados(org: Cliente) -> int:
    count = 0
    for item in BibliotecaConocimiento.objects.filter(cliente=org, estado_publicacion='publicado'):
        if indexar_item(item) > 0:
            count += 1
    return count
