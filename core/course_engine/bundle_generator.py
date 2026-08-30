"""Generador paquete mixto — video + infografía + podcast (1 run, 1 lección RAG)."""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from django.conf import settings

from core.course_engine.analyzer import analizar_leccion
from core.course_engine.budget import COST_IMAGE_USD
from core.course_engine.bundle import ModuloMixtoPlan, estimar_costo_modulo_mixto
from core.course_engine.compose import subir_asset_s3
from core.course_engine.format_config import (
    FORMAT_PASOS_WA,
    describe_formato,
    plan_desde_curso,
    resolver_formato_curso,
    resolver_podcast_minutos,
)
from core.course_engine.image_service import generar_imagen_escena
from core.course_engine.lesson import generar_leccion
from core.course_engine.local_store import local_runs_root
from core.course_engine.podcast_script import generar_guion_podcast
from core.course_engine.rag_source import obtener_contexto_rag_empresa, resumen_documentos_curso
from core.course_engine.tts import generar_narracion_archivo, ultimo_error_tts
from core.course_engine.types import Scene, SceneType
from core.course_engine.video_generator import CourseVideoGenerator

logger = logging.getLogger(__name__)


@dataclass
class BundleAsset:
    tipo: str
    label: str
    url: str = ''
    local_path: str = ''
    paso_orden: int = 0


@dataclass
class BundleGenerateResult:
    run_id: str
    formato: str
    plan: ModuloMixtoPlan
    pasos_wa: list[dict] = field(default_factory=list)
    assets: list[BundleAsset] = field(default_factory=list)
    costo_estimado_usd: float = 0.0
    costo_real_usd: float = 0.0
    pasos: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    manifest_path: Optional[Path] = None


