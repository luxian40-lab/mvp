"""API JSON del editor de cursos para eki_ops (JS-first)."""
from __future__ import annotations

import json

from django.db import IntegrityError, transaction
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods

from core.models import Cliente, Curso, Modulo, PasoModulo, SeccionModulo
from portal.authz import requiere_eki_ops
from portal.views import portal_login_required


def _json_body(request) -> dict:
    if not request.body:
        return {}
    try:
        data = json.loads(request.body.decode('utf-8'))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}


def _ok(data=None, status=200):
    payload = {'ok': True}
    if data is not None:
        payload.update(data)
    return JsonResponse(payload, status=status)


def _err(msg: str, status=400):
    return JsonResponse({'ok': False, 'error': msg}, status=status)


def _curso_dict(c: Curso) -> dict:
    return {
        'id': c.pk,
        'nombre': c.nombre,
        'cliente_id': c.cliente_id,
        'cliente_nombre': c.cliente.nombre if c.cliente_id else 'General',
        'activo': c.activo,
        'orden': c.orden,
        'modulos_count': getattr(c, 'modulos_count', None),
    }


def _modulo_dict(m: Modulo) -> dict:
    return {
        'id': m.pk,
        'curso_id': m.curso_id,
        'numero': m.numero,
        'titulo': m.titulo,
        'descripcion': m.descripcion or '',
        'contenido': m.contenido or '',
        'video_url': m.video_url or '',
        'archivo_pdf_url': m.archivo_pdf_url or '',
        'imagen_portada_url': m.imagen_portada_url or '',
        'modo_entrega': m.modo_entrega,
        'pasos_count': getattr(m, 'pasos_count', None),
    }


def _seccion_dict(s: SeccionModulo) -> dict:
    return {
        'id': s.pk,
        'modulo_id': s.modulo_id,
        'orden': s.orden,
        'titulo': s.titulo or '',
        'activa': s.activa,
    }


def _paso_dict(p: PasoModulo) -> dict:
    return {
        'id': p.pk,
        'modulo_id': p.modulo_id,
        'seccion_id': p.seccion_id,
        'orden': p.orden,
        'titulo': p.titulo or '',
        'tipo': p.tipo,
        'contenido': p.contenido or '',
        'media_url': p.media_url or '',
        'eval_opcion_a': p.eval_opcion_a or '',
        'eval_opcion_b': p.eval_opcion_b or '',
        'eval_opcion_c': p.eval_opcion_c or '',
        'eval_opcion_d': p.eval_opcion_d or '',
        'respuesta_correcta': p.respuesta_correcta or '',
        'feedback_correcto': p.feedback_correcto or '',
        'feedback_incorrecto': p.feedback_incorrecto or '',
        'activo': p.activo,
        'requiere_listo_para_avanzar': p.requiere_listo_para_avanzar,
    }


@portal_login_required
@requiere_eki_ops
@require_http_methods(['GET'])
def api_orgs(request):
    orgs = list(
        Cliente.objects.filter(activo=True)
        .order_by('nombre')
        .values('id', 'nombre')
    )
    return _ok({'orgs': orgs})


@portal_login_required
@requiere_eki_ops
@require_http_methods(['GET', 'POST'])
def api_cursos(request):
    if request.method == 'GET':
        org_id = request.GET.get('org')
        qs = Curso.objects.select_related('cliente').annotate(
            modulos_count=Count('modulos', distinct=True)
        ).order_by('cliente__nombre', 'orden', 'nombre')
        if org_id and str(org_id).isdigit():
            qs = qs.filter(cliente_id=int(org_id))
        return _ok({'cursos': [_curso_dict(c) for c in qs]})

    data = _json_body(request)
    nombre = (data.get('nombre') or '').strip()
    cliente_id = data.get('cliente_id')
    if not nombre:
        return _err('Nombre obligatorio')
    if not cliente_id:
        return _err('Organización obligatoria')
    org = get_object_or_404(Cliente, pk=cliente_id, activo=True)
    curso = Curso.objects.create(
        nombre=nombre[:200],
        descripcion=(data.get('descripcion') or '').strip() or nombre,
        cliente=org,
        activo=bool(data.get('activo', True)),
        orden=int(data.get('orden') or 0),
    )
    return _ok({'curso': _curso_dict(curso)}, status=201)


