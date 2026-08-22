"""Copiloto interno del admin eki (ops, no Nat / no LMS)."""
from __future__ import annotations

import json
import logging
import shutil
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Eres el copiloto de operaciones de eki (staff interno).
Hablas con el fundador/ops en español de Colombia, breve y concreto.
NO eres Nat ni eki.ia (eso es comercial/agro). NO inscribes estudiantes.
Usa SOLO el JSON de contexto. Si no está en el JSON, dilo.
Prioriza: fallos WhatsApp (63019/63021), campañas en borrador, ffmpeg, saldo Twilio, demo Riendas.
Si hay 63021: recodificar H.264 Main+AAC, no remux; M8/M9 de Impulso hay que re-subir master si el bitstream está roto.
No inventes cifras. Máximo 12 líneas.
"""


def _mask_tel(tel: str) -> str:
    d = ''.join(c for c in (tel or '') if c.isdigit())
    if len(d) < 4:
        return '****'
    return f'…{d[-4:]}'


def snapshot_ops(*, horas: int = 24) -> dict[str, Any]:
    from core.models import Campana, WhatsappLog
    from core.twilio_balance import twilio_balance_badge

    desde = timezone.now() - timedelta(hours=horas)
    logs = WhatsappLog.objects.filter(tipo='SENT', fecha__gte=desde)
    fallos = logs.filter(
        Q(estado__iexact='undelivered')
        | Q(estado__iexact='failed')
        | Q(error_detalle__icontains='63021')
        | Q(error_detalle__icontains='63019')
    )
    n_63021 = fallos.filter(error_detalle__icontains='63021').count()
    n_63019 = fallos.filter(error_detalle__icontains='63019').count()
    ejemplos = []
    for row in fallos.order_by('-fecha')[:8]:
        ejemplos.append(
            {
                'tel': _mask_tel(row.telefono),
                'estado': row.estado,
                'error': (row.error_detalle or '')[:80],
            }
        )

    campanas = list(
        Campana.objects.filter(ejecutada=False)
        .order_by('-id')
        .values('id', 'nombre', 'template_twilio_id')[:8]
    )

    ffmpeg = shutil.which('ffmpeg') or ''
    twilio_txt, twilio_tono = twilio_balance_badge()

    demo_id = str(getattr(settings, 'EKI_DEMO_RIENDAS_CURSO_ID', '') or '').strip()
    paq = {'fallidos_24h': 0}
    try:
        from core.models_media_entrega import MediaPaqueteEntrega

        paq['fallidos_24h'] = MediaPaqueteEntrega.objects.filter(
            estado=MediaPaqueteEntrega.ESTADO_FALLIDO,
            actualizado_en__gte=desde,
        ).count()
    except Exception:
        pass

    return {
        'ventana_horas': horas,
        'wa_enviados': logs.count(),
        'wa_fallos': fallos.count(),
        'n_63021': n_63021,
        'n_63019': n_63019,
        'ejemplos_fallos': ejemplos,
        'paquetes_media_fallidos': paq['fallidos_24h'],
        'campanas_sin_enviar': campanas,
        'ffmpeg': ffmpeg or 'no encontrado',
        'twilio_badge': twilio_txt,
        'twilio_tono': twilio_tono,
        'demo_riendas_curso_id': demo_id or '(vacío)',
    }


def _respuesta_reglas(pregunta: str, ctx: dict[str, Any]) -> str:
    q = (pregunta or '').lower()
    lineas = [
        f"Últimas {ctx.get('ventana_horas')} h: {ctx.get('wa_enviados')} envíos WA, "
        f"{ctx.get('wa_fallos')} fallos "
        f"(63021={ctx.get('n_63021')}, 63019={ctx.get('n_63019')}).",
        f"Twilio: {ctx.get('twilio_badge')}. ffmpeg: {ctx.get('ffmpeg')}.",
        f"Demo Riendas curso id: {ctx.get('demo_riendas_curso_id')}.",
    ]
    camps = ctx.get('campanas_sin_enviar') or []
    if camps:
        nombres = ', '.join(c.get('nombre') or f"#{c.get('id')}" for c in camps[:5])
        lineas.append(f"Campañas sin ejecutar: {nombres}.")
    else:
        lineas.append('No hay campañas en borrador.')
    if ctx.get('n_63021'):
        lineas.append(
            '63021 = video que WhatsApp no acepta. Recodificar H.264 Main+AAC; '
            'si el archivo está corrupto hay que re-subir el master.'
        )
    if 'campaña' in q or 'borrador' in q:
        lineas.append('No ejecute una campaña sin Content SID aprobado y variables {{1}}/{{2}} listas.')
    return '\n'.join(lineas)


def _llamar_openai(pregunta: str, ctx: dict[str, Any]) -> str | None:
    api_key = (getattr(settings, 'OPENAI_API_KEY', None) or '').strip()
    if not api_key:
        return None
    try:
        import openai

        client = openai.OpenAI(api_key=api_key)
        payload = json.dumps(ctx, ensure_ascii=False, default=str)[:8000]
        resp = client.chat.completions.create(
            model=getattr(settings, 'OPENAI_MODEL_COPILOTO', None) or 'gpt-4o-mini',
            temperature=0.2,
            max_tokens=500,
            messages=[
                {'role': 'system', 'content': SYSTEM_PROMPT},
                {
                    'role': 'user',
                    'content': f'Contexto ops (JSON):\n{payload}\n\nPregunta:\n{pregunta.strip()}',
                },
            ],
        )
        text = (resp.choices[0].message.content or '').strip()
        return text or None
    except Exception as exc:
        logger.warning('Copiloto OpenAI falló: %s', exc)
        return None


def responder_copiloto(pregunta: str) -> dict[str, Any]:
    ctx = snapshot_ops()
    pregunta = (pregunta or '').strip()
    if not pregunta:
        pregunta = '¿Qué debo mirar ahora?'
    ia = _llamar_openai(pregunta, ctx)
    if ia:
        return {'respuesta': ia, 'fuente': 'ia', 'snapshot': ctx}
    return {'respuesta': _respuesta_reglas(pregunta, ctx), 'fuente': 'reglas', 'snapshot': ctx}
