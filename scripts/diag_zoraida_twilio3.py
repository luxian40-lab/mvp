"""Tercera pasada Zoraida/Impulso: estados, progreso, contexto examen, No entendí."""
from collections import Counter
from datetime import timedelta

from django.utils import timezone

from core.models import (
    Curso,
    Estudiante,
    Modulo,
    ModuloCompletado,
    ProgresoEstudiante,
    WhatsappLog,
)

CUT7 = timezone.now() - timedelta(days=7)
CUT10 = timezone.now() - timedelta(days=10)

print('== CURSO 22 FLAGS')
c = Curso.objects.filter(id=22).values(
    'id', 'nombre', 'activo', 'usar_agentes_ia', 'usar_gamificacion',
    'nombre_agente_tutor', 'nombre_agente_asistente',
).first()
print(c)

print('\n== MODULOS checkpoint / guia / publicado')
for m in Modulo.objects.filter(curso_id=22).order_by('numero'):
    print(
        f"  M{m.numero} id={m.id} pub={getattr(m, 'publicado_wa', None)} "
        f"chk={getattr(m, 'facilitador_checkpoint', None)} "
        f"tipo={(getattr(m, 'tipo_reto_ia', None) or '')[:24]!r} "
        f"guia_len={len(getattr(m, 'reto_guia_ia', None) or '')} "
        f"tit={(m.titulo or '')[:40]!r}"
    )

print('\n== ESTADOS ONBOARDING org 14')
cnt = Counter(
    Estudiante.objects.filter(cliente_id=14).values_list('estado_onboarding', flat=True)
)
for k, v in cnt.most_common():
    print(f'  {v:3d} {k}')

print('\n== PROGRESOS curso 22')
for p in (
    ProgresoEstudiante.objects.filter(curso_id=22)
    .select_related('estudiante', 'modulo_actual')
    .order_by('estudiante_id')
):
    e = p.estudiante
    ctx = e.contexto_temporal or {}
    n_done = ModuloCompletado.objects.filter(progreso=p).count()
    print(
        f"  est={e.id} {(e.nombre or '')[:28]!r} chat={e.estado_chat} "
        f"onb={e.estado_onboarding} ctx={ctx.get('tipo')} "
        f"mod_ctx={ctx.get('modulo_id')} preg_id={ctx.get('pregunta_id')} "
        f"prog_id_ctx={ctx.get('progreso_id')} "
        f"mod_act={getattr(p.modulo_actual, 'numero', None)} paso={p.paso_actual_modulo} "
        f"done_n={n_done} completado={p.completado} last={p.fecha_ultimo_avance}"
    )

print('\n== NO ENTENDI 7d (tels org 14)')
tels = [
    (t or '')[-10:]
    for t in Estudiante.objects.filter(cliente_id=14).values_list('telefono', flat=True)
    if t
]
qs = WhatsappLog.objects.filter(fecha__gte=CUT7, mensaje__icontains='No entendí')
n_all = qs.count()
n_org = 0
by_tel = Counter()
for log in qs.iterator():
    tail = (log.telefono or '')[-10:]
    if tail in tels:
        n_org += 1
        by_tel[tail] += 1
print(f'  total plataforma={n_all} org14={n_org}')
for tail, n in by_tel.most_common(15):
    est = Estudiante.objects.filter(cliente_id=14, telefono__endswith=tail).first()
    nom = (est.nombre or '')[:28] if est else '?'
    print(f'  n={n} …{tail[-4:]} {nom!r}')

print('\n== WHATSAPPLOG ESTADO 10d org14 (no PENDING/SENT vacio)')
estados = Counter()
errs = Counter()
for log in WhatsappLog.objects.filter(fecha__gte=CUT10).iterator():
    tail = (log.telefono or '')[-10:]
    if tail not in tels:
        continue
    estados[(log.tipo or ''), (log.estado or '')] += 1
    if log.error_detalle:
        errs[(log.estado or ''), (log.error_detalle or '')[:80]] += 1
print('  tipos/estados', dict(estados))
print('  errores', dict(errs) or 'NINGUNO')

print('\n== STUCK CTX KEYS')
for e in Estudiante.objects.filter(
    cliente_id=14,
    estado_onboarding__in=[
        'esperando_respuesta_asistente',
        'esperando_respuesta_reto',
        'esperando_respuesta_modulo',
    ],
):
    ctx = e.contexto_temporal or {}
    print(f"  {e.id} onb={e.estado_onboarding} keys={sorted(ctx.keys())} ctx={ {k: ctx.get(k) for k in ('tipo','modulo_id','pregunta_id','progreso_id','preguntas_hechas','es_final') if k in ctx} }")