@portal_login_required
@requiere_eki_ops
@require_http_methods(['GET', 'PATCH', 'DELETE'])
def api_curso_detalle(request, curso_id: int):
    curso = get_object_or_404(Curso.objects.select_related('cliente'), pk=curso_id)
    if request.method == 'GET':
        mods = list(curso.modulos.order_by('numero', 'id'))
        return _ok({
            'curso': _curso_dict(curso),
            'modulos': [_modulo_dict(m) for m in mods],
        })

    if request.method == 'DELETE':
        curso.delete()
        return _ok({'deleted': True})

    data = _json_body(request)
    if 'nombre' in data:
        nombre = (data.get('nombre') or '').strip()
        if not nombre:
            return _err('Nombre vacío')
        curso.nombre = nombre[:200]
    if 'descripcion' in data:
        curso.descripcion = (data.get('descripcion') or '').strip()
    if 'activo' in data:
        curso.activo = bool(data.get('activo'))
    if 'orden' in data:
        try:
            curso.orden = int(data.get('orden') or 0)
        except (TypeError, ValueError):
            return _err('Orden inválido')
    curso.save()
    return _ok({'curso': _curso_dict(curso)})


@portal_login_required
@requiere_eki_ops
@require_http_methods(['POST'])
def api_modulos_crear(request, curso_id: int):
    curso = get_object_or_404(Curso, pk=curso_id)
    data = _json_body(request)
    titulo = (data.get('titulo') or '').strip()
    if not titulo:
        return _err('Título obligatorio')
    last = curso.modulos.order_by('-numero').first()
    try:
        numero = int(data.get('numero')) if data.get('numero') is not None else (
            int(last.numero) + 1 if last else 1
        )
    except (TypeError, ValueError):
        return _err('Número inválido')
    try:
        mod = Modulo.objects.create(
            curso=curso,
            numero=numero,
            titulo=titulo[:200],
            descripcion=(data.get('descripcion') or '').strip() or titulo,
            modo_entrega=data.get('modo_entrega') or 'pasos',
        )
    except IntegrityError:
        return _err(f'Ya existe el módulo número {numero}')
    # Sección inicial para poder agregar pasos
    SeccionModulo.objects.create(modulo=mod, orden=1, titulo='Bloque 1', activa=True)
    return _ok({'modulo': _modulo_dict(mod)}, status=201)


@portal_login_required
@requiere_eki_ops
@require_http_methods(['GET', 'PATCH', 'DELETE'])
def api_modulo_detalle(request, modulo_id: int):
    mod = get_object_or_404(Modulo.objects.select_related('curso'), pk=modulo_id)
    if request.method == 'GET':
        secciones = list(mod.secciones.order_by('orden', 'id'))
        pasos = list(mod.pasos.select_related('seccion').order_by('orden', 'id'))
        return _ok({
            'modulo': _modulo_dict(mod),
            'secciones': [_seccion_dict(s) for s in secciones],
            'pasos': [_paso_dict(p) for p in pasos],
            'tiene_pasos': len(pasos) > 0,
        })

    if request.method == 'DELETE':
        mod.delete()
        return _ok({'deleted': True})

    data = _json_body(request)
    if 'titulo' in data:
        t = (data.get('titulo') or '').strip()
        if not t:
            return _err('Título vacío')
        mod.titulo = t[:200]
    if 'descripcion' in data:
        mod.descripcion = (data.get('descripcion') or '').strip()
    if 'contenido' in data:
        mod.contenido = data.get('contenido') or ''
    if 'video_url' in data:
        mod.video_url = (data.get('video_url') or '').strip() or None
    if 'archivo_pdf_url' in data:
        mod.archivo_pdf_url = (data.get('archivo_pdf_url') or '').strip() or None
    if 'imagen_portada_url' in data:
        mod.imagen_portada_url = (data.get('imagen_portada_url') or '').strip() or None
    if 'numero' in data:
        try:
            mod.numero = int(data.get('numero'))
        except (TypeError, ValueError):
            return _err('Número inválido')
    if 'modo_entrega' in data and data.get('modo_entrega') in ('auto', 'legacy', 'pasos'):
        mod.modo_entrega = data['modo_entrega']
    try:
        # Evitar clean estricto de contenido vacío si hay pasos
        mod.save()
    except IntegrityError:
        return _err('Número de módulo duplicado')
    return _ok({'modulo': _modulo_dict(mod)})


