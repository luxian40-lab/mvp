"""Copiloto interno del admin eki (ops, no Nat / no LMS)."""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger(__name__)

CANON_OPS = """Hechos fijos (no los contradigas):
- Este chat es el copiloto OPS del admin Unfold. No es Nat (bot comercial agro) ni eki.ia del aula.
- Producción EB = eki-prod-final, región us-east-2, S3 eki-produccion. Un número WhatsApp sirve vitrina comercial + LMS.
- 63021 = WhatsApp rechazó el video (codec/perfil). Recodificar H.264 Main+AAC + faststart; remux no basta. Si el bitstream está roto hay que re-subir master.
- 63019 = Twilio no pudo bajar el media (URL/host/ACL).
- Campañas HSM: variables {{1}}… secuenciales; no mandar plantilla a medias.
- Demo Riendas: env EKI_DEMO_RIENDAS_CURSO_ID. Carrusel: EKI_DEMO_CAROUSEL_CONTENT_SID.
- media_wa_apto=False en un paso = video que el gate marcó no apto.
- No inventes SIDs, teléfonos ni deploys. Si no está en el JSON, dilo.
"""

SYSTEM_PROMPT = """Eres el copiloto de operaciones de eki. Hablas con el fundador/ops en español de Colombia, breve.
""" + CANON_OPS + """
Usa el JSON de pulso (producción vs local, fallos, infra, campañas) y el historial corto.
Prioriza: ¿estamos en producción?, qué falló en WA, Twilio, ffmpeg, demo, campañas en borrador.
Máximo 14 líneas. Accionable.
"""


def _mask_tel(tel: str) -> str:
    d = ''.join(c for c in (tel or '') if c.isdigit())
    if len(d) < 4:
        return '****'
    return f'…{d[-4:]}'


def _es_produccion() -> bool:
    if getattr(settings, 'DEBUG', False):
        return False
    env = (
        os.environ.get('AWS_EB_ENVIRONMENT_NAME')
        or os.environ.get('ENVIRONMENT')
        or ''
    ).strip()
    return env == 'eki-prod-final'


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
    for row in fallos.order_by('-fecha')[:10]:
        ejemplos.append(
            {
                'tel': _mask_tel(row.telefono),
                'estado': row.estado,
                'error': (row.error_detalle or '')[:120],
                'cuando': timezone.localtime(row.fecha).strftime('%H:%M') if row.fecha else '',
            }
        )

    codigos: dict[str, int] = {}
    for err in fallos.values_list('error_detalle', flat=True)[:200]:
        m = re.search(r'\b(63\d{3})\b', err or '')
        if m:
            codigos[m.group(1)] = codigos.get(m.group(1), 0) + 1
    top_codigos = sorted(codigos.items(), key=lambda x: -x[1])[:6]

    campanas = list(
        Campana.objects.filter(ejecutada=False)
        .order_by('-id')
        .values('id', 'nombre', 'template_twilio_id', 'fecha_programada')[:8]
    )
    for c in campanas:
        fp = c.get('fecha_programada')
        c['fecha_programada'] = fp.isoformat() if fp else None
        sid = c.get('template_twilio_id') or ''
        c['tiene_content_sid'] = bool(str(sid).strip().startswith('HX'))

    ffmpeg = shutil.which('ffmpeg') or ''
    twilio_txt, twilio_tono = twilio_balance_badge()

    demo_id = str(getattr(settings, 'EKI_DEMO_RIENDAS_CURSO_ID', '') or '').strip()
    carousel_sid = str(getattr(settings, 'EKI_DEMO_CAROUSEL_CONTENT_SID', '') or '').strip()
    wa_from = (
        (getattr(settings, 'TWILIO_WHATSAPP_NUMBER', None) or '')
        or (getattr(settings, 'TWILIO_PHONE_NUMBER', None) or '')
    ).strip()

    paq = {'fallidos_24h': 0}
    try:
        from core.models_media_entrega import MediaPaqueteEntrega

        paq['fallidos_24h'] = MediaPaqueteEntrega.objects.filter(
            estado=MediaPaqueteEntrega.ESTADO_FALLIDO,
            actualizado_en__gte=desde,
        ).count()
    except Exception:
        pass

    videos_no_aptos = 0
    try:
        from core.models import PasoModulo

        videos_no_aptos = PasoModulo.objects.filter(media_wa_apto=False, activo=True).count()
    except Exception:
        pass

    infra = []
    try:
        from core.infra_monitor import header_health_strip

        infra = header_health_strip()
    except Exception:
        infra = []

    eb = (
        os.environ.get('AWS_EB_ENVIRONMENT_NAME')
        or os.environ.get('ENVIRONMENT')
        or ''
    ).strip()
    es_prod = _es_produccion() or (eb == 'eki-prod-final')

    return {
        'entorno': {
            'es_produccion': es_prod,
            'debug': bool(getattr(settings, 'DEBUG', False)),
            'eb': eb or ('eki-prod-final' if es_prod else 'local/dev'),
            'region': 'us-east-2' if es_prod else 'n/a',
            's3': 'eki-produccion' if es_prod else '(local o no-prod)',
        },
        'ventana_horas': horas,
        'wa_enviados': logs.count(),
        'wa_fallos': fallos.count(),
        'n_63021': n_63021,
        'n_63019': n_63019,
        'top_codigos_error': [{'codigo': k, 'n': v} for k, v in top_codigos],
        'ejemplos_fallos': ejemplos,
        'paquetes_media_fallidos': paq['fallidos_24h'],
        'pasos_video_no_apto_wa': videos_no_aptos,
        'campanas_sin_enviar': campanas,
        'ffmpeg': ffmpeg or 'no encontrado',
        'twilio_badge': twilio_txt,
        'twilio_tono': twilio_tono,
        'wa_from_mask': _mask_tel(wa_from) if wa_from else '(vacío)',
        'demo_riendas_curso_id': demo_id or '(vacío)',
        'carrusel_content_sid': (carousel_sid[:8] + '…') if len(carousel_sid) > 10 else (carousel_sid or '(vacío)'),
        'infra_chips': infra,
    }


