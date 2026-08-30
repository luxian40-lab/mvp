"""
CourseVideoGenerator — una sola operación: lección → MP4 en S3.

Fase 2A: DALL-E + ElevenLabs + ffmpeg (sin Runway).
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from django.conf import settings

from core.course_engine.analyzer import analizar_leccion
from core.course_engine.budget import (
    VideoTier,
    aplicar_limites_storyboard,
    estimar_costo_storyboard,
    validar_presupuesto,
)
from core.course_engine.clip_builder import concatenar_clips, construir_clip_escena
from core.course_engine.compose import subir_video_s3
from core.course_engine.image_service import generar_imagen_escena
from core.course_engine.lesson import generar_leccion
from core.course_engine.local_store import guardar_run, local_runs_root
from core.course_engine.rag_source import obtener_contexto_rag_empresa, resumen_documentos_curso
from core.course_engine.storyboard import generar_storyboard
from core.course_engine.tts import generar_narracion_archivo, ultimo_error_tts
from core.course_engine.types import CourseEngineRun, SceneType

logger = logging.getLogger(__name__)

_SKIP_IMAGE = frozenset({SceneType.TRANSICION})


@dataclass
class VideoGenerateResult:
    run: CourseEngineRun
    video_local: Optional[Path] = None
    costo_estimado_usd: float = 0.0
    costo_real_usd: float = 0.0
    pasos: list[str] = field(default_factory=list)


class CourseVideoGenerator:
    """Generar video de la lección — el admin solo dispara esto."""

    def generar(
        self,
        *,
        cliente_id: int,
        curso_id: int,
        brief: str,
        tier: str = 'economico',
        modelo: str = 'gpt-4o-mini',
        dry_run: bool = False,
    ) -> VideoGenerateResult:
        run_id = uuid.uuid4().hex[:12]
        run_dir = local_runs_root() / run_id
        run = CourseEngineRun(
            run_id=run_id,
            cliente_id=cliente_id,
            curso_id=curso_id,
            brief=brief.strip(),
        )
        result = VideoGenerateResult(run=run)
        result.pasos.append('Analizando lección…')

        rag_ctx, rag_ok = obtener_contexto_rag_empresa(cliente_id, curso_id, brief)
        if not rag_ok:
            fb = resumen_documentos_curso(curso_id)
            if fb:
                rag_ctx = fb

        lesson = generar_leccion(brief, rag_ctx, modelo=modelo)
        if not lesson:
            run.errors.append('Falló generación de lección')
            guardar_run(run)
            return result
        run.lesson = lesson

        analysis = analizar_leccion(lesson, modelo=modelo)
        if not analysis:
            run.errors.append('Falló analizador')
            guardar_run(run)
            return result
        run.analysis = analysis

        result.pasos.append('Creando storyboard…')
        sb = generar_storyboard(lesson, analysis, modelo=modelo, tier=tier)
        if not sb:
            run.errors.append('Falló storyboard')
            guardar_run(run)
            return result

        sb = aplicar_limites_storyboard(sb, tier)
        ok, costo_est, msg = validar_presupuesto(sb, tier)
        result.costo_estimado_usd = costo_est
        if not ok:
            run.errors.append(msg)
            run.storyboard = sb
            guardar_run(run)
            return result

        run.storyboard = sb
        if dry_run:
            result.pasos.append(f'Dry-run OK — costo est. ${costo_est:.2f}')
            guardar_run(run)
            return result

        if getattr(settings, 'COURSE_ENGINE_DRY_RUN', False):
            run.errors.append('COURSE_ENGINE_DRY_RUN=true — abortado antes de APIs de pago')
            guardar_run(run)
            return result

        result.pasos.append('Generando recursos…')
        costo_real = 0.0
        clips_dir = run_dir / 'clips'
        clips: list[Path] = []
        escenas_out = []

        for escena in sb.escenas:
            meta = dict(escena.metadata)
            img_path: Optional[Path] = None
            audio_path: Optional[Path] = None
            asset_url = escena.asset_url

            if escena.tipo not in _SKIP_IMAGE:
                img_res = generar_imagen_escena(escena, run_dir)
                if img_res:
                    img_path = img_res.local_path
                    costo_real += img_res.cost_usd
                    meta['image_local'] = str(img_path)
                    if img_res.url:
                        meta['image_url'] = img_res.url
                else:
                    run.errors.append(f'Imagen falló escena {escena.orden}')

            guion = (escena.guion or escena.titulo or '').strip()
            if guion:
                audio_dest = run_dir / 'audio' / f'escena_{escena.orden:02d}.mp3'
                tts = generar_narracion_archivo(guion, audio_dest)
                if tts:
                    audio_path = audio_dest
                    meta['tts_provider'] = tts.provider
                    asset_url = tts.url or asset_url
                else:
                    err = ultimo_error_tts() or 'TTS falló'
                    run.errors.append(f'Audio escena {escena.orden}: {err}')

            if img_path:
                clip_out = clips_dir / f'escena_{escena.orden:02d}.mp4'
                if construir_clip_escena(
                    imagen_path=img_path,
                    audio_path=audio_path,
                    tipo=escena.tipo,
                    duracion_objetivo=escena.duracion_seg,
                    salida=clip_out,
                ):
                    clips.append(clip_out)
                    meta['clip'] = str(clip_out)
                else:
                    run.errors.append(f'Clip ffmpeg falló escena {escena.orden}')

            from core.course_engine.types import Scene

            escenas_out.append(
                Scene(
                    orden=escena.orden,
                    tipo=escena.tipo,
                    titulo=escena.titulo,
                    guion=escena.guion,
                    duracion_seg=escena.duracion_seg,
                    notas_visuales=escena.notas_visuales,
                    asset_url=asset_url,
                    asset_s3_key=escena.asset_s3_key,
                    metadata=meta,
                )
            )

        from core.course_engine.types import Storyboard

        sb = Storyboard(
            titulo_leccion=sb.titulo_leccion,
            objetivo=sb.objetivo,
            escenas=escenas_out,
            modelo_ia=sb.modelo_ia,
        )

        result.costo_real_usd = costo_real
        run.storyboard = sb

        if not clips:
            run.errors.append('Sin clips — video no generado')
            guardar_run(run)
            return result

        result.pasos.append('Componiendo video…')
        final_local = run_dir / 'compose' / 'video_final.mp4'
        if not concatenar_clips(clips, final_local):
            run.errors.append('Concat ffmpeg falló')
            guardar_run(run)
            return result

        result.video_local = final_local
        url = subir_video_s3(final_local, run_id)
        if url:
            run.video_url = url
            result.pasos.append('✓ Video listo')
        else:
            run.errors.append('MP4 local OK pero falló upload S3')
            result.pasos.append('✓ Video local (S3 pendiente)')

        guardar_run(run)
        result.run = run
        return result
