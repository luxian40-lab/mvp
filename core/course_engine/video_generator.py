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
    promover_escena_runway,
    validar_presupuesto,
)
from core.course_engine.clip_builder import (
    concatenar_clips,
    construir_clip_desde_video_ia,
    construir_clip_escena,
)
from core.course_engine.compose import subir_video_s3
from core.course_engine.image_service import generar_imagen_escena
from core.course_engine.lesson import generar_leccion
from core.course_engine.local_store import guardar_run, local_runs_root
from core.course_engine.rag_source import obtener_contexto_rag_empresa, resumen_documentos_curso
from core.course_engine.prompt_context import prompt_runway_escena
from core.course_engine.runway_service import generar_video_desde_imagen, runway_disponible
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
        modulo_id: Optional[int] = None,
        voice_id: Optional[str] = None,
        run_id: Optional[str] = None,
        visual_style: str = '',
        runway_duration_sec: Optional[int] = None,
        micro_realista: bool = False,
        _lesson=None,
        _analysis=None,
    ) -> VideoGenerateResult:
        voice_label = ''
        if modulo_id:
            from core.models import Modulo
            from core.course_engine.voice_config import config_modulo

            modulo = Modulo.objects.select_related('curso').filter(pk=modulo_id).first()
            if modulo:
                cfg = config_modulo(modulo)
                tier = cfg['tier']
                voice_id = voice_id or cfg['voice_id']
                voice_label = cfg['voice_label']
                if not brief.strip():
                    brief = (modulo.titulo or modulo.descripcion or '')[:500]

        run_id = (run_id or uuid.uuid4().hex[:12])[:12]
        run_dir = local_runs_root() / run_id
        run = CourseEngineRun(
            run_id=run_id,
            cliente_id=cliente_id,
            curso_id=curso_id,
            brief=brief.strip(),
        )
        result = VideoGenerateResult(run=run)
        if voice_label:
            result.pasos.append(f'Voz: {voice_label}')
        result.pasos.append(f'Tier: {tier}')

        estilo = (visual_style or getattr(settings, 'COURSE_ENGINE_VISUAL_STYLE', '') or '').strip()
        runway_dur = runway_duration_sec or int(getattr(settings, 'RUNWAY_DURATION_SEC', 4) or 4)
        runway_dur = max(2, min(10, int(runway_dur)))

        if micro_realista:
            return self._generar_micro_realista(
                result=result,
                run=run,
                run_dir=run_dir,
                brief=brief.strip(),
                voice_id=voice_id,
                estilo=estilo or 'documental',
                runway_dur=runway_dur,
                dry_run=dry_run,
            )

        if _lesson is not None:
            lesson = _lesson
            run.lesson = lesson
            result.pasos.append('Leccion (bundle compartida)...')
            analysis = _analysis if _analysis is not None else analizar_leccion(lesson, modelo=modelo)
            if not analysis:
                run.errors.append('Falló analizador')
                guardar_run(run)
                return result
            run.analysis = analysis
        else:
            result.pasos.append('Analizando leccion...')
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

        result.pasos.append('Creando storyboard...')
        sb = generar_storyboard(lesson, analysis, modelo=modelo, tier=tier)
        if not sb:
            run.errors.append('Falló storyboard')
            guardar_run(run)
            return result

        sb = aplicar_limites_storyboard(sb, tier)
        sb = promover_escena_runway(sb, tier)
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

        result.pasos.append('Generando imagenes...')
        costo_real = 0.0
        clips_dir = run_dir / 'clips'
        clips: list[Path] = []
        escenas_out = []
        img_by_orden: dict[int, Path] = {}
        img_meta_by_orden: dict[int, dict] = {}
        runway_by_orden: dict[int, Path] = {}
        lesson_title = (run.lesson.titulo if run.lesson else '') or (sb.titulo_leccion if sb else '')
        lesson_objetivo = (sb.objetivo if sb else '') or brief

        for escena in sb.escenas:
            if escena.tipo in _SKIP_IMAGE:
                continue
            img_res = generar_imagen_escena(
                escena,
                run_dir,
                titulo_leccion=lesson_title,
                objetivo=lesson_objetivo,
                brief=brief,
                estilo=estilo,
            )
            if not img_res:
                run.errors.append(f'Imagen fallo escena {escena.orden} — abortado (fail-fast)')
                guardar_run(run)
                return result
            img_by_orden[escena.orden] = img_res.local_path
            costo_real += img_res.cost_usd
            meta = {'image_local': str(img_res.local_path)}
            if img_res.url:
                meta['image_url'] = img_res.url
            img_meta_by_orden[escena.orden] = meta

        if runway_disponible():
            for escena in sb.escenas:
                if escena.tipo != SceneType.VIDEO_IA:
                    continue
                img_path = img_by_orden.get(escena.orden)
                if not img_path:
                    run.errors.append(f'video_ia escena {escena.orden} sin keyframe')
                    continue
                prompt = prompt_runway_escena(
                    escena,
                    titulo_leccion=lesson_title,
                    objetivo=lesson_objetivo,
                    brief=brief,
                    storyboard=sb,
                    estilo=estilo,
                )
                rw_model = 'gen4_turbo' if estilo == 'documental' else None
                rv = generar_video_desde_imagen(
                    prompt=prompt,
                    run_dir=run_dir,
                    escena_orden=escena.orden,
                    local_image=img_path,
                    duration_sec=runway_dur,
                    model=rw_model,
                )
                if rv:
                    runway_by_orden[escena.orden] = rv.local_path
                    costo_real += rv.cost_usd
                    img_meta_by_orden.setdefault(escena.orden, {})['runway_local'] = str(rv.local_path)
                    img_meta_by_orden[escena.orden]['runway_model'] = rv.model
                    img_meta_by_orden[escena.orden]['runway_prompt'] = prompt[:500]
                else:
                    run.errors.append(f'Runway fallo escena {escena.orden} — fallback imagen_zoom')

        result.pasos.append('Generando audio y clips...')
        for escena in sb.escenas:
            meta = dict(escena.metadata)
            meta.update(img_meta_by_orden.get(escena.orden, {}))
            img_path: Optional[Path] = img_by_orden.get(escena.orden)
            audio_path: Optional[Path] = None
            asset_url = escena.asset_url

            guion = (escena.guion or escena.titulo or '').strip()
            if guion:
                audio_dest = run_dir / 'audio' / f'escena_{escena.orden:02d}.mp3'
                tts = generar_narracion_archivo(guion, audio_dest, voice=voice_id)
                if tts:
                    audio_path = audio_dest
                    meta['tts_provider'] = tts.provider
                    asset_url = tts.url or asset_url
                else:
                    err = ultimo_error_tts() or 'TTS falló'
                    run.errors.append(f'Audio escena {escena.orden}: {err}')

            if runway_by_orden.get(escena.orden):
                clip_out = clips_dir / f'escena_{escena.orden:02d}.mp4'
                if construir_clip_desde_video_ia(
                    video_path=runway_by_orden[escena.orden],
                    audio_path=audio_path,
                    salida=clip_out,
                    duracion_objetivo=escena.duracion_seg,
                ):
                    clips.append(clip_out)
                    meta['clip'] = str(clip_out)
                    meta['video_ia'] = True
                else:
                    run.errors.append(f'Clip video_ia ffmpeg fallo escena {escena.orden}')
            elif img_path:
                clip_out = clips_dir / f'escena_{escena.orden:02d}.mp4'
                overlay = ''
                if escena.tipo in {SceneType.TEXTO, SceneType.RESUMEN}:
                    overlay = guion
                clip_tipo = SceneType.IMAGEN_ZOOM if escena.tipo == SceneType.VIDEO_IA else escena.tipo
                if construir_clip_escena(
                    imagen_path=img_path,
                    audio_path=audio_path,
                    tipo=clip_tipo,
                    duracion_objetivo=escena.duracion_seg,
                    salida=clip_out,
                    overlay_text=overlay,
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

        result.pasos.append('Componiendo video...')
        final_local = run_dir / 'compose' / 'video_final.mp4'
        if not concatenar_clips(clips, final_local):
            run.errors.append('Concat ffmpeg falló')
            guardar_run(run)
            return result

        result.video_local = final_local
        url = subir_video_s3(final_local, run_id)
        if url:
            run.video_url = url
            result.pasos.append('OK Video listo')
        else:
            run.errors.append('MP4 local OK pero fallo upload S3')
            result.pasos.append('OK Video local (S3 pendiente)')

        guardar_run(run)
        result.run = run
        return result

    def _generar_micro_realista(
        self,
        *,
        result: VideoGenerateResult,
        run: CourseEngineRun,
        run_dir: Path,
        brief: str,
        voice_id: Optional[str],
        estilo: str,
        runway_dur: int,
        dry_run: bool,
    ) -> VideoGenerateResult:
        """Un clip corto: keyframe foto documental + Runway + ElevenLabs."""
        from core.course_engine.keyframe_documental import generar_keyframe_documental
        from core.course_engine.visual_style import prompt_runway_documental

        if not brief.strip():
            run.errors.append('Modo micro-realista requiere --brief o --modulo-id')
            guardar_run(run)
            return result

        result.pasos.append(
            f'Micro clip realista {runway_dur}s · estilo {estilo} · Runway + ElevenLabs'
        )
        result.costo_estimado_usd = 0.35 + (runway_dur * 0.05)

        if dry_run:
            result.pasos.append(f'Dry-run OK — est. ${result.costo_estimado_usd:.2f}')
            guardar_run(run)
            return result

        if getattr(settings, 'COURSE_ENGINE_DRY_RUN', False):
            run.errors.append('COURSE_ENGINE_DRY_RUN=true — abortado antes de APIs de pago')
            guardar_run(run)
            return result

        if not runway_disponible():
            run.errors.append('RUNWAY_API_KEY no configurada')
            guardar_run(run)
            return result

        run_dir.mkdir(parents=True, exist_ok=True)
        costo = 0.0

        result.pasos.append('Keyframe documental (OpenAI)...')
        img_path = generar_keyframe_documental(run_dir, tema=brief)
        if not img_path:
            run.errors.append('Keyframe documental falló — revisa OPENAI_API_KEY')
            guardar_run(run)
            return result
        costo += 0.04

        result.pasos.append(f'Runway image-to-video {runway_dur}s (gen4_turbo)...')
        rw_prompt = prompt_runway_documental(tema=brief)
        rv = generar_video_desde_imagen(
            prompt=rw_prompt,
            run_dir=run_dir,
            escena_orden=1,
            local_image=img_path,
            duration_sec=runway_dur,
            model='gen4_turbo',
        )
        if not rv:
            run.errors.append('Runway falló — revisa logs')
            guardar_run(run)
            return result
        costo += rv.cost_usd

        guion = brief.strip()
        words = guion.split()
        if len(words) > 16:
            guion = ' '.join(words[:16]).rstrip(',;:') + '.'

        audio_path: Optional[Path] = None
        if guion:
            result.pasos.append('ElevenLabs narración corta...')
            audio_dest = run_dir / 'audio' / 'micro.mp3'
            audio_dest.parent.mkdir(parents=True, exist_ok=True)
            tts = generar_narracion_archivo(guion, audio_dest, voice=voice_id)
            if tts:
                audio_path = audio_dest
                costo += 0.05
            else:
                err = ultimo_error_tts() or 'TTS falló'
                run.errors.append(f'ElevenLabs: {err}')

        clip_out = run_dir / 'clips' / 'micro_realista.mp4'
        clip_out.parent.mkdir(parents=True, exist_ok=True)
        if not construir_clip_desde_video_ia(
            video_path=rv.local_path,
            audio_path=audio_path,
            salida=clip_out,
            duracion_objetivo=float(runway_dur),
        ):
            run.errors.append('ffmpeg no pudo armar el clip')
            guardar_run(run)
            return result

        final_local = run_dir / 'compose' / 'video_final.mp4'
        final_local.parent.mkdir(parents=True, exist_ok=True)
        if not concatenar_clips([clip_out], final_local):
            run.errors.append('ffmpeg concat falló')
            guardar_run(run)
            return result

        result.costo_real_usd = costo
        result.video_local = final_local
        url = subir_video_s3(final_local, run.run_id)
        if url:
            run.video_url = url
            result.pasos.append('OK Video listo')
        else:
            result.pasos.append('OK Video local (S3 pendiente)')

        guardar_run(run)
        return result
