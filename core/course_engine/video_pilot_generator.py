"""Generador piloto — un MP4 WA (escena + tarjeta + voz + subtítulos)."""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from django.conf import settings

from core.course_engine.clip_builder import (
    _audio_duration_sec,
    concatenar_clips,
    construir_segmento_imagen,
    construir_segmento_tarjeta_animada,
    construir_segmento_video_ia,
    recortar_video_duracion,
)
from core.course_engine.compose import subir_video_s3
from core.course_engine.infographic_card import generar_frames_tarjeta_animada, generar_tarjeta_infografica
from core.course_engine.keyframe_documental import generar_keyframe_documental
from core.course_engine.local_store import local_runs_root
from core.course_engine.rag_source import obtener_contexto_rag_empresa, resumen_documentos_curso
from core.course_engine.runway_service import generar_video_desde_imagen, runway_disponible
from core.course_engine.tts import generar_narracion_archivo, ultimo_error_tts
from core.course_engine.video_storyboard import (
    SegmentoStoryboard,
    VideoLeccionPlan,
    planificar_video_leccion,
)
from core.course_engine.visual_style import inferir_categoria_visual, prompt_runway_documental

logger = logging.getLogger(__name__)

# Foco piloto — error 1 del manual de rentabilidad
FOCO_PILOTO_ERROR1 = (
    'Error 1: No rendir cuentas entre los socios — sin reportes de ingresos y gastos '
    'el flujo de efectivo puede enmascarar una quiebra técnica.'
)


@dataclass
class PasoVideoWA:
    """Un solo envío WA — video con caption mínimo (sin ráfaga de texto)."""
    orden: int
    titulo: str
    caption: str
    media_url: str = ''
    formato_wa: str = 'video/mp4'

    def to_dict(self) -> dict:
        return {
            'orden': self.orden,
            'tipo': 'video',
            'titulo': self.titulo,
            'caption': self.caption,
            'contenido': self.caption,
            'media_url': self.media_url,
            'formato_wa': self.formato_wa,
        }


@dataclass
class VideoPilotResult:
    run_id: str
    plan: Optional[VideoLeccionPlan]
    paso_wa: Optional[PasoVideoWA] = None
    video_local: Optional[Path] = None
    voice_id: str = ''
    costo_estimado_usd: float = 0.0
    costo_real_usd: float = 0.0
    pasos: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    manifest_path: Optional[Path] = None


def _estimar_costo() -> float:
    return round(0.04 + 0.55 + 0.05 + 0.04, 2)  # keyframe + runway + tts + lámina IA


def _construir_segmento(
    *,
    run_dir: Path,
    seg: SegmentoStoryboard,
    audio_path: Optional[Path],
    video_escena: Optional[Path],
    video_cierre: Optional[Path],
    tarjeta_path: Optional[Path],
    tarjeta_frames: Optional[list[Path]] = None,
    orden: int,
) -> tuple[Optional[Path], list[str]]:
    errores: list[str] = []
    clips_dir = run_dir / 'segments'
    clips_dir.mkdir(parents=True, exist_ok=True)
    if not audio_path or not audio_path.is_file():
        errores.append(f'Segmento {orden}: audio TTS faltante')
        return None, errores

    salida = clips_dir / f'seg_{orden:02d}.mp4'
    dur = _audio_duration_sec(audio_path)
    # Subtítulo = lo que dice la voz en este tramo (no el titular corto del storyboard)
    subt = (seg.guion or seg.subtitulo or '').strip()

    if seg.tipo == 'tarjeta':
        if tarjeta_frames and len(tarjeta_frames) >= 2:
            ok = construir_segmento_tarjeta_animada(
                frames=tarjeta_frames,
                audio_path=audio_path,
                salida=salida,
            )
        elif tarjeta_path and tarjeta_path.is_file():
            ok = construir_segmento_imagen(
                imagen_path=tarjeta_path,
                audio_path=audio_path,
                salida=salida,
                duracion_seg=dur,
                subtitulo='',
                zoom=False,
            )
        else:
            errores.append(f'Segmento {orden}: tarjeta infográfica no generada')
            return None, errores
    elif seg.tipo == 'escena_cierre' and video_cierre and video_cierre.is_file():
        ok = construir_segmento_video_ia(
            video_path=video_cierre,
            audio_path=audio_path,
            salida=salida,
            duracion_seg=dur,
            subtitulo=subt,
        )
    elif video_escena and video_escena.is_file():
        ok = construir_segmento_video_ia(
            video_path=video_escena,
            audio_path=audio_path,
            salida=salida,
            duracion_seg=dur,
            subtitulo=subt,
        )
    else:
        kf = run_dir / 'images' / 'keyframe_fallback.png'
        if kf.is_file():
            ok = construir_segmento_imagen(
                imagen_path=kf,
                audio_path=audio_path,
                salida=salida,
                duracion_seg=dur,
                subtitulo=subt,
                zoom=False,
            )
        else:
            errores.append(f'Segmento {orden}: sin video ni keyframe')
            return None, errores

    if not ok:
        errores.append(f'Segmento {orden}: ffmpeg falló')
        return None, errores
    return salida, errores


