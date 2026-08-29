"""Auditoría read-only de media WhatsApp (63019/63021) por curso — sin envíos Twilio."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from django.db.models import Q

from core.modulo_publicacion import _head_url_ok
from core.module_steps import pasos_activos_qs
from core.models import Curso, Modulo, PasoModulo

_MEDIA_EXT = ('.mp4', '.m4v', '.mov', '.mp3', '.m4a', '.jpg', '.jpeg', '.png', '.pdf', '.webp')


def _es_media_url(url: str) -> bool:
    low = (url or '').lower().split('?')[0]
    return any(low.endswith(ext) for ext in _MEDIA_EXT)


def _riesgo_paso(paso: PasoModulo, *, head: bool) -> tuple[str, str | None]:
    """Devuelve (nivel, motivo). nivel: ok | warn | fail."""
    url = (paso.media_url or '').strip()
    if not url:
        return 'ok', None
    if not _es_media_url(url):
        return 'ok', None

    apto = paso.media_wa_apto
    if apto is False:
        return 'fail', 'media_wa_apto=False'

    head_ok = _head_url_ok(url) if head else None
    if head_ok is False:
        return 'fail', 'HEAD falló (63019 probable)'

    low = url.lower().split('?')[0]
    if apto is None and low.endswith(('.mp4', '.m4v', '.mov')):
        return 'warn', 'video sin verificar (apto vacío)'

    if apto is None and head_ok is True:
        return 'warn', 'HEAD OK pero apto vacío'

    return 'ok', None


@dataclass
class PasoAuditRow:
    curso_id: int
    curso_nombre: str
    modulo_id: int
    modulo_numero: int
    modulo_titulo: str
    publicado_wa: bool
    paso_id: int
    paso_orden: int | None
    paso_titulo: str
    media_url: str
    media_wa_apto: bool | None
    head_ok: bool | None
    nivel: str
    motivo: str | None = None


@dataclass
class MediaWaAuditResumen:
    cursos: int = 0
    pasos_media: int = 0
    fail: int = 0
    warn: int = 0
    ok: int = 0
    por_curso: dict[str, dict[str, int]] = field(default_factory=dict)


def auditar_media_cursos(
    *,
    curso_id: int | None = None,
    curso_nombre: str | None = None,
    solo_activos: bool = True,
    head_urls: bool = True,
    solo_riesgo: bool = False,
) -> tuple[list[PasoAuditRow], MediaWaAuditResumen]:
    qs = Curso.objects.all().order_by('nombre', 'id')
    if curso_id:
        qs = qs.filter(id=curso_id)
    if curso_nombre:
        qs = qs.filter(nombre__icontains=curso_nombre.strip())
    if solo_activos:
        qs = qs.filter(activo=True)

    filas: list[PasoAuditRow] = []
    resumen = MediaWaAuditResumen(cursos=qs.count())

    for curso in qs:
        cur_key = f'{curso.id}:{curso.nombre}'
        resumen.por_curso[cur_key] = {'fail': 0, 'warn': 0, 'ok': 0}
        for mod in Modulo.objects.filter(curso=curso).order_by('numero', 'id'):
            for paso in pasos_activos_qs(mod):
                url = (paso.media_url or '').strip()
                if not url or not _es_media_url(url):
                    continue
                resumen.pasos_media += 1
                nivel, motivo = _riesgo_paso(paso, head=head_urls)
                head_ok = _head_url_ok(url) if head_urls else None
                resumen.por_curso[cur_key][nivel] += 1
                setattr(resumen, nivel, getattr(resumen, nivel) + 1)
                if solo_riesgo and nivel == 'ok':
                    continue
                row = PasoAuditRow(
                    curso_id=curso.pk,
                    curso_nombre=curso.nombre,
                    modulo_id=mod.pk,
                    modulo_numero=mod.numero or 0,
                    modulo_titulo=(mod.titulo or '')[:120],
                    publicado_wa=bool(mod.publicado_wa),
                    paso_id=paso.pk,
                    paso_orden=paso.orden,
                    paso_titulo=(paso.titulo or '')[:120],
                    media_url=url[:500],
                    media_wa_apto=paso.media_wa_apto,
                    head_ok=head_ok,
                    nivel=nivel,
                    motivo=motivo,
                )
                filas.append(row)

    return filas, resumen


def contar_media_en_riesgo(*, solo_activos: bool = True) -> dict[str, Any]:
    """Resumen ligero para panel Inicio (sin HEAD)."""
    q = Q(media_wa_apto=False) | (
        Q(media_wa_apto__isnull=True)
        & Q(media_url__iregex=r'\.(mp4|m4v|mov)(\?|$)')
    )
    pasos_qs = PasoModulo.objects.filter(activo=True).filter(q).exclude(media_url='')
    if solo_activos:
        pasos_qs = pasos_qs.filter(modulo__curso__activo=True)

    n_fail = pasos_qs.filter(media_wa_apto=False).count()
    n_warn = pasos_qs.filter(media_wa_apto__isnull=True).count()
    top: list[dict[str, Any]] = []
    vistos: set[int] = set()
    for p in (
        pasos_qs.select_related('modulo', 'modulo__curso')
        .order_by('modulo__curso__nombre', 'modulo__numero', 'orden')[:12]
    ):
        cid = p.modulo.curso_id
        if cid in vistos:
            continue
        vistos.add(cid)
        top.append(
            {
                'curso_id': cid,
                'curso_nombre': p.modulo.curso.nombre,
                'modulo_id': p.modulo_id,
                'n_pasos': pasos_qs.filter(modulo__curso_id=cid).count(),
            }
        )
        if len(top) >= 5:
            break

    return {
        'total': pasos_qs.count(),
        'fail': n_fail,
        'warn': n_warn,
        'top_cursos': top,
    }


def filas_a_dict(filas: list[PasoAuditRow]) -> list[dict[str, Any]]:
    return [asdict(r) for r in filas]
