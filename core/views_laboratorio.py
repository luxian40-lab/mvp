"""Laboratorio de agentes. No envía WhatsApp, no descuenta cupo y no usa memoria de personas."""
from __future__ import annotations

import logging
import time
import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.cache import cache
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from core.admin.agentes_v2_textos import SIN_DATO
from core.models import Cliente, ConversacionRAGCandidata, EventoIA
from core.models_agentes import ConocimientoAgente, PruebaAgente
from core.planes_linea import PLAN_CHOICES

AGENTES_LAB = PruebaAgente.AGENTE_CHOICES
_TOPE_HORA_KEY = 'lab_hora:{user}:{hora}'
logger = logging.getLogger(__name__)


def _permitido(request) -> bool:
    user = request.user
    return bool(user.is_authenticated and user.is_staff)


def _clave_hora(user_id):
    return _TOPE_HORA_KEY.format(user=user_id, hora=timezone.now().strftime('%Y%m%d%H'))


def _cupo_disponible(user_id) -> bool:
    tope = int(getattr(settings, 'LABORATORIO_TOPE_HORA', 20))
    try:
        actual = cache.get(_clave_hora(user_id), 0) or 0
        return int(actual) < tope
    except Exception:
        logger.warning('laboratorio_cupo_no_disponible')
        return True


def _consumir_cupo(user_id) -> None:
    clave = _clave_hora(user_id)
    try:
        cache.add(clave, 0, timeout=3700)
        try:
            cache.incr(clave)
        except ValueError:
            cache.set(clave, 1, timeout=3700)
    except Exception:
        logger.warning('laboratorio_cupo_no_conto')


def _titulos(agente: str, cliente_id):
    from django.db.models import Q

    filas = ConocimientoAgente.objects.filter(
        estado=ConocimientoAgente.ESTADO_APROBADO,
        agente__in=(agente, ConocimientoAgente.AGENTE_TODOS),
    )
    if cliente_id:
        filas = filas.filter(
            Q(alcance=ConocimientoAgente.ALCANCE_TODOS) | Q(cliente_id=cliente_id)
        )
    else:
        filas = filas.exclude(alcance=ConocimientoAgente.ALCANCE_CLIENTE)
    return list(filas.order_by('orden', '-actualizado_en').values_list('titulo', flat=True)[:12])


def _cliente_id(valor: str):
    if valor and str(valor).isdigit():
        return int(valor)
    return None


def ejecutar_en_laboratorio(*, agente: str, pregunta: str, cliente_id, usuario, plan: str) -> dict:
    """Misma función que la línea de agentes, sin teléfono y sin cupo."""
    from core.sandbox_agentes import _modelo, responder_agente_sandbox

    if not _cupo_disponible(usuario.pk):
        return {'ok': False, 'error': 'Llegó al tope de pruebas de esta hora.'}
    inicio = time.perf_counter()
    texto = responder_agente_sandbox(
        agente,
        pregunta,
        telefono='',
        cliente_id=cliente_id,
    )
    _consumir_cupo(usuario.pk)
    ms = int((time.perf_counter() - inicio) * 1000)
    modelo = _modelo()
    EventoIA.objects.create(
        trace_id=uuid.uuid4(),
        tipo=EventoIA.TIPO_IA_AGENT_TRIGGERED,
        agente=agente,
        canal=EventoIA.CANAL_ADMIN,
        cliente_id=cliente_id,
        modelo=modelo,
        latencia_ms=ms,
        input_preview=(pregunta or '')[:500],
        output_preview=(texto or '')[:500],
        metadata={'origen': 'laboratorio', 'plan': plan or ''},
    )
    return {
        'ok': True,
        'texto': texto,
        'modelo': modelo,
        'ms': ms,
        'costo': SIN_DATO,
        'fragmentos': SIN_DATO,
        'productos': SIN_DATO,
        'conocimientos': _titulos(agente, cliente_id),
    }


def _lineas(texto: str) -> list[str]:
    return [linea.strip().lower() for linea in (texto or '').splitlines() if linea.strip()]


def evaluar_prueba(respuesta: str, prueba: PruebaAgente) -> str:
    cuerpo = (respuesta or '').lower()
    if not (prueba.debe_mencionar or prueba.no_debe_mencionar or prueba.debe_usar_fuente):
        return PruebaAgente.RESULTADO_REVISAR
    for frase in _lineas(prueba.debe_mencionar):
        if frase not in cuerpo:
            return PruebaAgente.RESULTADO_REVISAR
    for frase in _lineas(prueba.no_debe_mencionar):
        if frase in cuerpo:
            return PruebaAgente.RESULTADO_REVISAR
    fuente = (prueba.debe_usar_fuente or '').strip().lower()
    if fuente and fuente not in cuerpo:
        return PruebaAgente.RESULTADO_REVISAR
    return PruebaAgente.RESULTADO_PASA


def _contexto(request, extra=None):
    tope = int(getattr(settings, 'LABORATORIO_TOPE_PRUEBAS', 10))
    datos = {
        'agentes': AGENTES_LAB,
        'planes': PLAN_CHOICES,
        'clientes': Cliente.objects.order_by('nombre').only('id', 'nombre')[:200],
        'pruebas': PruebaAgente.objects.select_related('cliente')[:50],
        'tope_pruebas': tope,
        'tope_hora': int(getattr(settings, 'LABORATORIO_TOPE_HORA', 20)),
        'sin_dato': SIN_DATO,
        'ultimo': request.session.pop('lab_ultimo', None),
        'corrida': request.session.pop('lab_corrida', None),
    }
    if extra:
        datos.update(extra)
    return datos


