"""Diagnóstico: curso Zoraida / Impulso — fallos Twilio y agentes IA.

Solo lectura. Resume logs, no imprime cédulas ni mensajes completos.
"""
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from core.models import (
    Cliente,
    Curso,
    Estudiante,
    Modulo,
    PasoModulo,
    ProgresoEstudiante,
    WhatsappLog,
)

CUT = timezone.now() - timedelta(hours=48)

print('== CURSO / ORG ZORAIDA')
clientes = list(
    Cliente.objects.filter(
        Q(nombre__icontains='zoraida') | Q(nombre__icontains='nogales') | Q(nombre__icontains='cultivarte')
    ).values('id', 'nombre', 'activo')
)
print('  clientes', clientes)
cursos = list(
    Curso.objects.filter(
        Q(nombre__icontains='impulso')
        | Q(cliente__nombre__icontains='zoraida')
        | Q(cliente__nombre__icontains='nogales')
        | Q(cliente__nombre__icontains='cultivarte')
    ).values('id', 'nombre', 'activo', 'cliente_id', 'usar_agentes_ia', 'nombre_agente_tutor', 'nombre_agente_asistente')
)
print('  cursos', cursos)
curso_ids = [c['id'] for c in cursos]
cliente_ids = [c['id'] for c in clientes]

print('\n== ESTUDIANTES (48h de actividad o inscritos)')
ests = Estudiante.objects.filter(
    Q(cliente_id__in=cliente_ids) | Q(progresos__curso_id__in=curso_ids)
).distinct()
print('  n=', ests.count())
for e in ests.order_by('id')[:40]:
    tel = (e.telefono or '')[-4:]
    print(
        f"  est={e.id} nom={(e.nombre or '')[:40]!r} …{tel} "
        f"chat={e.estado_chat} onb={e.estado_onboarding} "
        f"ctx={(e.contexto_temporal or {}).get('tipo')}"
    )

print('\n== PROGRESOS')
for p in ProgresoEstudiante.objects.filter(curso_id__in=curso_ids).select_related('estudiante', 'curso', 'modulo_actual'):
    print(
        f"  prog={p.id} est={p.estudiante_id} curso={p.curso_id} "
        f"mod={getattr(p.modulo_actual, 'numero', None)} "
        f"paso={p.paso_actual_modulo} done={p.completado}"
    )

print('\n== PASOS CON MEDIA (curso)')
for paso in (
    PasoModulo.objects.filter(modulo__curso_id__in=curso_ids)
    .exclude(media_url='')
    .exclude(media_url__isnull=True)
    .select_related('modulo')
    .order_by('modulo__numero', 'orden')
):
    url = (paso.media_url or '')
    print(
        f"  p{paso.id} M{paso.modulo.numero} o={paso.orden} apto={paso.media_wa_apto} "
        f"tit={(paso.titulo or '')[:40]!r} url={url[-70:]}"
    )

print('\n== WHATSAPPLOG FAILED / undelivered 48h (estudiantes del curso o teléfonos recientes)')
est_ids = list(ests.values_list('id', flat=True))
qs_fail = WhatsappLog.objects.filter(fecha__gte=CUT).filter(
    Q(estudiante_id__in=est_ids)
    | Q(estado__icontains='fail')
    | Q(estado__icontains='undeliver')
    | Q(error_detalle__icontains='630')
)
# restringir a org si hay muchos
fails = list(
    WhatsappLog.objects.filter(fecha__gte=CUT)
    .filter(Q(estudiante_id__in=est_ids) | Q(error_detalle__regex=r'630(19|21|05)'))
    .order_by('-fecha')[:40]
)
print('  n_muestra', len(fails))
for log in fails:
    msg = (log.mensaje or '').replace('\n', ' ')[:90]
    err = (log.error_detalle or '')[:120]
    print(
        f"  [{log.fecha:%d/%m %H:%M}] tipo={log.tipo} est={log.estado} "
        f"agente={log.agente_usado!r} sid={(log.mensaje_id or '')[:10]} "
        f"err={err!r} body={msg!r}"
    )

print('\n== ULTIMOS 25 MENSAJES ESTUDIANTES DEL CURSO')
for log in WhatsappLog.objects.filter(estudiante_id__in=est_ids).order_by('-fecha')[:25]:
    msg = (log.mensaje or '').replace('\n', ' ')[:100]
    print(
        f"  [{log.fecha:%d/%m %H:%M}] {log.tipo:8} {log.estado:12} "
        f"ag={log.agente_usado or '-':16} {msg!r}"
    )

print('\n== MODULOS CHECKPOINT')
for m in Modulo.objects.filter(curso_id__in=curso_ids).order_by('numero'):
    print(
        f"  M{m.numero} id={m.id} pub={m.publicado_wa} cp={m.facilitador_checkpoint} "
        f"tipo={m.tipo_reto_ia!r} guia_len={len(m.reto_guia_ia or '')} tit={m.titulo!r}"
    )