def _respuesta_reglas(pregunta: str, ctx: dict[str, Any]) -> str:
    env = ctx.get('entorno') or {}
    donde = 'PRODUCCIÓN (eki-prod-final)' if env.get('es_produccion') else 'este entorno NO se marca como producción'
    lineas = [
        f'Estamos en {donde}. DEBUG={env.get("debug")}.',
        f"Últimas {ctx.get('ventana_horas')} h: {ctx.get('wa_enviados')} envíos WA, "
        f"{ctx.get('wa_fallos')} fallos "
        f"(63021={ctx.get('n_63021')}, 63019={ctx.get('n_63019')}).",
        f"Twilio: {ctx.get('twilio_badge')}. From {ctx.get('wa_from_mask')}. "
        f"ffmpeg: {ctx.get('ffmpeg')}.",
        f"Demo Riendas curso id: {ctx.get('demo_riendas_curso_id')}.",
    ]
    if ctx.get('pasos_video_no_apto_wa'):
        lineas.append(f"Pasos con video no apto WA: {ctx.get('pasos_video_no_apto_wa')}.")
    camps = ctx.get('campanas_sin_enviar') or []
    if camps:
        nombres = ', '.join(c.get('nombre') or f"#{c.get('id')}" for c in camps[:5])
        lineas.append(f'Campañas sin ejecutar: {nombres}.')
    else:
        lineas.append('No hay campañas en borrador.')
    if ctx.get('n_63021'):
        lineas.append(
            '63021 = video que WhatsApp no acepta. Recodificar H.264 Main+AAC; '
            'si el archivo está corrupto hay que re-subir el master.'
        )
    if ctx.get('n_63019'):
        lineas.append('63019 = Twilio no pudo descargar el archivo (URL/ACL).')
    q = (pregunta or '').lower()
    if 'campaña' in q or 'borrador' in q:
        lineas.append('No ejecute una campaña sin Content SID aprobado y variables {{1}}/{{2}} listas.')
    infra = ctx.get('infra_chips') or []
    malos = [c.get('label') for c in infra if c.get('ok') is False]
    if malos:
        lineas.append('Infra en rojo: ' + ', '.join(malos) + '.')
    return '\n'.join(lineas)


def _llamar_openai(pregunta: str, ctx: dict[str, Any], historial: list | None) -> str | None:
    api_key = (getattr(settings, 'OPENAI_API_KEY', None) or '').strip()
    if not api_key:
        return None
    try:
        import openai

        client = openai.OpenAI(api_key=api_key)
        payload = json.dumps(ctx, ensure_ascii=False, default=str)[:12000]
        messages: list[dict[str, str]] = [
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {
                'role': 'system',
                'content': 'Pulso ops ahora (JSON):\n' + payload,
            },
        ]
        for m in (historial or [])[-8]:
            role = m.get('role') or ''
            text = (m.get('text') or '').strip()
            if not text:
                continue
            if role == 'user':
                messages.append({'role': 'user', 'content': text[:1500]})
            elif role == 'assistant':
                messages.append({'role': 'assistant', 'content': text[:2000]})
        messages.append({'role': 'user', 'content': pregunta.strip()[:2000]})
        resp = client.chat.completions.create(
            model=getattr(settings, 'OPENAI_MODEL_COPILOTO', None) or 'gpt-4o-mini',
            temperature=0.2,
            max_tokens=650,
            messages=messages,
        )
        text = (resp.choices[0].message.content or '').strip()
        return text or None
    except Exception as exc:
        logger.warning('Copiloto OpenAI falló: %s', exc)
        return None


def responder_copiloto(pregunta: str, historial: list | None = None) -> dict[str, Any]:
    ctx = snapshot_ops()
    pregunta = (pregunta or '').strip()
    if not pregunta:
        pregunta = '¿Qué debo mirar ahora en producción?'
    ia = _llamar_openai(pregunta, ctx, historial)
    if ia:
        return {'respuesta': ia, 'fuente': 'ia', 'snapshot': ctx}
    return {'respuesta': _respuesta_reglas(pregunta, ctx), 'fuente': 'reglas', 'snapshot': ctx}
