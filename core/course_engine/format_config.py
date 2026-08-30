"""Formato de segmentación Course Engine — curso → paquete de microcontenidos."""
from __future__ import annotations

from core.course_engine.bundle import ModuloMixtoPlan

FORMAT_SOLO_VIDEO = 'solo_video'
FORMAT_VIDEO_INFOGRAFIA = 'video_infografia'
FORMAT_MIXTO_COMPLETO = 'mixto_completo'
FORMAT_MIXTO_LIGERO = 'mixto_ligero'

FORMAT_CHOICES = (
    (FORMAT_SOLO_VIDEO, 'Solo video MP4 (1 paso WA)'),
    (FORMAT_VIDEO_INFOGRAFIA, 'Video + infografía PNG (2 pasos)'),
    (FORMAT_MIXTO_COMPLETO, 'Mixto completo: video + infografía + podcast (3 pasos)'),
    (FORMAT_MIXTO_LIGERO, 'Ligero: video económico sin podcast ni PNG suelta'),
)

# Orden sugerido de pasos WA por formato
FORMAT_PASOS_WA: dict[str, list[dict[str, str]]] = {
    FORMAT_SOLO_VIDEO: [
        {'tipo': 'video', 'label': 'Video lección', 'formato_wa': 'video/mp4'},
    ],
    FORMAT_VIDEO_INFOGRAFIA: [
        {'tipo': 'video', 'label': 'Video lección', 'formato_wa': 'video/mp4'},
        {'tipo': 'infografia', 'label': 'Infografía resumen', 'formato_wa': 'image/png'},
    ],
    FORMAT_MIXTO_COMPLETO: [
        {'tipo': 'video', 'label': 'Video gancho', 'formato_wa': 'video/mp4'},
        {'tipo': 'infografia', 'label': 'Infografía', 'formato_wa': 'image/png'},
        {'tipo': 'podcast', 'label': 'Podcast profundización', 'formato_wa': 'audio/mpeg'},
    ],
    FORMAT_MIXTO_LIGERO: [
        {'tipo': 'video', 'label': 'Video lección (económico)', 'formato_wa': 'video/mp4'},
    ],
}


def resolver_formato_curso(curso) -> str:
    fmt = (getattr(curso, 'course_engine_format', None) or FORMAT_VIDEO_INFOGRAFIA).strip()
    valid = {c[0] for c in FORMAT_CHOICES}
    return fmt if fmt in valid else FORMAT_VIDEO_INFOGRAFIA


def resolver_podcast_minutos(curso) -> int:
    raw = int(getattr(curso, 'course_engine_podcast_minutos', 2) or 2)
    return raw if raw in (2, 3, 4) else 2


def plan_desde_curso(curso, *, tier_override: str | None = None) -> ModuloMixtoPlan:
    """Mapea formato del curso → plan de generación."""
    fmt = resolver_formato_curso(curso)
    tier = (tier_override or getattr(curso, 'course_engine_tier', None) or 'economico').strip()
    mins = resolver_podcast_minutos(curso)
    chars_podcast = {2: 1200, 3: 1800, 4: 2400}.get(mins, 1200)

    if fmt == FORMAT_SOLO_VIDEO:
        return ModuloMixtoPlan(
            tier_video=tier,
            incluir_infografia=False,
            incluir_podcast=False,
        )
    if fmt == FORMAT_VIDEO_INFOGRAFIA:
        return ModuloMixtoPlan(
            tier_video=tier,
            incluir_infografia=True,
            incluir_podcast=False,
        )
    if fmt == FORMAT_MIXTO_LIGERO:
        return ModuloMixtoPlan(
            tier_video='economico',
            incluir_infografia=False,
            incluir_podcast=False,
        )
    # mixto_completo
    return ModuloMixtoPlan(
        tier_video=tier,
        incluir_infografia=True,
        incluir_podcast=True,
        podcast_chars=chars_podcast,
    )


def describe_formato(curso) -> str:
    fmt = resolver_formato_curso(curso)
    pasos = FORMAT_PASOS_WA.get(fmt, [])
    labels = ' → '.join(p['label'] for p in pasos)
    return f'{dict(FORMAT_CHOICES).get(fmt, fmt)} ({len(pasos)} paso(s): {labels})'
