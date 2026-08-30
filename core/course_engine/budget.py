"""Presupuesto por tier — topes de costo y escenas (Fase 2A sin Runway)."""
from __future__ import annotations

import enum
from dataclasses import dataclass

from core.course_engine.types import Scene, SceneType, Storyboard


class VideoTier(str, enum.Enum):
    ECONOMICO = 'economico'
    ESTANDAR = 'estandar'
    PREMIUM = 'premium'


@dataclass(frozen=True)
class TierLimits:
    max_usd: float
    max_images: int
    max_video_ia: int
    max_scenes: int
    max_duration_seg: float


TIER_LIMITS: dict[VideoTier, TierLimits] = {
    VideoTier.ECONOMICO: TierLimits(
        max_usd=2.0,
        max_images=6,
        max_video_ia=0,
        max_scenes=8,
        max_duration_seg=90.0,
    ),
    VideoTier.ESTANDAR: TierLimits(
        max_usd=5.0,
        max_images=8,
        max_video_ia=1,
        max_scenes=10,
        max_duration_seg=120.0,
    ),
    VideoTier.PREMIUM: TierLimits(
        max_usd=15.0,
        max_images=10,
        max_video_ia=3,
        max_scenes=12,
        max_duration_seg=180.0,
    ),
}

# Estimados USD (Fase 2A — sin Runway)
COST_IMAGE_USD = 0.04
COST_STORYBOARD_USD = 0.02
COST_TTS_PER_1K_CHARS = 0.15  # aprox ElevenLabs; conservador


def limits_for(tier: str | VideoTier) -> TierLimits:
    if isinstance(tier, str):
        tier = VideoTier(tier.strip().lower())
    return TIER_LIMITS[tier]


def estimar_costo_storyboard(storyboard: Storyboard) -> float:
    n_images = sum(
        1 for s in storyboard.escenas
        if s.tipo in {SceneType.IMAGEN, SceneType.IMAGEN_ZOOM, SceneType.DIAGRAMA, SceneType.TEXTO, SceneType.RESUMEN}
        or s.tipo == SceneType.VIDEO_IA
    )
    chars = sum(len(s.guion or '') for s in storyboard.escenas)
    return (
        COST_STORYBOARD_USD
        + n_images * COST_IMAGE_USD
        + (chars / 1000.0) * COST_TTS_PER_1K_CHARS
    )


def aplicar_limites_storyboard(storyboard: Storyboard, tier: str | VideoTier) -> Storyboard:
    """Recorta escenas y degrada video_ia → imagen_zoom si el tier no lo permite."""
    lim = limits_for(tier)
    escenas = sorted(storyboard.escenas, key=lambda s: s.orden)[: lim.max_scenes]

    video_ia_count = 0
    nuevas: list[Scene] = []
    for esc in escenas:
        tipo = esc.tipo
        meta = dict(esc.metadata)
        if tipo == SceneType.VIDEO_IA:
            if video_ia_count >= lim.max_video_ia:
                tipo = SceneType.IMAGEN_ZOOM
                meta['degradado_desde'] = 'video_ia'
                meta['motivo'] = 'tier_sin_video_ia'
            else:
                video_ia_count += 1
                # Fase 2A: aún no hay Runway — degradar siempre
                tipo = SceneType.IMAGEN_ZOOM
                meta['degradado_desde'] = 'video_ia'
                meta['motivo'] = 'fase_2a_sin_runway'
        nuevas.append(
            Scene(
                orden=esc.orden,
                tipo=tipo,
                titulo=esc.titulo,
                guion=esc.guion,
                duracion_seg=min(esc.duracion_seg, 20.0),
                notas_visuales=esc.notas_visuales,
                metadata=meta,
            )
        )

    total_dur = sum(s.duracion_seg for s in nuevas)
    if total_dur > lim.max_duration_seg and nuevas:
        factor = lim.max_duration_seg / total_dur
        nuevas = [
            Scene(
                orden=s.orden,
                tipo=s.tipo,
                titulo=s.titulo,
                guion=s.guion,
                duracion_seg=max(3.0, s.duracion_seg * factor),
                notas_visuales=s.notas_visuales,
                metadata=s.metadata,
            )
            for s in nuevas
        ]

    return Storyboard(
        titulo_leccion=storyboard.titulo_leccion,
        objetivo=storyboard.objetivo,
        escenas=nuevas,
        modelo_ia=storyboard.modelo_ia,
    )


def validar_presupuesto(storyboard: Storyboard, tier: str | VideoTier) -> tuple[bool, float, str]:
    lim = limits_for(tier)
    costo = estimar_costo_storyboard(storyboard)
    n_images = sum(
        1 for s in storyboard.escenas
        if s.tipo in {SceneType.IMAGEN, SceneType.IMAGEN_ZOOM, SceneType.DIAGRAMA, SceneType.TEXTO, SceneType.RESUMEN}
    )
    if n_images > lim.max_images:
        return False, costo, f'Demasiadas imágenes ({n_images} > {lim.max_images})'
    if costo > lim.max_usd:
        return False, costo, f'Costo estimado ${costo:.2f} > tope ${lim.max_usd:.2f}'
    return True, costo, 'ok'
