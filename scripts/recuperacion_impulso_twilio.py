#!/usr/bin/env python
"""
Recuperación Twilio — curso Impulso Joven Rural.

Subcomandos:
  create-template   Crea plantilla en Twilio y la envía a aprobación WhatsApp
  status            Consulta estado de aprobación (requiere --content-sid)
  send-qa           Envía SOLO a 3026480629 (requiere plantilla aprobada)
  send-tres         Envía plantilla solo a Tatiana, Yuli y Sarita (tras rollback)
  rollback-tres     Devuelve las 3 al módulo acordado (paso 1)
  list-afectados    Lista estudiantes con fallos de media (prod/RDS)

Reglas:
  - Variables {{1}}, {{2}}, {{3}}: solo texto, SIN emojis
  - Envío masivo: bloqueado hasta OK explícito del PM

Ejemplos:
  python scripts/recuperacion_impulso_twilio.py create-template
  python scripts/recuperacion_impulso_twilio.py status --content-sid HX...
  python scripts/recuperacion_impulso_twilio.py send-qa --content-sid HX...
  EKI_USE_REMOTE_DB=1 python scripts/recuperacion_impulso_twilio.py list-afectados
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.db.models import Q  # noqa: E402

TEL_QA = '573026480629'
CONTENT_SID_DEFAULT = 'HXa840d8b553291628e4746a5c22902eca'
CURSO_ID_IMPULSO = 22

# Solo estas tres (autorizacion PM 2026-09-01). Modulo = re-entrar desde ese numero (paso 1).
IMPULSO_RECOVERY_TRES = {
    1963: {'nombre': 'Tatiana Nova', 'modulo_numero': 6, 'telefono': '573223032955'},
    1937: {'nombre': 'Yuli Andrea Nova', 'modulo_numero': 5, 'telefono': '573144346230'},
    1964: {'nombre': 'Sarita Diaz Usme', 'modulo_numero': 1, 'telefono': '573197239578'},
}
TEMPLATE_NAME = 'eki_impulso_recuperacion_media_v1'
TEMPLATE_CATEGORY = 'UTILITY'
ENV_SID = 'TWILIO_TEMPLATE_RECUPERACION_IMPULSO'

# Cuerpo: variables sin emoji. Botón quick-reply Listo (mismo flujo del curso).
TEMPLATE_BODY = (
    'Hola {{1}},\n\n'
    'Tuvimos un inconveniente al enviarte material del curso {{2}} ({{3}}). '
    'Ya lo corregimos.\n\n'
    'Cuando puedas, toca Listo para continuar desde donde quedaste.'
)

# Samples para aprobación Twilio (sin emojis)
TEMPLATE_SAMPLES = {
    '1': 'Maria Fernanda',
    '2': 'Impulso Joven Rural',
    '3': 'Modulo 8 Finanzas rurales',
}

_EMOJI_RE = re.compile(
    '['
    '\U0001F300-\U0001FAFF'
    '\U00002600-\U000027BF'
    '\U0001F600-\U0001F64F'
    ']+',
    flags=re.UNICODE,
)


def _twilio_client():
    from twilio.rest import Client

    sid = (getattr(settings, 'TWILIO_ACCOUNT_SID', None) or '').strip()
    token = (getattr(settings, 'TWILIO_AUTH_TOKEN', None) or '').strip()
    if not sid or not token:
        raise RuntimeError('TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN no configurados')
    return Client(sid, token)


def _sin_emoji(val: str, campo: str) -> str:
    if _EMOJI_RE.search(val or ''):
        raise ValueError(f'Variable {campo} no puede contener emojis: {val!r}')
    return (val or '').strip()


def cmd_create_template(_args) -> int:
    import requests
    from twilio.rest.content.v1.content import ApprovalCreateList

    account_sid = (getattr(settings, 'TWILIO_ACCOUNT_SID', None) or '').strip()
    auth_token = (getattr(settings, 'TWILIO_AUTH_TOKEN', None) or '').strip()
    if not account_sid or not auth_token:
        print('[FAIL] TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN no configurados')
        return 1

    print('[INFO] Creando Content Template en Twilio (REST API)...')
    print(f'       friendly_name: {TEMPLATE_NAME}')
    print(f'       body:\n{TEMPLATE_BODY}\n')

    payload = {
        'friendly_name': TEMPLATE_NAME,
        'language': 'es',
        'variables': TEMPLATE_SAMPLES,
        'types': {
            'twilio/quick-reply': {
                'body': TEMPLATE_BODY,
                'actions': [{'title': 'Listo', 'id': 'listo'}],
            },
        },
    }
    resp = requests.post(
        'https://content.twilio.com/v1/Content',
        auth=(account_sid, auth_token),
        json=payload,
        timeout=60,
    )
    if resp.status_code >= 400:
        print(f'[FAIL] Twilio {resp.status_code}: {resp.text}')
        return 1
    data = resp.json()
    hx = data.get('sid') or ''
    print(f'[OK] Content creado: {hx}')

    client = _twilio_client()
    print('[INFO] Enviando a aprobación WhatsApp (categoría UTILITY)...')
    try:
        approval = client.content.v1.contents(hx).approval_create.create(
            content_approval_request=ApprovalCreateList.ContentApprovalRequest(
                {'name': TEMPLATE_NAME, 'category': TEMPLATE_CATEGORY},
            ),
        )
        estado = getattr(approval, 'status', None) or str(approval)
        print(f'[OK] Solicitud de aprobación enviada: {estado}')
    except Exception as exc:
        print(f'[WARN] No se pudo solicitar aprobación automática: {exc}')
        print('       Revisar en Twilio Console → Content → Submit for WhatsApp')

    print('\n--- Siguiente paso ---')
    print(f'export {ENV_SID}={hx}')
    print(f'python scripts/recuperacion_impulso_twilio.py status --content-sid {hx}')
    print('Cuando status = approved -> send-qa')
    return 0


def cmd_status(args) -> int:
    from core.twilio_content_preview import fetch_content_preview

    hx = (args.content_sid or os.environ.get(ENV_SID) or '').strip()
    if not hx:
        print('[FAIL] Pasa --content-sid HX... o define TWILIO_TEMPLATE_RECUPERACION_IMPULSO')
        return 1
    data = fetch_content_preview(hx)
    print(json.dumps(data, ensure_ascii=False, indent=2))
    approval = (data.get('approval') or '').lower()
    if 'approv' in approval and 'reject' not in approval and 'pending' not in approval:
        print('\n[OK] Plantilla lista para send-qa')
        return 0
    if 'pending' in approval or not approval:
        print('\n[WAIT] Aún en revisión Meta/Twilio (suele tardar 5 min – 24 h)')
        return 0
    print('\n[WARN] Revisar estado en Twilio Console')
    return 0


def cmd_send_qa(args) -> int:
    from core.enviar_plantillas import enviar_plantilla_twilio
    from core.twilio_content_preview import fetch_content_preview

    tel = ''.join(c for c in TEL_QA if c.isdigit())
    if not tel.endswith('3026480629'):
        print('[FAIL] send-qa solo permite 3026480629')
        return 1

    hx = (args.content_sid or os.environ.get(ENV_SID) or '').strip()
    if not hx:
        print('[FAIL] Sin Content SID')
        return 1

    preview = fetch_content_preview(hx)
    approval = (preview.get('approval') or '').lower()
    if args.require_approved and 'approv' not in approval:
        print(f'[FAIL] Plantilla no aprobada aún: {preview.get("approval")!r}')
        print('       Usa --force para omitir (solo debug)')
        return 1

    variables = dict(TEMPLATE_SAMPLES)
    for item in args.var or []:
        k, v = item.split('=', 1)
        variables[k.strip()] = _sin_emoji(v, k)

    for k, v in variables.items():
        _sin_emoji(v, k)

    tel_e164 = f'+{tel}' if tel.startswith('57') else f'+57{tel}'
    print(f'Enviando a {tel_e164} | SID {hx}')
    print(f'Variables: {json.dumps(variables, ensure_ascii=False)}')

    r = enviar_plantilla_twilio(tel_e164, hx, variables=variables)
    print(json.dumps(r, ensure_ascii=False, indent=2))
    if r.get('success'):
        print('\n[OK] Revisa WhatsApp. Si el texto se ve bien, confirma para rollback + envío masivo.')
        return 0
    return 1


def _norm_tel(t: str) -> str:
    return ''.join(c for c in (t or '') if c.isdigit())


def _resolver_curso_impulso():
    from core.models import Curso

    curso = (
        Curso.objects.filter(nombre__icontains='impulso')
        .filter(nombre__icontains='rural')
        .order_by('id')
        .first()
    )
    if not curso:
        curso = Curso.objects.filter(pk=22).first()
    return curso


def _curso_impulso():
    return _resolver_curso_impulso()


def _modulo_por_numero(curso, numero: int):
    from core.models import Modulo

    return Modulo.objects.filter(curso=curso, numero=numero).order_by('id').first()


def cmd_rollback_tres(args) -> int:
    from core.models import Estudiante, ModuloCompletado, ProgresoEstudiante

    curso = _curso_impulso()
    if not curso:
        print('[FAIL] Curso Impulso no encontrado')
        return 1

    dry = not getattr(args, 'apply', False)
    print(f'{"[DRY-RUN]" if dry else "[APPLY]"} rollback Impulso — solo 3 estudiantes')
    print(f'Curso: {curso.nombre} (id={curso.id})\n')

    for est_id, cfg in IMPULSO_RECOVERY_TRES.items():
        est = Estudiante.objects.filter(pk=est_id).first()
        if not est:
            print(f'[FAIL] Estudiante {est_id} no existe')
            return 1
        prog = ProgresoEstudiante.objects.filter(estudiante=est, curso=curso).select_related(
            'modulo_actual',
        ).first()
        if not prog:
            print(f'[FAIL] Sin progreso curso 22 para {est_id} {cfg["nombre"]}')
            return 1

        target_n = cfg['modulo_numero']
        target_mod = _modulo_por_numero(curso, target_n)
        if not target_mod:
            print(f'[FAIL] Modulo M{target_n} no existe en curso {curso.id}')
            return 1

        antes_mod = prog.modulo_actual.numero if prog.modulo_actual_id else None
        antes_paso = prog.paso_actual_modulo
        borrar = ModuloCompletado.objects.filter(
            progreso=prog,
            modulo__numero__gte=target_n,
        )
        n_borrar = borrar.count()

        print(
            f'  {est_id} {cfg["nombre"]}: M{antes_mod} paso {antes_paso} '
            f'-> M{target_n} paso 1 | borrar completados >= M{target_n}: {n_borrar}'
        )

        if dry:
            continue

        borrar.delete()
        prog.modulo_actual = target_mod
        prog.paso_actual_modulo = 1
        prog.esperando_respuesta_evaluacion_paso = False
        prog.paso_evaluacion_paso = None
        prog.completado = False
        prog.save(update_fields=[
            'modulo_actual', 'paso_actual_modulo',
            'esperando_respuesta_evaluacion_paso', 'paso_evaluacion_paso', 'completado',
        ])
        if est.estado_onboarding in ('curso_finalizado', 'completado'):
            est.estado_onboarding = 'esperando_respuesta_modulo'
            est.save(update_fields=['estado_onboarding'])

    if dry:
        print('\n[DRY-RUN] Sin cambios. Para aplicar: rollback-tres --apply')
    else:
        print('\n[OK] Rollback aplicado. Siguiente: send-tres')
    return 0


def cmd_send_tres(args) -> int:
    from core.enviar_plantillas import enviar_plantilla_twilio
    from core.models import Estudiante

    hx = (args.content_sid or os.environ.get(ENV_SID) or CONTENT_SID_DEFAULT).strip()
    curso = _curso_impulso()
    if not curso:
        print('[FAIL] Curso Impulso no encontrado')
        return 1

    dry = getattr(args, 'dry_run', False)
    print(f'{"[DRY-RUN]" if dry else "[SEND]"} plantilla recuperacion — solo 3 autorizadas')
    print(f'Content SID: {hx}\n')

    for est_id, cfg in IMPULSO_RECOVERY_TRES.items():
        est = Estudiante.objects.filter(pk=est_id).first()
        if not est:
            print(f'[FAIL] Estudiante {est_id} no encontrado')
            return 1
        tel = _norm_tel(est.telefono or cfg.get('telefono', ''))
        if not tel:
            print(f'[FAIL] Sin telefono para {est_id}')
            return 1
        variables = {
            '1': _sin_emoji(est.nombre.split()[0] if est.nombre else cfg['nombre'], '1'),
            '2': 'Impulso Joven Rural',
            '3': f"Modulo {cfg['modulo_numero']}",
        }
        tel_e164 = f'+{tel}' if tel.startswith('57') else f'+57{tel}'
        print(f'  -> {est_id} {est.nombre} {tel_e164} vars={variables}')
        if dry:
            continue
        r = enviar_plantilla_twilio(tel_e164, hx, variables=variables)
        if not r.get('success'):
            print(f'[FAIL] {est_id}: {r}')
            return 1
        print(f'     OK sid={r.get("mensaje_id")} status={r.get("status")}')

    if dry:
        print('\n[DRY-RUN] Para enviar: send-tres')
    else:
        print('\n[OK] Plantillas enviadas a las 3 estudiantes.')
    return 0


def cmd_list_afectados(args) -> int:
    from core.models import (
        Curso,
        Estudiante,
        EstudianteEventoAprendizaje,
        ProgresoEstudiante,
        WhatsappLog,
    )
    from core.models_media_entrega import MediaPaqueteEntrega

    curso = _resolver_curso_impulso()
    if not curso:
        print('[FAIL] No se encontró curso Impulso Rural en esta BD')
        return 1

    print(f'Curso: {curso.nombre} (id={curso.id})')
    print(f'BD: {settings.DATABASES["default"].get("ENGINE", "?")}')
    print('=' * 72)

    tel_progreso = {
        _norm_tel(t): eid
        for eid, t in ProgresoEstudiante.objects.filter(curso=curso)
        .values_list('estudiante_id', 'estudiante__telefono')
    }

    # --- A) MediaPaqueteEntrega fallido ---
    paquetes = list(
        MediaPaqueteEntrega.objects.filter(curso=curso, estado=MediaPaqueteEntrega.ESTADO_FALLIDO)
        .select_related('estudiante', 'modulo')
        .order_by('telefono', 'creado_en')
    )

    # --- B) Eventos media_fallida ---
    eventos = list(
        EstudianteEventoAprendizaje.objects.filter(
            curso=curso,
            tipo=EstudianteEventoAprendizaje.TIPO_MEDIA_FALLIDA,
        )
        .select_related('estudiante', 'modulo', 'paso')
        .order_by('estudiante_id', 'created_at')
    )

    # --- C) WhatsappLog con error Twilio (estudiantes del curso) ---
    est_ids_curso = set(tel_progreso.values())
    tels_curso = set(tel_progreso.keys())
    logs = []
    q_logs = WhatsappLog.objects.filter(tipo='SENT').filter(
        Q(estado__in=('ERROR', 'FAILED', 'UNDELIVERED', 'failed', 'undelivered'))
        | Q(error_detalle__icontains='63019')
        | Q(error_detalle__icontains='63021')
        | Q(error_detalle__icontains='63005')
    )
    for lg in q_logs.order_by('-fecha')[:8000]:
        nt = _norm_tel(lg.telefono)
        ok = lg.estudiante_id in est_ids_curso
        if not ok and nt in tels_curso:
            ok = True
        if not ok:
            for t in tels_curso:
                if len(nt) >= 10 and len(t) >= 10 and nt[-10:] == t[-10:]:
                    ok = True
                    break
        if ok:
            logs.append(lg)

    # Unificar por estudiante
    filas: dict[int, dict] = {}

    def _upsert(est_id, telefono, nombre, fuente, cuando, modulo=None, detalle=''):
        if not est_id and telefono:
            est = Estudiante.objects.filter(telefono__contains=telefono[-10:]).first()
            if est:
                est_id = est.id
                nombre = est.nombre
        if not est_id:
            return
        row = filas.get(est_id) or {
            'estudiante_id': est_id,
            'nombre': nombre or '',
            'telefono': telefono or '',
            'primer_fallo': cuando,
            'fuentes': set(),
            'modulos': set(),
            'detalle': '',
        }
        if cuando and (not row['primer_fallo'] or cuando < row['primer_fallo']):
            row['primer_fallo'] = cuando
        row['fuentes'].add(fuente)
        if modulo:
            row['modulos'].add(str(modulo))
        if detalle and not row['detalle']:
            row['detalle'] = detalle[:120]
        filas[est_id] = row

    for p in paquetes:
        mod = f'M{p.modulo.numero}' if p.modulo_id and p.modulo else '?'
        _upsert(
            p.estudiante_id,
            p.telefono,
            getattr(p.estudiante, 'nombre', ''),
            'MediaPaqueteEntrega',
            p.creado_en,
            mod,
            f'code={p.error_code}',
        )

    for ev in eventos:
        mod = f'M{ev.modulo.numero}' if ev.modulo_id else '?'
        _upsert(
            ev.estudiante_id,
            ev.estudiante.telefono if ev.estudiante_id else '',
            getattr(ev.estudiante, 'nombre', ''),
            'EventoAprendizaje',
            ev.created_at,
            mod,
            (ev.metadata or {}).get('error_code', ''),
        )

    for lg in logs:
        est_id = lg.estudiante_id
        nt = _norm_tel(lg.telefono)
        if not est_id:
            for t, eid in tel_progreso.items():
                if t.endswith(nt[-10:]) or nt.endswith(t[-10:]):
                    est_id = eid
                    break
        _upsert(
            est_id,
            lg.telefono,
            getattr(lg.estudiante, 'nombre', '') if lg.estudiante_id else '',
            'WhatsappLog',
            lg.fecha,
            '',
            (lg.error_detalle or lg.estado or '')[:120],
        )

    if not filas:
        print('Sin registros de fallo para este curso en esta BD.')
        print('Tip: EKI_USE_REMOTE_DB=1 y DATABASE_URL de prod si estás en local.')
        return 0

    ordenados = sorted(filas.values(), key=lambda r: (r['primer_fallo'] or datetime.min, r['nombre']))

    print(f'Total estudiantes afectados (union A+B+C): {len(ordenados)}\n')
    print(f'{"ID":>6}  {"Teléfono":<14}  {"Nombre":<28}  {"1er fallo":<20}  Fuentes  Módulos')
    print('-' * 100)
    for r in ordenados:
        pf = r['primer_fallo'].strftime('%Y-%m-%d %H:%M') if r['primer_fallo'] else '-'
        mods = ','.join(sorted(r['modulos'])) if r['modulos'] else '-'
        fnts = ','.join(sorted(r['fuentes']))
        nombre = (r['nombre'] or '')[:28]
        tel = (r['telefono'] or '')[-14:]
        print(f'{r["estudiante_id"]:>6}  {tel:<14}  {nombre:<28}  {pf:<20}  {fnts:<20}  {mods}')

    if args.json:
        out = []
        for r in ordenados:
            out.append({
                **r,
                'primer_fallo': r['primer_fallo'].isoformat() if r['primer_fallo'] else None,
                'fuentes': sorted(r['fuentes']),
                'modulos': sorted(r['modulos']),
            })
        print('\n' + json.dumps(out, ensure_ascii=False, indent=2))

    print('\n--- Desglose fuentes ---')
    print(f'  MediaPaqueteEntrega fallido : {len(paquetes)} registros')
    print(f'  Evento media_fallida        : {len(eventos)} registros')
    print(f'  WhatsappLog error           : {len(logs)} registros (últimos 5000 SENT)')
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description='Recuperación Twilio Impulso Rural')
    sub = parser.add_subparsers(dest='cmd', required=True)

    sub.add_parser('create-template', help='Crear plantilla HX y solicitar aprobación WhatsApp')

    p_st = sub.add_parser('status', help='Estado aprobación plantilla')
    p_st.add_argument('--content-sid', default='')

    p_sq = sub.add_parser('send-qa', help='Enviar plantilla solo a 3026480629')
    p_sq.add_argument('--content-sid', default='')
    p_sq.add_argument('--var', action='append', default=[], metavar='N=valor')
    p_sq.add_argument('--require-approved', action='store_true', default=True)
    p_sq.add_argument('--force', action='store_true', help='Enviar aunque no esté approved')

    p_rb = sub.add_parser('rollback-tres', help='Rollback Tatiana, Yuli, Sarita (solo 3)')
    p_rb.add_argument('--apply', action='store_true', help='Aplicar cambios en BD (default dry-run)')

    p_st3 = sub.add_parser('send-tres', help='Enviar plantilla solo a las 3 autorizadas')
    p_st3.add_argument('--content-sid', default='')
    p_st3.add_argument('--dry-run', action='store_true')

    p_la = sub.add_parser('list-afectados', help='Lista estudiantes con fallos de media')
    p_la.add_argument('--json', action='store_true')

    args = parser.parse_args()
    if args.cmd == 'send-qa' and getattr(args, 'force', False):
        args.require_approved = False

    handlers = {
        'create-template': cmd_create_template,
        'status': cmd_status,
        'send-qa': cmd_send_qa,
        'rollback-tres': cmd_rollback_tres,
        'send-tres': cmd_send_tres,
        'list-afectados': cmd_list_afectados,
    }
    return handlers[args.cmd](args)


if __name__ == '__main__':
    raise SystemExit(main())
