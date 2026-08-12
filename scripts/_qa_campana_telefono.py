"""QA puntual: EnvioLog + WhatsappLog para un teléfono (sin Twilio smoke)."""
from __future__ import annotations

import os
import sys
from datetime import timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
os.environ.setdefault('EKI_USE_REMOTE_DB', '1')

import django

django.setup()

from django.conf import settings
from django.db.models import Count, Q
from django.utils import timezone

from core.models import Campana, EnvioLog, Estudiante, WhatsappLog

NEEDLE = (sys.argv[1] if len(sys.argv) > 1 else '3106077609').replace(' ', '').replace('+', '')
if NEEDLE.startswith('57') and len(NEEDLE) > 10:
    local = NEEDLE[2:]
else:
    local = NEEDLE
    NEEDLE = f'57{NEEDLE}' if len(NEEDLE) == 10 else NEEDLE

db = settings.DATABASES['default']
print('engine=', db.get('ENGINE'))
print('host=', db.get('HOST') or '(sqlite)')
print('needle=', NEEDLE, 'local=', local)

tel_q = Q(telefono__icontains=local) | Q(telefono__icontains=NEEDLE)
print('WhatsappLog matches=', WhatsappLog.objects.filter(tel_q).count())
print('--- WhatsappLog (30) ---')
for w in WhatsappLog.objects.filter(tel_q).order_by('-fecha')[:30]:
    msg = (w.mensaje or '').replace('\n', ' ')[:140]
    err = (w.error_detalle or '')[:120]
    print(
        f'{w.fecha.isoformat()} | {w.tipo} | {w.estado} | tel={w.telefono} '
        f'| sid={w.mensaje_id} | err={err!r} | msg={msg!r}'
    )

print('--- Estudiantes ---')
for e in Estudiante.objects.filter(tel_q)[:15]:
    print(f'id={e.id} nombre={e.nombre!r} tel={e.telefono} cliente_id={e.cliente_id}')

print('--- EnvioLog (20) ---')
for ev in (
    EnvioLog.objects.filter(
        Q(estudiante__telefono__icontains=local) | Q(estudiante__telefono__icontains=NEEDLE)
    )
    .select_related('campana', 'estudiante')
    .order_by('-fecha_envio')[:20]
):
    api = (ev.respuesta_api or '')[:180]
    print(
        f'{ev.fecha_envio.isoformat()} | campana_id={ev.campana_id} '
        f'nombre={ev.campana.nombre!r} | estado={ev.estado} | '
        f'est={ev.estudiante.nombre!r} | api={api!r}'
    )

now = timezone.now()
print('--- EnvioLog agregados últimas 12h ---')
for r in (
    EnvioLog.objects.filter(fecha_envio__gte=now - timedelta(hours=12))
    .values('campana_id', 'campana__nombre', 'estado')
    .annotate(n=Count('id'))
    .order_by('-n')[:20]
):
    print(r)

print('--- Campanas touched last 24h (by EnvioLog) ---')
for r in (
    EnvioLog.objects.filter(fecha_envio__gte=now - timedelta(hours=24))
    .values('campana_id', 'campana__nombre')
    .annotate(n=Count('id'))
    .order_by('-n')[:10]
):
    print(r)
    c = Campana.objects.filter(pk=r['campana_id']).first()
    if c:
        print(
            f"  campana estado={getattr(c, 'estado', None)!r} "
            f"fecha={getattr(c, 'fecha_envio', None) or getattr(c, 'updated_at', None)!r}"
        )