class CourseBundleGenerator:
    """Un módulo → paquete alineado al formato elegido en el curso."""

    def generar(
        self,
        *,
        cliente_id: int,
        curso_id: int,
        modulo_id: Optional[int] = None,
        brief: str = '',
        dry_run: bool = False,
        voice_id: Optional[str] = None,
        tier_override: Optional[str] = None,
        formato_override: Optional[str] = None,
    ) -> BundleGenerateResult:
        from core.models import Curso, Modulo

        curso = Curso.objects.filter(pk=curso_id).first()
        if not curso:
            return BundleGenerateResult(
                run_id='',
                formato='',
                plan=ModuloMixtoPlan(),
                errors=['Curso no encontrado'],
            )

        modulo = None
        if modulo_id:
            modulo = Modulo.objects.select_related('curso').filter(pk=modulo_id, curso_id=curso_id).first()
            if not modulo:
                return BundleGenerateResult(
                    run_id='',
                    formato=resolver_formato_curso(curso),
                    plan=ModuloMixtoPlan(),
                    errors=['Modulo no encontrado o no pertenece al curso'],
                )
            if not brief.strip():
                brief = (modulo.titulo or modulo.descripcion or '')[:500]

        if not brief.strip():
            return BundleGenerateResult(
                run_id='',
                formato=resolver_formato_curso(curso),
                plan=ModuloMixtoPlan(),
                errors=['Brief vacio — pasa --brief o --modulo-id'],
            )

        if formato_override or tier_override:
            from types import SimpleNamespace

            curso_plan = SimpleNamespace(
                course_engine_format=formato_override or curso.course_engine_format,
                course_engine_tier=tier_override or curso.course_engine_tier,
                course_engine_podcast_minutos=getattr(curso, 'course_engine_podcast_minutos', 2),
            )
        else:
            curso_plan = curso

        fmt = resolver_formato_curso(curso_plan)
        plan = plan_desde_curso(curso_plan, tier_override=tier_override)
        pasos_wa = FORMAT_PASOS_WA.get(fmt, [])
        run_id = uuid.uuid4().hex[:12]
        run_dir = local_runs_root() / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        result = BundleGenerateResult(
            run_id=run_id,
            formato=fmt,
            plan=plan,
            pasos_wa=pasos_wa,
            costo_estimado_usd=estimar_costo_modulo_mixto(plan).total_usd,
        )
        result.pasos.append(f'Formato: {describe_formato(curso_plan)}')
        result.pasos.append(f'Costo est. paquete: ${result.costo_estimado_usd:.2f}')

        if voice_id is None and modulo:
            from core.course_engine.voice_config import config_modulo

            voice_id = config_modulo(modulo).get('voice_id')
        elif voice_id is None:
            from core.course_engine.voice_config import resolver_voice_id_curso

            voice_id = resolver_voice_id_curso(curso)

        result.pasos.append('Leccion unica (RAG + brief)...')
        rag_ctx, rag_ok = obtener_contexto_rag_empresa(cliente_id, curso_id, brief)
        if not rag_ok:
            fb = resumen_documentos_curso(curso_id)
            if fb:
                rag_ctx = fb

        lesson = generar_leccion(brief, rag_ctx)
        if not lesson:
            result.errors.append('Fallo leccion OpenAI')
            return result

        analysis = analizar_leccion(lesson)
        if not analysis:
            result.errors.append('Fallo analizador')
            return result

        if dry_run:
            result.pasos.append('Dry-run OK — sin APIs de pago extra')
            self._write_manifest(run_dir, result, lesson.titulo, brief)
            return result

        if getattr(settings, 'COURSE_ENGINE_DRY_RUN', False):
            result.errors.append('COURSE_ENGINE_DRY_RUN=true')
            return result

        costo_real = 0.0
        paso_idx = 0

        # --- Video ---
        result.pasos.append('Generando video...')
        vgen = CourseVideoGenerator()
        vout = vgen.generar(
            cliente_id=cliente_id,
            curso_id=curso_id,
            brief=brief,
            tier=plan.tier_video,
            modulo_id=modulo_id,
            voice_id=voice_id,
            run_id=run_id,
            _lesson=lesson,
            _analysis=analysis,
        )
        costo_real += vout.costo_real_usd
        result.pasos.extend(vout.pasos)
        result.errors.extend(vout.run.errors)

        video_url = vout.run.video_url or ''
        video_local = str(vout.video_local) if vout.video_local else ''
        if video_url or video_local:
            paso_idx += 1
            result.assets.append(
                BundleAsset(
                    tipo='video',
                    label=pasos_wa[0]['label'] if pasos_wa else 'Video',
                    url=video_url,
                    local_path=video_local,
                    paso_orden=paso_idx,
                )
            )
        elif any(p['tipo'] == 'video' for p in pasos_wa):
            result.errors.append('Video requerido por formato pero no se genero')

        # --- Infografia ---
        if plan.incluir_infografia:
            result.pasos.append('Generando infografia...')
            puntos = '; '.join(lesson.puntos_clave[:4]) or lesson.titulo
            esc_inf = Scene(
                orden=99,
                tipo=SceneType.DIAGRAMA,
                titulo=f'Infografia: {lesson.titulo[:60]}',
                guion='',
                duracion_seg=0,
                notas_visuales=f'Infografia educativa una pagina: {puntos}',
            )
            img_res = generar_imagen_escena(
                esc_inf,
                run_dir,
                titulo_leccion=lesson.titulo,
                objetivo=getattr(analysis, 'recomendacion_formato', '') or brief,
                brief=brief,
            )
            if img_res:
                costo_real += img_res.cost_usd or COST_IMAGE_USD
                inf_url = img_res.url or subir_asset_s3(
                    img_res.local_path, run_id, ext='png', content_type='image/png', subpath='infografias',
                ) or ''
                paso_idx += 1
                result.assets.append(
                    BundleAsset(
                        tipo='infografia',
                        label=next((p['label'] for p in pasos_wa if p['tipo'] == 'infografia'), 'Infografia'),
                        url=inf_url,
                        local_path=str(img_res.local_path),
                        paso_orden=paso_idx,
                    )
                )
            else:
                result.errors.append('Infografia no generada')

        # --- Podcast ---
        if plan.incluir_podcast:
            result.pasos.append('Generando podcast...')
            mins = resolver_podcast_minutos(curso_plan)
            guion_pod = generar_guion_podcast(lesson, minutos_objetivo=mins)
            if not guion_pod:
                result.errors.append('Guion podcast vacio')
            else:
                pod_path = run_dir / 'podcast' / 'episodio.mp3'
                tts = generar_narracion_archivo(
                    guion_pod,
                    pod_path,
                    voice=voice_id,
                    voice_profile='podcast',
                )
                if tts:
                    pod_url = tts.url or subir_asset_s3(
                        pod_path, run_id, ext='mp3', content_type='audio/mpeg', subpath='podcasts',
                    ) or ''
                    paso_idx += 1
                    result.assets.append(
                        BundleAsset(
                            tipo='podcast',
                            label=next((p['label'] for p in pasos_wa if p['tipo'] == 'podcast'), 'Podcast'),
                            url=pod_url,
                            local_path=str(pod_path),
                            paso_orden=paso_idx,
                        )
                    )
                    (run_dir / 'podcast' / 'guion.txt').write_text(guion_pod, encoding='utf-8')
                else:
                    result.errors.append(f'Podcast TTS fallo: {ultimo_error_tts() or "?"}')

        result.costo_real_usd = round(costo_real, 2)
        result.manifest_path = self._write_manifest(run_dir, result, lesson.titulo, brief)
        result.pasos.append(f'Bundle OK — ${result.costo_real_usd:.2f} real (parcial video+extras)')
        return result

    def _write_manifest(
        self,
        run_dir: Path,
        result: BundleGenerateResult,
        titulo: str,
        brief: str,
    ) -> Path:
        manifest = {
            'run_id': result.run_id,
            'formato': result.formato,
            'titulo_leccion': titulo,
            'brief': brief,
            'costo_estimado_usd': result.costo_estimado_usd,
            'costo_real_usd': result.costo_real_usd,
            'pasos_wa_sugeridos': result.pasos_wa,
            'assets': [
                {
                    'paso_orden': a.paso_orden,
                    'tipo': a.tipo,
                    'label': a.label,
                    'url': a.url,
                    'local_path': a.local_path,
                }
                for a in sorted(result.assets, key=lambda x: x.paso_orden)
            ],
            'errors': result.errors,
        }
        path = run_dir / 'bundle_manifest.json'
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        return path
