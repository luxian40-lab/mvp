"""API compartida Course Engine — Studio admin y portal."""
from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from django.core.cache import cache

logger = logging.getLogger(__name__)

_CACHE_PREFIX = 'ce_video_job:'
STUDIO_DEMO_MAX_SEC = 15.0
MAX_UPLOAD_MB = 200

_ESTADO_LABEL = {
    'pendiente': 'Indexando…',
    'indexado': 'Indexado',
    'error': 'Error',
}


def modulos_curso_json(curso) -> list[dict]:
    from core.models import Modulo

    return [
        {'id': m.id, 'numero': float(m.numero), 'titulo': m.titulo}
        for m in Modulo.objects.filter(curso=curso).order_by('numero', 'id')
    ]


def documentos_curso_json(curso, *, limite: int = 24) -> list[dict]:
    from core.models import DocumentoRAG

    filas = []
    for d in (
        DocumentoRAG.objects.filter(curso=curso)
        .order_by('-fecha_subida', '-id')
        .values('id', 'nombre', 'tipo', 'estado', 'chunks_indexados')[:limite]
    ):
        estado = d['estado'] or 'pendiente'
        filas.append(
            {
                'id': d['id'],
                'nombre': d['nombre'],
                'tipo': d['tipo'],
                'estado': estado,
                'estado_label': _ESTADO_LABEL.get(estado, estado),
                'chunks': d['chunks_indexados'] or 0,
            }
        )
    return filas


def subir_documentos_rag(curso, archivos, *, usuario=None) -> dict[str, Any]:
    """Sube material del curso al RAG; la indexación corre en segundo plano."""
    from portal.rag_curso_service import crear_documento_curso

    if not archivos:
        return {'ok': False, 'error': 'No hay archivos', 'status': 400}

    creados, errores = [], []
    for f in archivos:
        if f.size > MAX_UPLOAD_MB * 1024 * 1024:
            errores.append(f'{f.name}: supera {MAX_UPLOAD_MB} MB')
            continue
        try:
            doc = crear_documento_curso(
                curso,
                nombre=f.name.rsplit('.', 1)[0][:180],
                tipo='contenido',
                archivo=f,
                subido_por=usuario,
            )
            creados.append({'id': doc.pk, 'nombre': doc.nombre, 'estado': doc.estado})
        except ValueError as exc:
            errores.append(f'{f.name}: {exc}')
        except Exception:
            logger.exception('CE upload %s', f.name)
            errores.append(f'{f.name}: no se pudo guardar')

    return {
        'ok': bool(creados),
        'creados': creados,
        'errores': errores,
        'documentos': documentos_curso_json(curso),
        'status': 200 if creados else 400,
    }


def reindexar_documento(curso, doc_id) -> dict[str, Any]:
    from core.models import DocumentoRAG
    from portal.rag_curso_service import encolar_indexacion_rag_curso

    try:
        pk = int(doc_id or 0)
    except (TypeError, ValueError):
        pk = 0

    doc = DocumentoRAG.objects.filter(pk=pk, curso=curso).first()
    if not doc:
        return {'ok': False, 'error': 'Documento no encontrado', 'status': 404}

    doc.estado = 'pendiente'
    doc.save(update_fields=['estado'])
    encolar_indexacion_rag_curso(doc.pk)
    return {'ok': True, 'documentos': documentos_curso_json(curso), 'status': 200}


def voces_demo_curso(curso, *, request=None) -> list[dict]:
    from core.course_engine.voice_demos import catalogo_voces_demo

    return catalogo_voces_demo(curso=curso, request=request)


def set_voz_curso(curso, voice_id: str) -> dict[str, Any]:
    from core.course_engine.voice_config import catalogo_voces, label_voz

    vid = (voice_id or '').strip()
    if vid and vid not in {v['id'] for v in catalogo_voces()}:
        return {'ok': False, 'error': 'Voz no válida', 'status': 400}

    curso.course_engine_voice_id = vid
    curso.course_engine_voice_label = label_voz(vid) if vid else ''
    curso.save(update_fields=['course_engine_voice_id', 'course_engine_voice_label'])
    return {
        'ok': True,
        'voice_id': vid,
        'voice_label': curso.course_engine_voice_label,
        'voces': voces_demo_curso(curso),
        'status': 200,
    }