@portal_login_required
@requiere_eki_ops
@require_http_methods(['POST'])
def api_secciones_crear(request, modulo_id: int):
    mod = get_object_or_404(Modulo, pk=modulo_id)
    data = _json_body(request)
    last = mod.secciones.order_by('-orden').first()
    try:
        orden = int(data.get('orden')) if data.get('orden') is not None else (
            (last.orden + 1) if last else 1
        )
    except (TypeError, ValueError):
        return _err('Orden inválido')
    try:
        sec = SeccionModulo.objects.create(
            modulo=mod,
            orden=orden,
            titulo=(data.get('titulo') or f'Bloque {orden}')[:200],
            activa=bool(data.get('activa', True)),
        )
    except IntegrityError:
        return _err(f'Ya existe sección con orden {orden}')
    return _ok({'seccion': _seccion_dict(sec)}, status=201)


@portal_login_required
@requiere_eki_ops
@require_http_methods(['PATCH', 'DELETE'])
def api_seccion_detalle(request, seccion_id: int):
    sec = get_object_or_404(SeccionModulo, pk=seccion_id)
    if request.method == 'DELETE':
        if sec.pasos.exists():
            return _err('Mueva o borre los pasos antes de eliminar la sección')
        sec.delete()
        return _ok({'deleted': True})

    data = _json_body(request)
    if 'titulo' in data:
        sec.titulo = (data.get('titulo') or '')[:200]
    if 'activa' in data:
        sec.activa = bool(data.get('activa'))
    if 'orden' in data:
        try:
            sec.orden = int(data.get('orden'))
        except (TypeError, ValueError):
            return _err('Orden inválido')
    try:
        sec.save()
    except IntegrityError:
        return _err('Orden de sección duplicado')
    return _ok({'seccion': _seccion_dict(sec)})


@portal_login_required
@requiere_eki_ops
@require_http_methods(['POST'])
def api_pasos_crear(request, seccion_id: int):
    sec = get_object_or_404(SeccionModulo.objects.select_related('modulo'), pk=seccion_id)
    data = _json_body(request)
    tipo = (data.get('tipo') or PasoModulo.TIPO_CONTENIDO).strip()
    allowed = {c[0] for c in PasoModulo.TIPOS}
    if tipo not in (PasoModulo.TIPO_CONTENIDO, PasoModulo.TIPO_EVAL_OPC):
        if tipo not in allowed:
            return _err('Tipo no permitido')
        # v1 UI focuses on contenido + eval opciones; still allow if sent
    last = sec.modulo.pasos.order_by('-orden').first()
    try:
        orden = int(data.get('orden')) if data.get('orden') is not None else (
            (last.orden + 1) if last else 1
        )
    except (TypeError, ValueError):
        return _err('Orden inválido')
    try:
        paso = PasoModulo(
            modulo=sec.modulo,
            seccion=sec,
            orden=orden,
            titulo=(data.get('titulo') or '')[:200],
            tipo=tipo,
            contenido=(data.get('contenido') or ''),
            media_url=(data.get('media_url') or '')[:1000],
            eval_opcion_a=(data.get('eval_opcion_a') or ''),
            eval_opcion_b=(data.get('eval_opcion_b') or ''),
            eval_opcion_c=(data.get('eval_opcion_c') or ''),
            eval_opcion_d=(data.get('eval_opcion_d') or ''),
            respuesta_correcta=(data.get('respuesta_correcta') or '')[:10],
            feedback_correcto=(data.get('feedback_correcto') or ''),
            feedback_incorrecto=(data.get('feedback_incorrecto') or ''),
            activo=bool(data.get('activo', True)),
            requiere_listo_para_avanzar=bool(data.get('requiere_listo_para_avanzar', True)),
        )
        paso.save()
    except IntegrityError:
        return _err(f'Ya existe paso con orden {orden} en el módulo')
    return _ok({'paso': _paso_dict(paso)}, status=201)


