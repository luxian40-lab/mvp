"""Genera secuencia interactiva: plan RAG + bloques texto + micro-videos WA."""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from django.conf import settings

from core.course_engine.brief_visual import ClipMicroPlan
from core.course_engine.clip_builder import construir_clip_desde_video_ia
from core.course_engine.compose import subir_video_s3
from core.course_engine.interactive_sequence import (
    BloqueInteractivo,
    SecuenciaInteractiva,
    generar_secuencia_interactiva,
)
from core.course_engine.keyframe_documental import generar_keyframe_documental
from core.course_engine.local_store import local_runs_root
from core.course_engine.rag_source import obtener_contexto_rag_empresa, resumen_documentos_curso
from core.course_engine.runway_service import generar_video_desde_imagen, runway_disponible
from core.course_engine.tts import generar_narracion_archivo, ultimo_error_tts
from core.course_engine.visual_style import inferir_categoria_visual, prompt_runway_documental

logger = logging.getLogger(__name__)


@dataclass
class PasoWA:
    orden: int
    tipo: str
    titulo: str
    contenido: str
    media_url: str = ''
    formato_wa: str = 'text/plain'

    def to_dict(self) -> dict:
        return {
            'orden': self.orden,
            'tipo': self.tipo,
            'titulo': self.titulo,
            'contenido': self.contenido,
            'media_url': self.media_url,
            'formato_wa': self.formato_wa,
        }


@dataclass
class InteractiveGenerateResult:
    run_id: str
    secuencia: Optional[SecuenciaInteractiva]
    pasos_wa: list[PasoWA] = field(default_factory=list)
    costo_estimado_usd: float = 0.0
    costo_real_usd: float = 0.0
    pasos: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    manifest_path: Optional[Path] = None


def _estimar_costo(secuencia: SecuenciaInteractiva) -> float:
    n_mv = sum(1 for b in secuencia.bloques if b.tipo == 'micro_video')
    return round(0.05 + n_mv * 0.55, 2)


def _generar_clip_micro(
    *,
    run_dir: Path,
    bloque: BloqueInteractivo,
    run_id: str,
    voice_id: Optional[str],
    runway_dur: int,
) -> tuple[Optional[Path], float, list[str]]:
    """Un micro_video: keyframe + Runway + TTS + ffmpeg."""
    errores: list[str] = []
    costo = 0.0
    target = max(float(runway_dur), float(bloque.duracion_seg))
    target = min(15.0, target)

    categoria = inferir_categoria_visual(f'{bloque.titulo} {bloque.guion} {bloque.escena_visual}')
    plan = ClipMicroPlan(
        titulo_corto=bloque.titulo,
        guion_narracion=bloque.guion,
        escena_visual=bloque.escena_visual or bloque.titulo,
        categoria_visual=categoria,
    )

    img_path = generar_keyframe_documental(
        run_dir,
        tema=plan.titulo_corto,
        escena_visual=plan.escena_visual,
        categoria_visual=plan.categoria_visual,
    )
    if not img_path:
        errores.append(f'Bloque {bloque.orden}: keyframe falló')
        return None, costo, errores
    costo += 0.04

    rw_prompt = prompt_runway_documental(
        tema=plan.titulo_corto,
        escena_visual=plan.escena_visual,
        categoria_visual=plan.categoria_visual,
    )
    rv = generar_video_desde_imagen(
        prompt=rw_prompt,
        run_dir=run_dir,
        escena_orden=bloque.orden,
        local_image=img_path,
        duration_sec=runway_dur,
        model='gen4_turbo',
    )
    if not rv:
        errores.append(f'Bloque {bloque.orden}: Runway falló')
        return None, costo, errores
    costo += rv.cost_usd

    audio_path = None
    if plan.guion_narracion:
        audio_dest = run_dir / 'audio' / f'bloque_{bloque.orden:02d}.mp3'
        audio_dest.parent.mkdir(parents=True, exist_ok=True)
        tts = generar_narracion_archivo(plan.guion_narracion, audio_dest, voice=voice_id)
        if tts:
            audio_path = audio_dest
            costo += 0.05
        else:
            errores.append(f'Bloque {bloque.orden}: TTS — {ultimo_error_tts() or "?"}')

    clip_out = run_dir / 'clips' / f'bloque_{bloque.orden:02d}.mp4'
    clip_out.parent.mkdir(parents=True, exist_ok=True)
    if not construir_clip_desde_video_ia(
        video_path=rv.local_path,
        audio_path=audio_path,
        salida=clip_out,
        duracion_objetivo=target,
    ):
        errores.append(f'Bloque {bloque.orden}: ffmpeg falló')
        return None, costo, errores

    return clip_out, costo, errores


