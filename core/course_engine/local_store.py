"""Persistencia local de runs (tmp/course_engine — gitignored)."""
from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings

from core.course_engine.types import CourseEngineRun


def local_runs_root() -> Path:
    base = getattr(settings, 'COURSE_ENGINE_LOCAL_DIR', None)
    if base:
        return Path(base)
    return Path(settings.BASE_DIR) / 'tmp' / 'course_engine' / 'runs'


def guardar_run(run: CourseEngineRun) -> Path:
    root = local_runs_root()
    run_dir = root / run.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / 'run.json'
    path.write_text(json.dumps(run.to_dict(), ensure_ascii=False, indent=2), encoding='utf-8')
    return run_dir


def cargar_run(run_id: str) -> CourseEngineRun | None:
    path = local_runs_root() / run_id / 'run.json'
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding='utf-8'))
    from core.course_engine.types import LessonAnalysis, LessonDraft, Storyboard

    run = CourseEngineRun(
        run_id=data['run_id'],
        cliente_id=int(data['cliente_id']),
        curso_id=int(data['curso_id']),
        brief=data.get('brief', ''),
        video_url=data.get('video_url'),
        errors=list(data.get('errors') or []),
    )
    if data.get('lesson'):
        ld = data['lesson']
        run.lesson = LessonDraft(
            titulo=ld['titulo'],
            contenido=ld['contenido'],
            puntos_clave=ld.get('puntos_clave') or [],
            rag_chars=int(ld.get('rag_chars') or 0),
        )
    if data.get('analysis'):
        a = data['analysis']
        run.analysis = LessonAnalysis(
            audiencia=a['audiencia'],
            duracion_estimada_min=int(a['duracion_estimada_min']),
            conceptos=a.get('conceptos') or [],
            riesgos_pedagogicos=a.get('riesgos_pedagogicos') or [],
            recomendacion_formato=a.get('recomendacion_formato', ''),
        )
    if data.get('storyboard'):
        run.storyboard = Storyboard.from_dict(data['storyboard'])
    return run
