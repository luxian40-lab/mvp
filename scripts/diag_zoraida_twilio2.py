"""Segunda pasada: actividad por teléfono de quienes están en agente, y huecos de media."""
from datetime import timedelta

from django.utils import timezone

from core.models import Estudiante, Modulo, PasoModulo, WhatsappLog

CUT = timezone.now() - timedelta(days=10)

stuck = list(
    Estudiante.objects.filter(
        cliente_id=14,
        estado_onboarding__in=[
            'esperando_respuesta_asistente',
            'esperando_respuesta_reto',
            'esperando_respuesta_modulo',
        ],
    )
)
print('== ATASCADOS EN AGENTE / MODULO')
for e in stuck:
    ctx = e.contexto_temporal or {}
    print(
        f"  {e.id} {(e.nombre or '')[:32]!r} onb={e.estado_onboarding} "
        f"tipo={ctx.get('tipo')} mod={ctx.get('modulo_id')} "
        f"preg={ctx.get('preguntas_hechas')} tel=…{(e.telefono or '')[-4:]}"
    )
    tels = [(e.telefono or '').replace('+', ''), (e.telefono or '')]
    logs = WhatsappLog.objects.filter(fecha__gte=CUT).filter(
        telefono__endswith=(e.telefono or '')[-10:]
    ).order_by('-fecha')[:8]
    print(f"    logs 10d n={logs.count() if hasattr(logs, 'count') else 'slice'}")
    for log in logs:
        body = (log.mensaje or '').replace('\n', ' ')[:80]
        err = (log.error_detalle or '')[:80]
        print(
            f"    [{log.fecha:%d/%m %H:%M}] {log.tipo} {log.estado} "
            f"ag={log.agente_usado or '-'} err={err!r} {body!r}"
        )

print('\n== FAILED 10d TODOS (630 / fail)')
fails = WhatsappLog.objects.filter(fecha__gte=CUT).filter(
    error_detalle__iregex=r'630|fail|undeliver|21211|21610'
).order_by('-fecha')[:25]
print(' n', fails.count() if False else 'slice')
for log in WhatsappLog.objects.filter(fecha__gte=CUT).exclude(error_detalle='').exclude(error_detalle__isnull=True).order_by('-fecha')[:30]:
    print(
        f"  [{log.fecha:%d/%m %H:%M}] tel=…{(log.telefono or '')[-4:]} "
        f"{log.estado} {(log.error_detalle or '')[:100]!r} {(log.mensaje or '')[:50]!r}"
    )

print('\n== FAILED estado 10d')
for log in WhatsappLog.objects.filter(fecha__gte=CUT, estado__iregex=r'fail|undeliver|error').order_by('-fecha')[:20]:
    print(
        f"  [{log.fecha:%d/%m %H:%M}] tel=…{(log.telefono or '')[-4:]} "
        f"{log.estado} err={(log.error_detalle or '')[:80]!r}"
    )

print('\n== M5 PASOS (ideas a negocios)')
m5 = Modulo.objects.filter(curso_id=22, numero=5).first()
if m5:
    for p in PasoModulo.objects.filter(modulo=m5).order_by('orden', 'id'):
        print(
            f"  p{p.id} o={p.orden} act={p.activo} tit={(p.titulo or '')[:40]!r} "
            f"media={bool(p.media_url)} apto={p.media_wa_apto} cont_len={len(p.contenido or '')}"
        )

print('\n== PASOS NO APTOS / SIN FLAG curso 22')
for p in PasoModulo.objects.filter(modulo__curso_id=22).exclude(media_url='').exclude(media_url__isnull=True):
    if p.media_wa_apto is not True:
        print(
            f"  p{p.id} M{p.modulo.numero} apto={p.media_wa_apto} {(p.media_url or '')[-60:]}"
        )