def contexto_studio(curso, *, request=None) -> dict[str, Any]:
    """Contexto de render compartido por el Studio admin y el portal."""
    from core.course_engine.voice_config import resolver_voice_id_curso, resolver_voice_label_curso

    return {
        'curso': curso,
        'modulos': modulos_curso_json(curso),
        'documentos': documentos_curso_json(curso),
        'voces_demo': voces_demo_curso(curso, request=request),
        'voice_id_activa': resolver_voice_id_curso(curso) or '',
        'voice_label_activa': resolver_voice_label_curso(curso),
        'max_upload_mb': MAX_UPLOAD_MB,
        'demo_max_seg': int(STUDIO_DEMO_MAX_SEC),
    }


def studio_ajax(request, curso, *, usuario=None) -> Optional[dict[str, Any]]:
    """Contrato ajax único del Studio (admin y portal comparten JS).

    Devuelve el dict de respuesta con 'status', o None si el request es el GET
    normal de la página.
    """
    from core.course_engine.voice_demos import url_demo_voz

    if request.method == 'GET':
        run_id = (request.GET.get('status') or '').strip()
        if run_id:
            out = estado_generacion(run_id)
            out['status'] = 200 if out.get('ok') else 404
            return out

        if request.GET.get('docs') == '1':
            return {'ok': True, 'documentos': documentos_curso_json(curso), 'status': 200}

        demo_voice = (request.GET.get('demo_voice') or '').strip()
        if demo_voice:
            out = url_demo_voz(
                demo_voice,
                generar_si_falta=request.GET.get('generate') == '1',
                request=request,
            )
            out['status'] = 200 if out.get('ok') else 404
            return out
        return None

    action = (request.POST.get('action') or '').strip()

    if action == 'upload_rag':
        archivos = request.FILES.getlist('archivos') or []
        if not archivos and request.FILES.get('archivo'):
            archivos = [request.FILES['archivo']]
        return subir_documentos_rag(curso, archivos, usuario=usuario)

    if action == 'reindex':
        return reindexar_documento(curso, request.POST.get('doc_id'))

    if action == 'set_voice':
        return set_voz_curso(curso, request.POST.get('voice_id') or '')

    if action in ('plan', 'generar'):
        try:
            modulo_id = int(request.POST.get('modulo_id') or 0) or None
        except (TypeError, ValueError):
            modulo_id = None
        fn = plan_video_desde_brief if action == 'plan' else encolar_generacion_video
        out = fn(
            cliente_id=curso.cliente_id,
            curso_id=curso.id,
            modulo_id=modulo_id,
            brief=request.POST.get('brief') or '',
            foco=request.POST.get('foco') or '',
            brief_file=request.FILES.get('brief_file'),
            modo_demo=True,
        )
        out['status'] = 200 if out.get('ok') else 400
        return out

    return {'ok': False, 'error': 'Acción no reconocida', 'status': 400}


def _leer_brief(brief: str, brief_file) -> str:
    text = (brief or '').strip()
    if not text and brief_file:
        text = brief_file.read().decode('utf-8', errors='ignore').strip()
    return text


def _brief_desde_curso(*, curso_id: int, cliente_id: int, modulo_id: Optional[int], foco: str) -> str:
    """Arma un brief usable sin textarea: RAG + módulo + foco."""
    partes: list[str] = []
    foco_txt = (foco or '').strip()
    if foco_txt:
        partes.append(f'Foco del video: {foco_txt}')

    if modulo_id:
        from core.models import Modulo

        mod = Modulo.objects.filter(pk=modulo_id, curso_id=curso_id).first()
        if mod:
            partes.append(f'Módulo {mod.numero}: {mod.titulo}')
            desc = (mod.descripcion or '').strip()
            if desc:
                partes.append(desc[:2000])
            cont = (mod.contenido or '').strip()
            if cont:
                partes.append(cont[:4000])

    try:
        from core.course_engine.rag_source import obtener_contexto_rag_empresa, resumen_documentos_curso

        rag_txt, _ok = obtener_contexto_rag_empresa(
            cliente_id,
            curso_id,
            foco_txt or 'contenido principal del curso para video microlearning',
            max_chars=3500,
        )
        if rag_txt:
            partes.append(rag_txt)
        else:
            resumen = resumen_documentos_curso(curso_id)
            if resumen:
                partes.append(resumen[:4000])
    except Exception:
        logger.exception('CE brief desde RAG curso=%s', curso_id)

    texto = '\n\n'.join(p for p in partes if p).strip()
    if len(texto) >= 40:
        return texto
    # Fallback mínimo para demo cuando aún no hay docs
    return (
        'Video demo eki: finanzas rurales prácticas. Separar gastos del hogar y del cultivo, '
        'guardar fondo de emergencia y registrar cada peso que entra y sale del emprendimiento.'
    )


