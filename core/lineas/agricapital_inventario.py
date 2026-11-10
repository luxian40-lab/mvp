"""S0: inventario de media de cursos AgriCapital (MB por curso).

Solo el cliente de EKI_AGRICAPITAL_CLIENTE_ID. Sin setting = lista vacía.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from urllib.parse import urlparse


_MEDIA_EXT = (
    '.mp4', '.m4v', '.mov', '.3gp',
    '.mp3', '.m4a', '.aac', '.ogg', '.amr',
    '.jpg', '.jpeg', '.png', '.webp', '.pdf',
)


@dataclass
class MediaFila:
    curso_id: int
    curso_nombre: str
    origen: str  # paso | archivo_legacy
    ref: str
    url: str
    bytes: int | None
    mb: float | None
    error: str | None = None


@dataclass
class CursoResumen:
    curso_id: int
    curso_nombre: str
    archivos: int = 0
    bytes_conocidos: int = 0
    mb_conocidos: float = 0.0
    sin_tamano: int = 0
    filas: list[MediaFila] = field(default_factory=list)


def _es_media_url(url: str) -> bool:
    low = (url or '').lower().split('?')[0]
    return any(low.endswith(ext) for ext in _MEDIA_EXT)


def _bytes_por_head(url: str, timeout: float = 6.0) -> tuple[int | None, str | None]:
    if not url or url.startswith('/'):
        return None, 'url_local'
    import urllib.error
    import urllib.request

    try:
        req = urllib.request.Request(
            url,
            method='HEAD',
            headers={'User-Agent': 'eki-agricapital-inventario/1.0'},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if not (200 <= resp.status < 400):
                return None, f'http_{resp.status}'
            bruto = resp.headers.get('Content-Length') or resp.headers.get('content-length')
            if bruto is None:
                return None, 'sin_content_length'
            return int(bruto), None
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, OSError) as exc:
        return None, type(exc).__name__


def _mb(n: int | None) -> float | None:
    if n is None:
        return None
    return round(n / (1024 * 1024), 2)


def cursos_agricapital():
    """Cursos del carrusel AgriCapital; vacío si el cliente no está configurado."""
    from core.lineas.registro_agricapital import cliente_id_configurado, cursos_del_carrusel
    from core.models import Cliente

    cliente_id = cliente_id_configurado()
    if cliente_id is None:
        return []
    cliente = Cliente.objects.filter(pk=cliente_id, activo=True).first()
    if cliente is None:
        return []
    return cursos_del_carrusel(cliente)


def inventariar_media_agricapital(*, head_urls: bool = True) -> list[CursoResumen]:
    """Suma media de pasos y archivos legacy por curso AgriCapital."""
    from core.models import ArchivoModulo, Modulo, PasoModulo

    resumenes: list[CursoResumen] = []
    for curso in cursos_agricapital():
        cur = CursoResumen(curso_id=curso.pk, curso_nombre=curso.nombre or f'Curso {curso.pk}')
        for mod in Modulo.objects.filter(curso=curso).order_by('numero', 'id'):
            for paso in PasoModulo.objects.filter(modulo=mod).order_by('orden', 'id'):
                url = (paso.media_url or '').strip()
                if not url or not _es_media_url(url):
                    continue
                nbytes, err = (_bytes_por_head(url) if head_urls else (None, 'sin_head'))
                fila = MediaFila(
                    curso_id=curso.pk,
                    curso_nombre=cur.curso_nombre,
                    origen='paso',
                    ref=f'M{mod.numero or 0}/paso{paso.orden or paso.pk}',
                    url=url,
                    bytes=nbytes,
                    mb=_mb(nbytes),
                    error=err,
                )
                cur.filas.append(fila)
                cur.archivos += 1
                if nbytes is not None:
                    cur.bytes_conocidos += nbytes
                else:
                    cur.sin_tamano += 1
            for arch in ArchivoModulo.objects.filter(modulo=mod, activo=True).order_by('orden', 'id'):
                url = ''
                if getattr(arch, 'url_externa', None):
                    url = (arch.url_externa or '').strip()
                elif getattr(arch, 'archivo', None):
                    try:
                        url = arch.archivo.url
                    except (ValueError, OSError, AttributeError):
                        url = ''
                if not url or not _es_media_url(url):
                    continue
                nbytes, err = (None, None)
                if head_urls and urlparse(url).scheme in ('http', 'https'):
                    nbytes, err = _bytes_por_head(url)
                elif getattr(arch, 'archivo', None):
                    try:
                        nbytes = int(arch.archivo.size)
                    except (ValueError, OSError, AttributeError):
                        err = 'sin_size_local'
                else:
                    err = 'sin_head'
                fila = MediaFila(
                    curso_id=curso.pk,
                    curso_nombre=cur.curso_nombre,
                    origen='archivo_legacy',
                    ref=f'M{mod.numero or 0}/{arch.titulo or arch.pk}',
                    url=url,
                    bytes=nbytes,
                    mb=_mb(nbytes),
                    error=err,
                )
                cur.filas.append(fila)
                cur.archivos += 1
                if nbytes is not None:
                    cur.bytes_conocidos += nbytes
                else:
                    cur.sin_tamano += 1
        cur.mb_conocidos = _mb(cur.bytes_conocidos) or 0.0
        resumenes.append(cur)
    return resumenes


def resumenes_a_dict(resumenes: list[CursoResumen]) -> list[dict[str, Any]]:
    return [asdict(r) for r in resumenes]
