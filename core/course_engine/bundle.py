"""Paquete mixto por módulo — estimación costos (video + infografía + podcast)."""
from __future__ import annotations

from dataclasses import dataclass

from core.course_engine.budget import (
    COST_IMAGE_USD,
    COST_STORYBOARD_USD,
    COST_TTS_PER_1K_CHARS,
    COST_VIDEO_IA_USD,
    TIER_LIMITS,
    VideoTier,
)


@dataclass(frozen=True)
class ModuloMixtoPlan:
    """Receta de microcontenidos para un módulo."""

    tier_video: str = 'estandar'
    incluir_infografia: bool = True
    incluir_podcast: bool = True
    podcast_chars: int = 1200  # ~2 min narración
    n_infografias: int = 1
    n_runway_clips: int = 1


@dataclass(frozen=True)
class ModuloMixtoCosto:
    video_usd: float
    infografia_usd: float
    podcast_usd: float
    gpt_extra_usd: float
    total_usd: float


def _costo_video_tier(tier: str, *, n_runway: int = 1) -> float:
    t = VideoTier(tier.strip().lower())
    lim = TIER_LIMITS[t]
    n_img = min(5, lim.max_images)
    n_rw = min(n_runway, lim.max_video_ia)
    chars_video = 700  # guiones cortos por escenas
    return (
        COST_STORYBOARD_USD * 2
        + n_img * COST_IMAGE_USD
        + n_rw * COST_VIDEO_IA_USD
        + (chars_video / 1000.0) * COST_TTS_PER_1K_CHARS
    )


def estimar_costo_modulo_mixto(plan: ModuloMixtoPlan) -> ModuloMixtoCosto:
    video = _costo_video_tier(plan.tier_video, n_runway=plan.n_runway_clips)
    infografia = (plan.n_infografias * COST_IMAGE_USD) if plan.incluir_infografia else 0.0
    podcast = (
        (plan.podcast_chars / 1000.0) * COST_TTS_PER_1K_CHARS + 0.02
        if plan.incluir_podcast
        else 0.0
    )
    gpt_extra = 0.03 if plan.incluir_podcast else 0.0
    total = video + infografia + podcast + gpt_extra
    return ModuloMixtoCosto(
        video_usd=round(video, 2),
        infografia_usd=round(infografia, 2),
        podcast_usd=round(podcast, 2),
        gpt_extra_usd=round(gpt_extra, 2),
        total_usd=round(total, 2),
    )


def estimar_costo_curso(
    n_modulos: int,
    plan: ModuloMixtoPlan,
    *,
    factor_qa: float = 1.10,
) -> dict:
    uno = estimar_costo_modulo_mixto(plan)
    subtotal = uno.total_usd * n_modulos
    con_qa = subtotal * factor_qa
    chars_podcast = plan.podcast_chars * n_modulos if plan.incluir_podcast else 0
    chars_video = 700 * n_modulos
    return {
        'n_modulos': n_modulos,
        'costo_por_modulo_usd': uno.total_usd,
        'desglose_modulo': uno,
        'subtotal_usd': round(subtotal, 2),
        'con_qa_usd': round(con_qa, 2),
        'elevenlabs_chars_aprox': chars_video + chars_podcast,
    }
