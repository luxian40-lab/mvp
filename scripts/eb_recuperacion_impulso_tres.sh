#!/bin/bash
set -eu
export ELASTIC_BEANSTALK=true
GC=/opt/elasticbeanstalk/bin/get-config
for key in DB_NAME DB_USER DB_PASSWORD DB_HOST DB_PORT TWILIO_ACCOUNT_SID TWILIO_AUTH_TOKEN TWILIO_WHATSAPP_NUMBER TWILIO_PHONE_NUMBER TWILIO_WHATSAPP_FROM AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_STORAGE_BUCKET_NAME AWS_S3_REGION_NAME; do
  export "$key="$($GC environment -k $key 2>/dev/null)""
done
export USE_S3=True
export TWILIO_TEMPLATE_RECUPERACION_IMPULSO=HXa840d8b553291628e4746a5c22902eca
cd /var/app/current
source /var/app/venv/*/bin/activate
export PYTHONPATH=/var/app/current
export DJANGO_SETTINGS_MODULE=mvp_project.settings_production

python3 <<'PY'
import os
import django

django.setup()

from core.enviar_plantillas import enviar_plantilla_twilio
from core.models import Curso, Estudiante, Modulo, ModuloCompletado, ProgresoEstudiante

CONTENT_SID = os.environ.get(
    'TWILIO_TEMPLATE_RECUPERACION_IMPULSO',
    'HXa840d8b553291628e4746a5c22902eca',
)
IMPULSO_RECOVERY_TRES = {
    1963: {'nombre': 'Tatiana Nova', 'modulo_numero': 6, 'telefono': '573223032955'},
    1937: {'nombre': 'Yuli Andrea Nova', 'modulo_numero': 5, 'telefono': '573144346230'},
    1964: {'nombre': 'Sarita Diaz Usme', 'modulo_numero': 1, 'telefono': '573197239578'},
}


def curso_impulso():
    c = (
        Curso.objects.filter(nombre__icontains='impulso')
        .filter(nombre__icontains='rural')
        .order_by('id')
        .first()
    )
    return c or Curso.objects.filter(pk=22).first()


def modulo_por_numero(curso, numero):
    return Modulo.objects.filter(curso=curso, numero=numero).order_by('id').first()


def norm_tel(t):
    return ''.join(c for c in (t or '') if c.isdigit())


def rollback(apply=False):
    curso = curso_impulso()
    if not curso:
        raise SystemExit('[FAIL] Curso Impulso no encontrado')
    print(f'{"[DRY-RUN]" if not apply else "[APPLY]"} rollback — solo 3 estudiantes')
    print(f'Curso: {curso.nombre} (id={curso.id})\n')
    for est_id, cfg in IMPULSO_RECOVERY_TRES.items():
        est = Estudiante.objects.filter(pk=est_id).first()
        if not est:
            raise SystemExit(f'[FAIL] Estudiante {est_id} no existe')
        prog = ProgresoEstudiante.objects.filter(estudiante=est, curso=curso).select_related(
            'modulo_actual',
        ).first()
        if not prog:
            raise SystemExit(f'[FAIL] Sin progreso para {est_id} {cfg["nombre"]}')
        target_n = cfg['modulo_numero']
        target_mod = modulo_por_numero(curso, target_n)
        if not target_mod:
            raise SystemExit(f'[FAIL] Modulo M{target_n} no existe')
        antes_mod = prog.modulo_actual.numero if prog.modulo_actual_id else None
        antes_paso = prog.paso_actual_modulo
        borrar = ModuloCompletado.objects.filter(progreso=prog, modulo__numero__gte=target_n)
        n_borrar = borrar.count()
        print(
            f'  {est_id} {cfg["nombre"]}: M{antes_mod} paso {antes_paso} '
            f'-> M{target_n} paso 1 | borrar completados >= M{target_n}: {n_borrar}'
        )
        if not apply:
            continue
        borrar.delete()
        prog.modulo_actual = target_mod
        prog.paso_actual_modulo = 1
        prog.esperando_respuesta_evaluacion_paso = False
        prog.paso_evaluacion_paso = None
        prog.completado = False
        prog.save(
            update_fields=[
                'modulo_actual',
                'paso_actual_modulo',
                'esperando_respuesta_evaluacion_paso',
                'paso_evaluacion_paso',
                'completado',
            ]
        )
        if est.estado_onboarding in ('curso_finalizado', 'completado'):
            est.estado_onboarding = 'esperando_respuesta_modulo'
            est.save(update_fields=['estado_onboarding'])
    if apply:
        print('\n[OK] Rollback aplicado.')
    else:
        print('\n[DRY-RUN] Sin cambios.')


def send_tres():
    curso = curso_impulso()
    if not curso:
        raise SystemExit('[FAIL] Curso Impulso no encontrado')
    print(f'[SEND] plantilla recuperacion — solo 3 autorizadas')
    print(f'Content SID: {CONTENT_SID}\n')
    for est_id, cfg in IMPULSO_RECOVERY_TRES.items():
        est = Estudiante.objects.filter(pk=est_id).first()
        if not est:
            raise SystemExit(f'[FAIL] Estudiante {est_id} no encontrado')
        tel = norm_tel(est.telefono or cfg.get('telefono', ''))
        if not tel:
            raise SystemExit(f'[FAIL] Sin telefono para {est_id}')
        nombre = (est.nombre or cfg['nombre']).split()[0]
        variables = {
            '1': nombre,
            '2': 'Impulso Joven Rural',
            '3': f"Modulo {cfg['modulo_numero']}",
        }
        tel_e164 = f'+{tel}' if tel.startswith('57') else f'+57{tel}'
        print(f'  -> {est_id} {est.nombre} {tel_e164} vars={variables}')
        r = enviar_plantilla_twilio(tel_e164, CONTENT_SID, variables=variables)
        if not r.get('success'):
            raise SystemExit(f'[FAIL] {est_id}: {r}')
        print(f'     OK sid={r.get("mensaje_id")} status={r.get("status")}')
    print('\n[OK] Plantillas enviadas a las 3 estudiantes.')


rollback(apply=False)
rollback(apply=True)
send_tres()
PY