@portal_login_required
@requiere_eki_ops
@require_http_methods(['PATCH', 'DELETE'])
def api_paso_detalle(request, paso_id: int):
    paso = get_object_or_404(PasoModulo, pk=paso_id)
    if request.method == 'DELETE':
        paso.delete()
        return _ok({'deleted': True})

    data = _json_body(request)
    fields_txt = (
        'titulo', 'contenido', 'media_url', 'eval_opcion_a', 'eval_opcion_b',
        'eval_opcion_c', 'eval_opcion_d', 'respuesta_correcta',
        'feedback_correcto', 'feedback_incorrecto',
    )
    for f in fields_txt:
        if f in data:
            val = data.get(f) or ''
            if f == 'titulo':
                val = str(val)[:200]
            elif f == 'media_url':
                val = str(val)[:1000]
            elif f == 'respuesta_correcta':
                val = str(val)[:10]
            setattr(paso, f, val)
    if 'tipo' in data:
        tipo = (data.get('tipo') or '').strip()
        if tipo not in {c[0] for c in PasoModulo.TIPOS}:
            return _err('Tipo inválido')
        paso.tipo = tipo
    if 'activo' in data:
        paso.activo = bool(data.get('activo'))
    if 'requiere_listo_para_avanzar' in data:
        paso.requiere_listo_para_avanzar = bool(data.get('requiere_listo_para_avanzar'))
    if 'seccion_id' in data:
        sec = get_object_or_404(SeccionModulo, pk=data.get('seccion_id'), modulo=paso.modulo)
        paso.seccion = sec
    if 'orden' in data:
        try:
            paso.orden = int(data.get('orden'))
        except (TypeError, ValueError):
            return _err('Orden inválido')
    try:
        paso.save()
    except IntegrityError:
        return _err('Orden de paso duplicado')
    return _ok({'paso': _paso_dict(paso)})


@portal_login_required
@requiere_eki_ops
@require_http_methods(['POST'])
def api_reordenar_pasos(request, modulo_id: int):
    """Body: { "orden_ids": [paso_id, ...] } asigna orden 1..n."""
    mod = get_object_or_404(Modulo, pk=modulo_id)
    data = _json_body(request)
    ids = data.get('orden_ids') or []
    if not isinstance(ids, list) or not ids:
        return _err('orden_ids requerido')
    pasos = {p.pk: p for p in mod.pasos.filter(pk__in=ids)}
    if len(pasos) != len(ids):
        return _err('Algunos pasos no pertenecen al módulo')
    with transaction.atomic():
        # Evitar colisión unique: mover a rango alto temporal
        for i, pid in enumerate(ids):
            PasoModulo.objects.filter(pk=pid).update(orden=10000 + i)
        for i, pid in enumerate(ids, start=1):
            PasoModulo.objects.filter(pk=pid).update(orden=i)
    pasos_out = list(mod.pasos.order_by('orden', 'id'))
    return _ok({'pasos': [_paso_dict(p) for p in pasos_out]})
