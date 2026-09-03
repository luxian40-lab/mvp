#!/bin/bash
# Diagnostico Impulso: estudiantes con senales de error Twilio/media (prod).
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
from django.db.models import Q, Count
from core.models import Curso, Estudiante, ModuloCompletado, ProgresoEstudiante, WhatsappLog
from core.models_media_entrega import MediaPaqueteEntrega
from datetime import timedelta
from django.utils import timezone

def norm(t):
    return ''.join(c for c in (t or '') if c.isdigit())

curso = Curso.objects.filter(pk=22).first()
print('CURSO', curso.id, curso.nombre)

progresos = list(
    ProgresoEstudiante.objects.filter(curso=curso)
    .select_related('estudiante', 'modulo_actual')
    .order_by('estudiante_id')
)
print('INSCRITOS', len(progresos))

# Mapa telefono -> estudiante
tel_suffixes = {}
for p in progresos:
    nt = norm(p.estudiante.telefono)
    tel_suffixes[nt[-10:]] = p

desde = timezone.now() - timedelta(days=120)
filas = {}

def add(est_id, nombre, tel, motivo, detalle='', mod=''):
    r = filas.get(est_id) or {
        'id': est_id, 'nombre': nombre, 'tel': tel,
        'motivos': set(), 'detalles': [], 'mod': mod,
    }
    r['motivos'].add(motivo)
    if detalle and detalle not in r['detalles']:
        r['detalles'].append(detalle[:100])
    if mod and not r['mod']:
        r['mod'] = mod
    filas[est_id] = r

# 1) Paquetes media fallidos
for p in MediaPaqueteEntrega.objects.filter(curso=curso, estado='fallido').select_related('estudiante', 'modulo'):
    mod = f"M{p.modulo.numero}" if p.modulo_id else '?'
    add(p.estudiante_id, getattr(p.estudiante, 'nombre', ''), p.telefono, 'paquete_fallido', p.error_code, mod)

# 2) Logs Whatsapp con error para telefonos del curso (ultimos 120 dias)
for lg in WhatsappLog.objects.filter(fecha__gte=desde).order_by('-fecha'):
    nt = norm(lg.telefono)
    suf = nt[-10:] if len(nt) >= 10 else nt
    prog = tel_suffixes.get(suf)
    if not prog and lg.estudiante_id:
        prog = next((p for p in progresos if p.estudiante_id == lg.estudiante_id), None)
    if not prog:
        continue
    det = (lg.error_detalle or '') + ' ' + (lg.estado or '')
    bad = any(x in det for x in ('63019', '63021', '63005', 'FAILED', 'UNDELIVERED', 'ERROR', 'failed'))
    if not bad and lg.tipo == 'SENT' and lg.estado and lg.estado.upper() not in ('SENT', 'DELIVERED', 'READ', 'PENDING'):
        bad = True
    if bad:
        mod = f"M{prog.modulo_actual.numero}" if prog.modulo_actual_id else '-'
        add(prog.estudiante_id, prog.estudiante.nombre, prog.estudiante.telefono, 'log_twilio', det.strip()[:80], mod)

# 3) Mensajes entrantes pidiendo reenvio (reenvia / no llego)
keywords = ('reenvi', 'no lleg', 'no me lleg', 'video', 'error', 'fall', 'problema')
for lg in WhatsappLog.objects.filter(tipo='INCOMING', fecha__gte=desde).order_by('-fecha'):
    nt = norm(lg.telefono)
    suf = nt[-10:] if len(nt) >= 10 else nt
    prog = tel_suffixes.get(suf)
    if not prog:
        continue
    msg = (lg.mensaje or '').lower()
    if any(k in msg for k in keywords):
        mod = f"M{prog.modulo_actual.numero}" if prog.modulo_actual_id else '-'
        add(prog.estudiante_id, prog.estudiante.nombre, prog.estudiante.telefono, 'queja_estudiante', (lg.mensaje or '')[:80], mod)

# 4) Estudiantes en M8+ sin completar (ventana tipica de videos rotos)
for p in progresos:
    if p.completado:
        continue
    if p.modulo_actual_id and p.modulo_actual.numero >= 8:
        add(p.estudiante_id, p.estudiante.nombre, p.estudiante.telefono, 'atascado_m8plus', f'paso={p.paso_actual_modulo}', f"M{p.modulo_actual.numero}")

rows = sorted(filas.values(), key=lambda r: r['nombre'])
print('TOTAL_CANDIDATOS', len(rows))
print('ID\tTelefono\tNombre\tModuloActual\tMotivos\tDetalle')
for r in rows:
    print(
        f"{r['id']}\t{r['tel']}\t{r['nombre']}\t{r['mod']}\t"
        f"{','.join(sorted(r['motivos']))}\t{' | '.join(r['detalles'][:2])}"
    )

# Resumen todos los inscritos (contexto)
print('\n--- TODOS_INSCRITOS ---')
print('ID\tTelefono\tNombre\tModuloActual\tPaso\tCompletado')
for p in progresos:
    mod = f"M{p.modulo_actual.numero}" if p.modulo_actual_id else '-'
    print(f"{p.estudiante_id}\t{p.estudiante.telefono}\t{p.estudiante.nombre}\t{mod}\t{p.paso_actual_modulo}\t{p.completado}")
PY