def _resolver_brief(brief: str, brief_file, *, curso_id: int, cliente_id: int, modulo_id: Optional[int], foco: str) -> str:
    text = _leer_brief(brief, brief_file)
    if len(text) >= 40:
        return text
    return _brief_desde_curso(
        curso_id=curso_id,
        cliente_id=cliente_id,
        modulo_id=modulo_id,
        foco=foco,
    )


def plan_video_desde_brief(
    *,
    cliente_id: int,
    curso_id: int,
    modulo_id: Optional[int],
    brief: str,
    foco: str = '',
    brief_file=None,
    modo_demo: bool = False,
) -> dict[str, Any]:
    """Storyboard + beats tarjeta (dry run, sin APIs de pago)."""
    from core.course_engine.tarjeta_beats import beats_desde_tarjeta
    from core.course_engine.video_pilot_generator import VideoPilotGenerator

    brief_text = _resolver_brief(
        brief,
        brief_file,
        curso_id=curso_id,
        cliente_id=cliente_id,
        modulo_id=modulo_id,
        foco=foco,
    )

    gen = VideoPilotGenerator()
    target_sec = STUDIO_DEMO_MAX_SEC if modo_demo else 14.0
    out = gen.generar(
        cliente_id=cliente_id,
        curso_id=curso_id,
        modulo_id=modulo_id,
        brief=brief_text,
        foco=(foco or '').strip(),
        dry_run=True,
        generar_video=False,
        target_sec=target_sec,
        modo_demo=modo_demo,
    )
    if not out.plan:
        return {'ok': False, 'error': '; '.join(out.errors) or 'Plan falló'}

    seg_tarjeta = next((s for s in out.plan.segmentos if s.tipo == 'tarjeta'), None)
    beats = []
    if seg_tarjeta:
        beats = [
            {'headline': b.headline, 'narracion': b.narracion, 'detalle': b.detalle, 'filas': b.filas}
            for b in beats_desde_tarjeta(
                titulo=seg_tarjeta.tarjeta_titulo or seg_tarjeta.titulo or out.plan.titulo,
                puntos=seg_tarjeta.tarjeta_puntos,
                guion=seg_tarjeta.guion or '',
            )
        ]

    return {
        'ok': True,
        'run_id': out.run_id,
        'titulo': out.plan.titulo,
        'segmentos': [s.to_dict() for s in out.plan.segmentos],
        'beats_tarjeta': beats,
        'costo_estimado_usd': out.costo_estimado_usd,
        'modo_demo': modo_demo,
        'max_seg': target_sec,
    }


def encolar_generacion_video(
    *,
    cliente_id: int,
    curso_id: int,
    modulo_id: Optional[int],
    brief: str,
    foco: str = '',
    brief_file=None,
    modo_demo: bool = False,
) -> dict[str, Any]:
    brief_text = _resolver_brief(
        brief,
        brief_file,
        curso_id=curso_id,
        cliente_id=cliente_id,
        modulo_id=modulo_id,
        foco=foco,
    )

    run_id = uuid.uuid4().hex[:12]
    cache.set(f'{_CACHE_PREFIX}{run_id}', {'status': 'queued'}, 7200)

    from core.tasks import generar_video_course_engine_async

    generar_video_course_engine_async.delay(
        run_id,
        cliente_id,
        curso_id,
        modulo_id,
        brief_text,
        (foco or '').strip(),
        modo_demo,
    )
    return {
        'ok': True,
        'run_id': run_id,
        'status': 'queued',
        'modo_demo': modo_demo,
        'max_seg': STUDIO_DEMO_MAX_SEC if modo_demo else 14.0,
    }


def estado_generacion(run_id: str) -> dict[str, Any]:
    data = cache.get(f'{_CACHE_PREFIX}{run_id}')
    if not data:
        return {'ok': False, 'error': 'Run desconocido o expirado'}
    return {'ok': True, **data}
