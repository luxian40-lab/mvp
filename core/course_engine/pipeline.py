"""
Orquestador Course Engine — pipeline completo (local-first).

RAG empresa → OpenAI → lección → analizador → storyboard → assets → composición → S3
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import replace

from core.course_engine.analyzer import analizar_leccion
from core.course_engine.assets import generar_assets_storyboard
from core.course_engine.compose import componer_video_local, subir_video_s3
from core.course_engine.lesson import generar_leccion
from core.course_engine.local_store import guardar_run
from core.course_engine.rag_source import obtener_contexto_rag_empresa, resumen_documentos_curso
from core.course_engine.storyboard import generar_storyboard
from core.course_engine.types import CourseEngineRun

logger = logging.getLogger(__name__)


def ejecutar_pipeline_local(
    *,
    cliente_id: int,
    curso_id: int,
    brief: str,
    modelo: str = 'gpt-4o-mini',
    generar_audio: bool = True,
    hasta_paso: str = 'compose',
) -> CourseEngineRun:
    """
    Ejecuta el pipeline hasta `hasta_paso`:
    rag | lesson | analysis | storyboard | assets | compose
    """
    run_id = uuid.uuid4().hex[:12]
    run = CourseEngineRun(
        run_id=run_id,
        cliente_id=cliente_id,
        curso_id=curso_id,
        brief=brief.strip(),
    )

    # 1 — RAG empresa
    rag_ctx, rag_ok = obtener_contexto_rag_empresa(cliente_id, curso_id, brief)
    if not rag_ok:
        fallback = resumen_documentos_curso(curso_id)
        if fallback:
            rag_ctx = fallback
            run.errors.append('RAG vectorial no disponible — usando listado DocumentoRAG')
        else:
            run.errors.append('Sin RAG — lección solo desde brief')

    if hasta_paso == 'rag':
        guardar_run(run)
        return run

    # 2 — Lección
    lesson = generar_leccion(brief, rag_ctx, modelo=modelo)
    if not lesson:
        run.errors.append('Falló generación de lección')
        guardar_run(run)
        return run
    run = replace(run, lesson=lesson)

    if hasta_paso == 'lesson':
        guardar_run(run)
        return run

    # 3 — Analizador
    analysis = analizar_leccion(lesson, modelo=modelo)
    if not analysis:
        run.errors.append('Falló analizador pedagógico')
        guardar_run(run)
        return run
    run = replace(run, analysis=analysis)

    if hasta_paso == 'analysis':
        guardar_run(run)
        return run

    # 4 — Storyboard
    storyboard = generar_storyboard(lesson, analysis, modelo=modelo)
    if not storyboard:
        run.errors.append('Falló storyboard automático')
        guardar_run(run)
        return run
    run = replace(run, storyboard=storyboard)

    if hasta_paso == 'storyboard':
        guardar_run(run)
        return run

    # 5 — Assets (ElevenLabs narración + stubs visuales)
    from core.course_engine.local_store import local_runs_root

    run_dir = local_runs_root() / run_id
    storyboard = generar_assets_storyboard(
        storyboard,
        run_dir,
        generar_audio=generar_audio,
    )
    run = replace(run, storyboard=storyboard)

    if hasta_paso == 'assets':
        guardar_run(run)
        return run

    # 6 — Composición
    video_path, compose_warnings = componer_video_local(storyboard, run_dir)
    run.errors.extend(compose_warnings)
    if video_path:
        url = subir_video_s3(video_path, run_id)
        if url:
            run = replace(run, video_url=url)

    guardar_run(run)
    return run