@staff_member_required
@require_http_methods(['GET', 'POST'])
def laboratorio_view(request):
    if not _permitido(request):
        return HttpResponseForbidden('El laboratorio está apagado.')
    if request.method == 'POST':
        return _post(request)
    return render(request, 'admin/laboratorio.html', _contexto(request))


def _post(request):
    accion = (request.POST.get('accion') or '').strip()
    agente = (request.POST.get('agente') or '').strip()
    pregunta = (request.POST.get('pregunta') or '').strip()
    plan = (request.POST.get('plan') or '').strip()
    cliente_id = _cliente_id(request.POST.get('cliente') or '')
    codigos = {clave for clave, _nombre in AGENTES_LAB}

    if accion == 'preguntar':
        if agente not in codigos or not pregunta:
            messages.error(request, 'Elija un agente y escriba la pregunta.')
        else:
            resultado = ejecutar_en_laboratorio(
                agente=agente,
                pregunta=pregunta,
                cliente_id=cliente_id,
                usuario=request.user,
                plan=plan,
            )
            if not resultado.get('ok'):
                messages.error(request, resultado.get('error') or 'No se pudo probar.')
            else:
                request.session['lab_ultimo'] = {
                    'agente': agente,
                    'pregunta': pregunta,
                    'plan': plan,
                    'cliente': cliente_id or '',
                    'texto': resultado['texto'],
                    'modelo': resultado['modelo'],
                    'ms': resultado['ms'],
                    'costo': resultado['costo'],
                    'fragmentos': resultado['fragmentos'],
                    'productos': resultado['productos'],
                    'conocimientos': resultado['conocimientos'],
                }
        return redirect(_volver(request))

    if accion == 'mal':
        ultimo = request.session.pop('lab_ultimo', None) or {}
        texto_pregunta = (ultimo.get('pregunta') or pregunta).strip()
        texto_respuesta = (ultimo.get('texto') or '').strip()
        if not texto_pregunta or not texto_respuesta:
            messages.error(request, 'Primero haga una pregunta en el laboratorio.')
            return redirect(_volver(request))
        candidata = ConversacionRAGCandidata.objects.create(
            telefono='laboratorio',
            pregunta=texto_pregunta[:4000],
            respuesta_nati=texto_respuesta[:4000],
            estado=ConversacionRAGCandidata.ESTADO_PENDIENTE,
            cliente_id=cliente_id or ultimo.get('cliente') or None,
            agentes=[ultimo.get('agente') or agente] if (ultimo.get('agente') or agente) in codigos else [],
            alcance='cliente' if (cliente_id or ultimo.get('cliente')) else 'todos',
            notas_revisor='Creada desde el laboratorio.',
        )
        url = reverse(
            'admin:agents_commercial_conversacionragcandidata_change',
            args=[candidata.pk],
        )
        return redirect(url)

    if accion == 'guardar':
        if agente not in codigos or not pregunta:
            messages.error(request, 'Elija un agente y escriba la pregunta.')
            return redirect(_volver(request))
        PruebaAgente.objects.create(
            agente=agente,
            pregunta=pregunta[:4000],
            cliente_id=cliente_id,
            plan=plan if plan in {clave for clave, _etiq in PLAN_CHOICES} else '',
            debe_mencionar=(request.POST.get('debe_mencionar') or '')[:2000],
            no_debe_mencionar=(request.POST.get('no_debe_mencionar') or '')[:2000],
            debe_usar_fuente=(request.POST.get('debe_usar_fuente') or '')[:160],
        )
        messages.success(request, 'La prueba quedó guardada.')
        return redirect(_volver(request))

    if accion == 'correr':
        tope = int(getattr(settings, 'LABORATORIO_TOPE_PRUEBAS', 10))
        pruebas = list(PruebaAgente.objects.all()[:tope])
        filas = []
        for prueba in pruebas:
            if not _cupo_disponible(request.user.pk):
                filas.append({'pregunta': prueba.pregunta, 'resultado': 'revisar', 'nota': 'Tope de la hora.'})
                break
            resultado = ejecutar_en_laboratorio(
                agente=prueba.agente,
                pregunta=prueba.pregunta,
                cliente_id=prueba.cliente_id,
                usuario=request.user,
                plan=prueba.plan,
            )
            if not resultado.get('ok'):
                filas.append({'pregunta': prueba.pregunta, 'resultado': 'revisar', 'nota': resultado.get('error')})
                break
            marca = evaluar_prueba(resultado['texto'], prueba)
            prueba.ultimo_resultado = marca
            prueba.corridas = (prueba.corridas or 0) + 1
            prueba.ultima_corrida = timezone.now()
            prueba.save(update_fields=['ultimo_resultado', 'corridas', 'ultima_corrida'])
            filas.append({'pregunta': prueba.pregunta, 'resultado': marca, 'nota': ''})
        request.session['lab_corrida'] = filas
        return redirect(_volver(request))

    return redirect(_volver(request))


def _volver(request):
    return reverse('laboratorio_agentes')
