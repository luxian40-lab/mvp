#!/bin/bash
# Diagnostico ampliado: fallos Twilio + estudiantes Impulso Rural (prod).
set -eu
export ELASTIC_BEANSTALK=true
GC=/opt/elasticbeanstalk/bin/get-config
for key in DB_NAME DB_USER DB_PASSWORD DB_HOST DB_PORT; do
  export "$key=$($GC environment -k $key 2>/dev/null)"
done
export DJANGO_SETTINGS_MODULE=mvp_project.settings_production
cd /var/app/current
source /var/app/venv/*/bin/activate
python3 <<'PY'
import django
django.setup()
from django.db.models import Q
from core.models import Curso, Estudiante, EstudianteEventoAprendizaje, ProgresoEstudiante, WhatsappLog
from core.models_media_entrega import MediaPaqueteEntrega
from datetime import datetime

def norm(t):
    return ''.join(c for c in (t or '') if c.isdigit())

curso = Curso.objects.filter(nombre__icontains='impulso').filter(nombre__icontains='rural').first()
print('CURSO', curso.id, curso.nombre)

progresos = list(
    ProgresoEstudiante.objects.filter(curso=curso)
    .select_related('estudiante', 'modulo_actual')
    .order_by('estudiante_id')
)
print('INSCRITOS', len(progresos))

est_ids = {p.estudiante_id for p in progresos}
tel_map = {norm(p.estudiante.telefono): p for p in progresos}

filas = {}

def upsert(est_id, tel, nombre, fuente, cuando, mod='', det=''):
    if not est_id and tel:
        est = Estudiante.objects.filter(telefono__contains=tel[-10:]).first()
        if est:
            est_id, nombre = est.id, est.nombre
    if not est_id:
        return
    r = filas.get(est_id) or {'id': est_id, 'nombre': nombre or '', 'tel': tel or '', 'pf': cuando, 'f': set(), 'm': set(), 'det': ''}
    if cuando and (not r['pf'] or cuando < r['pf']):
        r['pf'] = cuando
    r['f'].add(fuente)
    if mod:
        r['m'].add(mod)
    if det and not r['det']:
        r['det'] = det[:120]
    filas[est_id] = r

for p in MediaPaqueteEntrega.objects.filter(curso=curso, estado='fallido').select_related('estudiante', 'modulo'):
    mod = f"M{p.modulo.numero}" if p.modulo_id else '?'
    upsert(p.estudiante_id, p.telefono, getattr(p.estudiante, 'nombre', ''), 'Paquete', p.creado_en, mod, p.error_code)

for ev in EstudianteEventoAprendizaje.objects.filter(curso=curso, tipo='media_fallida').select_related('estudiante', 'modulo'):
    mod = f"M{ev.modulo.numero}" if ev.modulo_id else '?'
    upsert(ev.estudiante_id, ev.estudiante.telefono if ev.estudiante_id else '', getattr(ev.estudiante, 'nombre', ''), 'Evento', ev.created_at, mod, str((ev.metadata or {}).get('error_code', '')))

q = WhatsappLog.objects.filter(tipo='SENT').filter(
    Q(estado__in=('ERROR', 'FAILED', 'UNDELIVERED', 'failed', 'undelivered'))
    | Q(error_detalle__icontains='63019')
    | Q(error_detalle__icontains='63021')
    | Q(error_detalle__icontains='63005')
)
matched = 0
unmatched = []
for lg in q.order_by('-fecha')[:8000]:
    nt = norm(lg.telefono)
    ok = lg.estudiante_id in est_ids
    if not ok:
        for t, prog in tel_map.items():
            if len(nt) >= 10 and len(t) >= 10 and nt[-10:] == t[-10:]:
                ok = True
                lg.estudiante_id = prog.estudiante_id
                break
    if ok:
        matched += 1
        upsert(lg.estudiante_id, lg.telefono, getattr(lg.estudiante, 'nombre', '') if lg.estudiante_id else '', 'Log', lg.fecha, '', (lg.error_detalle or lg.estado or '')[:80])
    elif len(unmatched) < 15:
        unmatched.append((lg.fecha, lg.telefono, lg.estado, (lg.error_detalle or '')[:60]))

rows = sorted(filas.values(), key=lambda r: (r['pf'] or datetime.min, r['nombre']))
print('LOGS_MATCH_CURSO', matched)
print('TOTAL_AFECTADOS', len(rows))
print('--- LISTA ---')
print('ID\tTelefono\tNombre\tModuloActual\tPrimerFallo\tFuentes\tModulosFallo\tDetalle')
for r in rows:
    pf = r['pf'].strftime('%Y-%m-%d %H:%M') if r['pf'] else '-'
    prog = ProgresoEstudiante.objects.filter(curso=curso, estudiante_id=r['id']).select_related('modulo_actual').first()
    mod_act = f"M{prog.modulo_actual.numero}" if prog and prog.modulo_actual_id else '-'
    print(f"{r['id']}\t{r['tel']}\t{r['nombre']}\t{mod_act}\t{pf}\t{','.join(sorted(r['f']))}\t{','.join(sorted(r['m'])) or '-'}\t{r['det']}")

if unmatched:
    print('--- LOGS_ERROR_SIN_MATCH_CURSO (muestra) ---')
    for f, t, st, det in unmatched:
        print(f, t, st, det)
PY
