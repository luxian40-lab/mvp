"""Copiar conocimiento Nati (biblioteca + RAG comercial) desde Agronexo/general a un cliente.

Evita re-subir archivos (la indexación en request cuelga). Reutiliza el mismo
archivo en almacenamiento y encola reindexación async hacia el cliente destino.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from django.db import transaction
from django.db.models import Q

from core.models import BibliotecaConocimiento, Cliente, DocumentoRAGComercial

CLIENTE_FUENTE_NOMBRE = 'Agronexo'
CANAL_RAG = 'bot_comercial'


class FuenteConocimientoNoEncontrada(LookupError):
    """No hay cliente Agronexo ni documentos generales para copiar."""


@dataclass
class ResultadoCopiaConocimiento:
    destino: Cliente
    origen: Cliente | None
    bib_copiados: int = 0
    bib_omitidos: int = 0
    rag_copiados: int = 0
    rag_omitidos: int = 0
    mensajes: list[str] = field(default_factory=list)


def obtener_cliente_agronexo() -> Cliente | None:
    return (
        Cliente.objects.filter(nombre__icontains=CLIENTE_FUENTE_NOMBRE, activo=True)
        .order_by('id')
        .first()
    )


def _nombre_rag_unico(destino: Cliente, nombre: str) -> str:
    base = (nombre or 'doc')[:180]
    candidato = base
    n = 1
    while DocumentoRAGComercial.objects.filter(
        cliente=destino, canal=CANAL_RAG, nombre=candidato
    ).exists():
        n += 1
        candidato = f'{base}-{n}'[:200]
    return candidato


def _slug_unico(destino: Cliente, slug: str) -> str:
    from core.biblioteca_nat_service import slug_unico

    return slug_unico(destino, slug.replace('-', ' ') or 'conocimiento')


def _copiar_archivo_field(origen_field, destino_obj, attr: str = 'archivo') -> None:
    """Reutiliza la misma key S3/disco sin re-upload (evita colgar el admin)."""
    if not origen_field:
        return
    name = getattr(origen_field, 'name', '') or ''
    if not name:
        return
    getattr(destino_obj, attr).name = name


@transaction.atomic
def copiar_conocimiento_a_cliente(
    destino: Cliente,
    *,
    origen: Cliente | None = None,
    incluir_generales: bool = True,
    encolar_index: bool = True,
) -> ResultadoCopiaConocimiento:
    """
    Copia BibliotecaConocimiento + DocumentoRAGComercial al cliente destino.

    Fuente: Agronexo (por nombre) y/o documentos RAG con cliente vacío (general).
    """
    if origen is None:
        origen = obtener_cliente_agronexo()

    hay_bib = (
        BibliotecaConocimiento.objects.filter(cliente=origen).exists()
        if origen
        else False
    )
    rag_q = Q()
    if origen:
        rag_q |= Q(cliente=origen)
    if incluir_generales:
        rag_q |= Q(cliente__isnull=True)
    hay_rag = DocumentoRAGComercial.objects.filter(rag_q, canal=CANAL_RAG).exists() if rag_q else False

    if not hay_bib and not hay_rag:
        raise FuenteConocimientoNoEncontrada(
            'No hay documentos en Agronexo ni RAG general (cliente vacío) para copiar.'
        )

    out = ResultadoCopiaConocimiento(destino=destino, origen=origen)
    bib_nuevos: list[BibliotecaConocimiento] = []
    rag_nuevos: list[DocumentoRAGComercial] = []

    if origen:
        for src in BibliotecaConocimiento.objects.filter(cliente=origen).exclude(
            estado_publicacion='archivado'
        ):
            # Evitar duplicar por título ya presente
            if BibliotecaConocimiento.objects.filter(
                cliente=destino, titulo=src.titulo
            ).exists():
                out.bib_omitidos += 1
                continue
            nuevo = BibliotecaConocimiento(
                cliente=destino,
                titulo=src.titulo,
                slug=_slug_unico(destino, src.slug or src.titulo),
                categoria=src.categoria,
                formato=src.formato,
                pregunta=src.pregunta,
                texto_contenido=src.texto_contenido,
                enlace_url=src.enlace_url,
                cultivo=src.cultivo,
                problema=src.problema,
                region=src.region,
                idioma=src.idioma,
                nivel=src.nivel,
                fuente=src.fuente,
                autor=src.autor,
                fecha_contenido=src.fecha_contenido,
                estado_publicacion=src.estado_publicacion,
                estado_rag='pendiente',
                rag_error_detalle='',
                chunks_indexados=0,
                subido_por=src.subido_por,
            )
            nuevo.save()
            _copiar_archivo_field(src.archivo, nuevo)
            if nuevo.archivo.name:
                nuevo.save(update_fields=['archivo'])
            bib_nuevos.append(nuevo)
            out.bib_copiados += 1

    vistos_nombres: set[str] = set()
    for src in DocumentoRAGComercial.objects.filter(rag_q, canal=CANAL_RAG).order_by('id'):
        # Dedup por nombre base dentro de esta corrida + destino
        clave = (src.nombre or '').strip().lower()
        if clave in vistos_nombres:
            out.rag_omitidos += 1
            continue
        if DocumentoRAGComercial.objects.filter(
            cliente=destino, canal=CANAL_RAG, nombre=src.nombre
        ).exists():
            out.rag_omitidos += 1
            vistos_nombres.add(clave)
            continue
        vistos_nombres.add(clave)
        nombre = _nombre_rag_unico(destino, src.nombre)
        nuevo = DocumentoRAGComercial(
            cliente=destino,
            canal=CANAL_RAG,
            nombre=nombre,
            tipo=src.tipo,
            estado='pendiente',
            chunks_indexados=0,
            error_indexacion='',
            descripcion=src.descripcion,
            subido_por=src.subido_por,
        )
        nuevo.save()
        _copiar_archivo_field(src.archivo, nuevo)
        if nuevo.archivo.name:
            nuevo.save(update_fields=['archivo'])
        rag_nuevos.append(nuevo)
        out.rag_copiados += 1

    out.mensajes.append(
        f'Origen={origen.nombre if origen else "—"} + generales={incluir_generales}. '
        f'Bib +{out.bib_copiados}/omit {out.bib_omitidos}; '
        f'RAG +{out.rag_copiados}/omit {out.rag_omitidos}.'
    )

    if encolar_index:
        def _enqueue():
            from django.conf import settings

            from core.biblioteca_nat_service import _stagger_segundos, encolar_indexacion

            for i, item in enumerate(bib_nuevos):
                encolar_indexacion(item.pk, countdown=_stagger_segundos(i))
            for i, doc in enumerate(rag_nuevos):
                try:
                    if getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False):
                        continue
                    from core.tasks import indexar_documento_rag_por_id

                    indexar_documento_rag_por_id.apply_async(
                        args=['core', 'DocumentoRAGComercial', doc.pk],
                        countdown=_stagger_segundos(i),
                    )
                except Exception:
                    pass

        transaction.on_commit(_enqueue)

    return out
