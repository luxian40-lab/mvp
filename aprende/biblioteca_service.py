"""Biblioteca multimedia del aula: archivos de módulos liberados (mismo origen que WhatsApp)."""

from __future__ import annotations

from dataclasses import dataclass

from core.models import Curso, Estudiante, Modulo, ProgresoEstudiante
from core.models_extras import ArchivoModulo

from .acceso_modulos import modulos_visibles_aula
from .media_aula import MediaAula, media_desde_url


@dataclass
class ItemBibliotecaAula:
    curso: Curso
    modulo: Modulo
    archivo: ArchivoModulo | None
    tipo: str
    titulo: str
    url: str | None
    media: MediaAula | None = None
    es_video_modulo: bool = False


def _url_archivo(archivo: ArchivoModulo) -> str | None:
    if archivo.url_externa:
        return archivo.url_externa
    if archivo.archivo:
        return archivo.archivo.url
    return None


def items_biblioteca_aula(estudiante: Estudiante) -> list[ItemBibliotecaAula]:
    """
    Multimedia accesible en el aula para un estudiante:
    archivos activos de módulos liberados (drip/avance) en sus cursos inscritos.
    Incluye video/PDF del módulo cuando están configurados.
    """
    items: list[ItemBibliotecaAula] = []
    progresos = (
        ProgresoEstudiante.objects.filter(estudiante=estudiante, curso__activo=True)
        .select_related('curso')
        .order_by('curso__nombre')
    )

    for prog in progresos:
        for modulo in modulos_visibles_aula(estudiante, prog.curso, prog):
            video_url = (
                modulo.get_video_url_publica()
                if modulo.video_url or modulo.video_archivo
                else modulo.video_url
            )
            if video_url:
                media = media_desde_url(f'Video — {modulo.titulo}', video_url, 'video')
                items.append(
                    ItemBibliotecaAula(
                        curso=prog.curso,
                        modulo=modulo,
                        archivo=None,
                        tipo='video',
                        titulo=f'Video — {modulo.titulo}',
                        url=video_url,
                        media=media,
                        es_video_modulo=True,
                    )
                )
            if modulo.archivo_pdf_url:
                media = media_desde_url(f'PDF — {modulo.titulo}', modulo.archivo_pdf_url, 'pdf')
                items.append(
                    ItemBibliotecaAula(
                        curso=prog.curso,
                        modulo=modulo,
                        archivo=None,
                        tipo='pdf',
                        titulo=f'PDF — {modulo.titulo}',
                        url=modulo.archivo_pdf_url,
                        media=media,
                    )
                )
            for arch in ArchivoModulo.objects.filter(modulo=modulo, activo=True).order_by(
                'orden', 'titulo'
            ):
                url = _url_archivo(arch)
                items.append(
                    ItemBibliotecaAula(
                        curso=prog.curso,
                        modulo=modulo,
                        archivo=arch,
                        tipo=arch.tipo,
                        titulo=arch.titulo,
                        url=url,
                        media=media_desde_url(arch.titulo, url or '', arch.tipo),
                    )
                )
    return items


def biblioteca_agrupada_por_curso(estudiante: Estudiante) -> list[dict]:
    """Agrupa items por curso para la plantilla."""
    por_curso: dict[int, dict] = {}
    for item in items_biblioteca_aula(estudiante):
        cid = item.curso.pk
        if cid not in por_curso:
            por_curso[cid] = {'curso': item.curso, 'items': []}
        por_curso[cid]['items'].append(item)
    return list(por_curso.values())