class VideoPilotGenerator:
    """Brief + RAG → un MP4 con escena, tarjeta infográfica, voz y subtítulos."""

    def generar(
        self,
        *,
        cliente_id: int,
        curso_id: int,
        brief: str,
        modulo_id: Optional[int] = None,
        voice_id: Optional[str] = None,
        foco: str = '',
        dry_run: bool = False,
        generar_video: bool = True,
        target_sec: float = 14.0,
        runway_duration_sec: int = 5,
        modo_demo: bool = False,
        max_duracion_seg: Optional[float] = None,
    ) -> VideoPilotResult:
        from core.models import Modulo

        brief = (brief or '').strip()
        if modulo_id:
            mod = Modulo.objects.select_related('curso').filter(pk=modulo_id).first()
            if mod and not brief:
                brief = (mod.titulo or mod.descripcion or '')[:8000]
            if mod and not voice_id:
                from core.course_engine.voice_config import config_modulo

                voice_id = config_modulo(mod).get('voice_id')

        run_id = uuid.uuid4().hex[:12]
        run_dir = local_runs_root() / run_id
        result = VideoPilotResult(run_id=run_id, plan=None, costo_estimado_usd=_estimar_costo())
        if modo_demo:
            result.pasos.append(f'Modo demo studio — máx {max_duracion_seg or target_sec:.0f}s')

        if not brief:
            result.errors.append('Brief vacío')
            return result

        result.pasos.append('RAG empresa/curso...')
        rag_ctx, rag_ok = obtener_contexto_rag_empresa(cliente_id, curso_id, brief)
        if not rag_ok:
            fb = resumen_documentos_curso(curso_id)
            rag_ctx = fb or ''
            result.pasos.append('RAG Chroma vacío — fallback documentos' if fb else 'Sin RAG — solo brief')
        else:
            result.pasos.append(f'RAG OK ({len(rag_ctx)} chars)')

        foco_txt = (foco or FOCO_PILOTO_ERROR1).strip()
        result.pasos.append('Planificando storyboard video único...')
        plan = planificar_video_leccion(
            brief,
            rag_ctx,
            foco=foco_txt,
            target_sec=target_sec,
        )
        if not plan:
            result.errors.append('Falló planificación storyboard')
            return result

        result.plan = plan
        result.pasos.append(
            f'Plan: {plan.titulo} — {len(plan.segmentos)} segmentos (~{plan.duracion_objetivo_seg:.0f}s)'
        )

        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / 'video_plan.json').write_text(
            json.dumps(plan.to_dict(), ensure_ascii=False, indent=2),
            encoding='utf-8',
        )

        if dry_run or getattr(settings, 'COURSE_ENGINE_DRY_RUN', False):
            result.pasos.append('Dry-run — manifest sin APIs de pago')
            result.paso_wa = PasoVideoWA(
                orden=1,
                titulo=plan.titulo,
                caption=f'[eki video] {plan.titulo}',
            )
            result.manifest_path = self._write_manifest(run_dir, result, brief)
            return result

        if not generar_video:
            result.pasos.append('generar_video=False — solo plan guardado')
            result.manifest_path = self._write_manifest(run_dir, result, brief)
            return result

        costo = 0.0
        guion = plan.guion_completo or ' '.join(s.guion for s in plan.segmentos)

        # 1) TTS por segmento — voz y subtítulo alineados al mismo guion
        from core.course_engine.voice_config import label_voz, resolver_voice_id_curso
        from core.models import Curso

        # Sin modulo (o modulo sin voz) manda la voz elegida en el curso; solo si
        # tampoco hay, cae al default del entorno.
        if not voice_id and curso_id:
            curso_obj = Curso.objects.filter(pk=curso_id).first()
            if curso_obj:
                voice_id = resolver_voice_id_curso(curso_obj)

        result.voice_id = voice_id or ''
        result.pasos.append(
            f'Narración TTS con voz: {label_voz(voice_id) or voice_id or "default entorno"}'
        )
        audios_seg: dict[int, Path] = {}
        audio_dir = run_dir / 'audio'
        audio_dir.mkdir(parents=True, exist_ok=True)
        for i, seg in enumerate(plan.segmentos, start=1):
            texto = (seg.guion or '').strip()
            if not texto:
                result.errors.append(f'Segmento {i}: guion vacío')
                continue
            dest = audio_dir / f'seg_{i:02d}.mp3'
            tts = generar_narracion_archivo(texto, dest, voice=voice_id)
            if tts and dest.is_file():
                audios_seg[i] = dest
                costo += 0.05
            else:
                result.errors.append(f'Segmento {i} TTS — {ultimo_error_tts() or "?"}')

        if len(audios_seg) < len(plan.segmentos):
            result.manifest_path = self._write_manifest(run_dir, result, brief)
            return result

        audio_dur = sum(_audio_duration_sec(p) for p in audios_seg.values())
        result.pasos.append(f'Audio OK — {audio_dur:.1f}s ({len(audios_seg)} segmentos)')

        # 2) Keyframe + Runway (escena apertura y cierre)
        video_escena: Optional[Path] = None
        video_cierre: Optional[Path] = None
        keyframe_apertura: Optional[Path] = None
        seg_escena = next((s for s in plan.segmentos if s.tipo == 'escena'), None)
        seg_cierre = next((s for s in plan.segmentos if s.tipo == 'escena_cierre'), None)

        if runway_disponible():
            for label, seg in (('apertura', seg_escena), ('cierre', seg_cierre)):
                if not seg:
                    continue
                cat = plan.categoria_visual or inferir_categoria_visual(plan.titulo + guion)
                result.pasos.append(f'Keyframe + Runway ({label})...')
                img = generar_keyframe_documental(
                    run_dir,
                    tema=plan.titulo,
                    escena_visual=seg.escena_visual,
                    categoria_visual=cat,
                )
                if not img:
                    result.errors.append(f'Keyframe {label} falló')
                    continue
                if label == 'apertura':
                    keyframe_apertura = img
                costo += 0.04
                rw = generar_video_desde_imagen(
                    prompt=prompt_runway_documental(
                        tema=plan.titulo,
                        escena_visual=seg.escena_visual,
                        categoria_visual=cat,
                    ),
                    run_dir=run_dir,
                    escena_orden=seg.orden,
                    local_image=img,
                    duration_sec=max(2, min(10, int(runway_duration_sec))),
                    model='gen4_turbo',
                )
                if rw:
                    costo += rw.cost_usd
                    if label == 'apertura':
                        video_escena = rw.local_path
                    else:
                        video_cierre = rw.local_path
                else:
                    result.errors.append(f'Runway {label} falló')
        else:
            result.errors.append('RUNWAY_API_KEY no configurada — solo keyframe estático')
            cat = plan.categoria_visual or 'finanzas'
            kf = generar_keyframe_documental(
                run_dir,
                tema=plan.titulo,
                escena_visual=seg_escena.escena_visual if seg_escena else '',
                categoria_visual=cat,
            )
            if kf:
                costo += 0.04

        # 3) Tarjeta infográfica
        seg_tarjeta = next((s for s in plan.segmentos if s.tipo == 'tarjeta'), None)
        tarjeta_path: Optional[Path] = None
        tarjeta_frames: list[Path] = []
        if seg_tarjeta:
            tarjeta_idx = next(
                (i for i, s in enumerate(plan.segmentos, start=1) if s.tipo == 'tarjeta'),
                None,
            )
            tarjeta_dur = (
                _audio_duration_sec(audios_seg[tarjeta_idx])
                if tarjeta_idx and audios_seg.get(tarjeta_idx)
                else float(seg_tarjeta.duracion_seg or 6.0)
            )
            result.pasos.append(
                f'Generando lámina Platzi 16:9 ({tarjeta_dur:.1f}s — guion + puntos)...'
            )
            tarjeta_path = run_dir / 'images' / 'tarjeta_infografica.png'
            anim_dir = run_dir / 'images' / 'tarjeta_anim'
            tarjeta_frames = generar_frames_tarjeta_animada(
                titulo=seg_tarjeta.tarjeta_titulo or seg_tarjeta.titulo or plan.titulo,
                puntos=seg_tarjeta.tarjeta_puntos,
                guion=(seg_tarjeta.guion or '').strip(),
                salida_dir=anim_dir,
                fondo_imagen=keyframe_apertura,
                run_dir=run_dir,
                escena_visual=seg_tarjeta.escena_visual or (seg_escena.escena_visual if seg_escena else ''),
                categoria_visual=plan.categoria_visual,
                usar_fondo_ia=False,
                estilo='platzi',
                duracion_seg=tarjeta_dur,
            )
            if tarjeta_frames:
                tarjeta_path = tarjeta_frames[-1]
                costo += 0.04
            elif generar_tarjeta_infografica(
                titulo=seg_tarjeta.tarjeta_titulo or seg_tarjeta.titulo or plan.titulo,
                puntos=seg_tarjeta.tarjeta_puntos,
                salida=tarjeta_path,
                fondo_imagen=keyframe_apertura,
                run_dir=run_dir,
                escena_visual=seg_tarjeta.escena_visual or (seg_escena.escena_visual if seg_escena else ''),
                categoria_visual=plan.categoria_visual,
                usar_fondo_ia=True,
            ):
                costo += 0.04
            else:
                result.errors.append('Tarjeta infográfica falló')

        # 4) Componer segmentos
        result.pasos.append('Componiendo segmentos ffmpeg...')
        clips: list[Path] = []
        for i, seg in enumerate(plan.segmentos, start=1):
            clip_path, errs = _construir_segmento(
                run_dir=run_dir,
                seg=seg,
                audio_path=audios_seg.get(i),
                video_escena=video_escena,
                video_cierre=video_cierre,
                tarjeta_path=tarjeta_path,
                tarjeta_frames=tarjeta_frames or None,
                orden=i,
            )
            result.errors.extend(errs)
            if clip_path:
                clips.append(clip_path)

        if not clips:
            result.errors.append('Sin segmentos generados')
            result.costo_real_usd = round(costo, 2)
            result.manifest_path = self._write_manifest(run_dir, result, brief)
            return result

        if len(clips) < len(plan.segmentos):
            result.errors.append(
                f'Video incompleto: {len(clips)}/{len(plan.segmentos)} segmentos — no se envía WA'
            )
            result.costo_real_usd = round(costo, 2)
            result.manifest_path = self._write_manifest(run_dir, result, brief)
            return result

        final_path = run_dir / 'video_leccion_wa.mp4'
        if len(clips) == 1:
            final_path = clips[0]
        elif not concatenar_clips(clips, final_path):
            result.errors.append('Concatenación ffmpeg falló')
            result.costo_real_usd = round(costo, 2)
            result.manifest_path = self._write_manifest(run_dir, result, brief)
            return result

        cap = max_duracion_seg if max_duracion_seg and max_duracion_seg > 0 else None
        if cap and final_path.is_file():
            dur_actual = _audio_duration_sec(final_path)
            if dur_actual > cap + 0.15:
                trimmed = run_dir / 'video_leccion_wa_trim.mp4'
                if recortar_video_duracion(final_path, trimmed, max_seg=cap):
                    final_path = trimmed
                    result.pasos.append(f'Demo recortado a {cap:.0f}s')

        result.video_local = final_path
        result.pasos.append(f'Video local OK — {final_path.name}')

        # 5) Subir S3 + gate WA
        url = subir_video_s3(final_path, run_id)
        if not url:
            result.errors.append('Gate WA / S3 falló')
        else:
            result.paso_wa = PasoVideoWA(
                orden=1,
                titulo=plan.titulo,
                caption=f'[eki video] {plan.titulo}',
                media_url=url,
            )
            result.pasos.append('Video subido S3 — apto WA')

        result.costo_real_usd = round(costo, 2)
        result.manifest_path = self._write_manifest(run_dir, result, brief)
        result.pasos.append(f'Piloto OK — ${result.costo_real_usd:.2f}')
        return result

    def _write_manifest(
        self,
        run_dir: Path,
        result: VideoPilotResult,
        brief: str,
    ) -> Path:
        manifest = {
            'run_id': result.run_id,
            'tipo': 'video_leccion_unico',
            'brief_chars': len(brief),
            'voice_id': result.voice_id,
            'plan': result.plan.to_dict() if result.plan else None,
            'costo_estimado_usd': result.costo_estimado_usd,
            'costo_real_usd': result.costo_real_usd,
            'paso_wa': result.paso_wa.to_dict() if result.paso_wa else None,
            'video_local': str(result.video_local) if result.video_local else None,
            'errors': result.errors,
        }
        path = run_dir / 'video_pilot_manifest.json'
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        return path