class InteractiveSequenceGenerator:
    """Brief largo + RAG → secuencia WA (texto intercalado + micro-videos)."""

    def generar(
        self,
        *,
        cliente_id: int,
        curso_id: int,
        brief: str,
        modulo_id: Optional[int] = None,
        voice_id: Optional[str] = None,
        dry_run: bool = False,
        max_bloques: int = 12,
        max_micro_videos: int = 6,
        generar_micro_videos: int = 0,
        runway_duration_sec: int = 8,
    ) -> InteractiveGenerateResult:
        """
        generar_micro_videos: cuántos clips Runway generar (0 = solo plan/manifest).
        Útil para piloto: --plan-all --generate-videos 2
        """
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
        result = InteractiveGenerateResult(run_id=run_id, secuencia=None)

        if not brief:
            result.errors.append('Brief vacío')
            return result

        result.pasos.append('RAG empresa/curso...')
        rag_ctx, rag_ok = obtener_contexto_rag_empresa(cliente_id, curso_id, brief)
        if not rag_ok:
            fb = resumen_documentos_curso(curso_id)
            if fb:
                rag_ctx = fb
                result.pasos.append('RAG Chroma vacío — fallback lista documentos')
            else:
                result.pasos.append('Sin RAG — solo brief')
        else:
            result.pasos.append(f'RAG OK ({len(rag_ctx)} chars)')

        result.pasos.append('Planificando secuencia interactiva...')
        secuencia = generar_secuencia_interactiva(
            brief,
            rag_ctx,
            max_bloques=max_bloques,
            max_micro_videos=max_micro_videos,
        )
        if not secuencia:
            result.errors.append('Falló planificación secuencia')
            return result

        result.secuencia = secuencia
        result.costo_estimado_usd = _estimar_costo(secuencia)
        n_mv = sum(1 for b in secuencia.bloques if b.tipo == 'micro_video')
        n_txt = sum(1 for b in secuencia.bloques if b.tipo in ('texto', 'resumen'))
        result.pasos.append(
            f'Plan: {len(secuencia.bloques)} bloques ({n_txt} texto, {n_mv} micro_video) — '
            f'est. ${result.costo_estimado_usd:.2f}'
        )

        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / 'secuencia_plan.json').write_text(
            json.dumps(secuencia.to_dict(), ensure_ascii=False, indent=2),
            encoding='utf-8',
        )

        if dry_run or getattr(settings, 'COURSE_ENGINE_DRY_RUN', False):
            result.pasos.append('Dry-run — manifest sin APIs de pago')
            self._build_pasos_wa(result, secuencia, generated_urls={})
            result.manifest_path = self._write_manifest(run_dir, result, brief)
            return result

        costo_real = 0.0
        generated_urls: dict[int, str] = {}
        micro_generados = 0
        # 0 = solo plan/manifest; N>0 = generar hasta N clips Runway (piloto controlado).
        limite_gen = max(0, int(generar_micro_videos or 0))

        if limite_gen > 0 and not runway_disponible():
            result.errors.append('RUNWAY_API_KEY no configurada — solo texto en manifest')
            limite_gen = 0

        for bloque in secuencia.bloques:
            if bloque.tipo != 'micro_video':
                continue
            if micro_generados >= limite_gen:
                result.pasos.append(
                    f'Bloque {bloque.orden} micro_video — plan only (límite generate={limite_gen})'
                )
                continue

            result.pasos.append(f'Generando micro_video bloque {bloque.orden}: {bloque.titulo[:50]}...')
            clip_path, costo_b, errs = _generar_clip_micro(
                run_dir=run_dir,
                bloque=bloque,
                run_id=run_id,
                voice_id=voice_id,
                runway_dur=max(2, min(10, int(runway_duration_sec))),
            )
            costo_real += costo_b
            result.errors.extend(errs)
            if clip_path:
                url = subir_video_s3(clip_path, f'{run_id}_b{bloque.orden:02d}')
                if url:
                    generated_urls[bloque.orden] = url
                    micro_generados += 1
                    result.pasos.append(f'  OK bloque {bloque.orden} -> S3')
                else:
                    result.errors.append(f'Bloque {bloque.orden}: gate WA / S3 falló')

        result.costo_real_usd = round(costo_real, 2)
        self._build_pasos_wa(result, secuencia, generated_urls=generated_urls)
        result.manifest_path = self._write_manifest(run_dir, result, brief)
        result.pasos.append(f'Secuencia OK — ${result.costo_real_usd:.2f} real · {len(result.pasos_wa)} pasos WA')
        return result

    def _build_pasos_wa(
        self,
        result: InteractiveGenerateResult,
        secuencia: SecuenciaInteractiva,
        *,
        generated_urls: dict[int, str],
    ) -> None:
        paso_idx = 0
        for bloque in secuencia.bloques:
            paso_idx += 1
            if bloque.tipo == 'micro_video':
                url = generated_urls.get(bloque.orden, '')
                if url:
                    result.pasos_wa.append(
                        PasoWA(
                            orden=paso_idx,
                            tipo='video',
                            titulo=bloque.titulo,
                            contenido=bloque.guion,
                            media_url=url,
                            formato_wa='video/mp4',
                        )
                    )
                else:
                    # Plan sin asset aún: enviar narración como texto hasta generar clip.
                    result.pasos_wa.append(
                        PasoWA(
                            orden=paso_idx,
                            tipo='texto',
                            titulo=f'[video pendiente] {bloque.titulo}',
                            contenido=bloque.guion,
                            formato_wa='text/plain',
                        )
                    )
            else:
                result.pasos_wa.append(
                    PasoWA(
                        orden=paso_idx,
                        tipo='texto',
                        titulo=bloque.titulo,
                        contenido=bloque.guion,
                        formato_wa='text/plain',
                    )
                )

    def _write_manifest(
        self,
        run_dir: Path,
        result: InteractiveGenerateResult,
        brief: str,
    ) -> Path:
        manifest = {
            'run_id': result.run_id,
            'tipo': 'secuencia_interactiva',
            'brief_chars': len(brief),
            'secuencia': result.secuencia.to_dict() if result.secuencia else None,
            'costo_estimado_usd': result.costo_estimado_usd,
            'costo_real_usd': result.costo_real_usd,
            'pasos_wa': [p.to_dict() for p in result.pasos_wa],
            'errors': result.errors,
        }
        path = run_dir / 'interactive_manifest.json'
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        return path
