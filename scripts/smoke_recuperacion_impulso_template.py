#!/usr/bin/env python
"""
Paso 1 — Prueba controlada plantilla recuperación Impulso Rural.

Envía SOLO al teléfono QA autorizado (default 573026480629) para validar
UTF-8, acentos, emojis y variables del Content Template antes de cualquier
envío masivo.

Uso (local con credenciales Twilio en .env):
  python scripts/smoke_recuperacion_impulso_template.py --dry-run
  python scripts/smoke_recuperacion_impulso_template.py --send

En EB prod (misma shell que otros smokes):
  export TWILIO_TEMPLATE_RECUPERACION_IMPULSO=HXxxxxxxxx
  python scripts/smoke_recuperacion_impulso_template.py --send

Variables del template: por defecto {"1": nombre, "2": curso, "3": módulo}.
Ajustar con --var 1="Julián" --var 2="Impulso Joven Rural" ...
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402

from core.enviar_plantillas import enviar_plantilla_twilio  # noqa: E402
from core.twilio_content_preview import fetch_content_preview  # noqa: E402

TEL_QA_DEFAULT = '573026480629'
CURSO_NOMBRE_FILTRO = 'Impulso Joven Rural'
ENV_CONTENT_SID = 'TWILIO_TEMPLATE_RECUPERACION_IMPULSO'
ENV_FALLBACK_SID = 'TWILIO_TEMPLATE_DRIP_REENGANCHE'


def _resolver_content_sid(explicit: str | None) -> str:
    if explicit and explicit.strip():
        return explicit.strip()
    sid = (os.environ.get(ENV_CONTENT_SID) or '').strip()
    if sid:
        return sid
    sid = (getattr(settings, ENV_CONTENT_SID, None) or '').strip()
    if sid:
        return sid
    sid = (os.environ.get(ENV_FALLBACK_SID) or '').strip()
    if sid:
        return sid
    sid = (getattr(settings, ENV_FALLBACK_SID, None) or '').strip()
    if sid:
        return sid
    # Último recurso: plantilla en BD (admin → Plantillas)
    try:
        from core.models import Plantilla

        pl = (
            Plantilla.objects.filter(activa=True, twilio_template_sid__startswith='HX')
            .filter(nombre_interno__icontains='impulso')
            .filter(nombre_interno__icontains='recuper')
            .first()
        )
        if not pl:
            pl = (
                Plantilla.objects.filter(activa=True, twilio_template_sid__startswith='HX')
                .filter(nombre_interno__icontains='recuper')
                .first()
            )
        if pl and pl.twilio_template_sid:
            print(f'[INFO] Content SID desde Plantilla BD: {pl.nombre_interno}')
            return pl.twilio_template_sid.strip()
    except Exception as exc:
        print(f'[WARN] No se pudo leer Plantilla BD: {exc}')
    return ''


def _default_variables() -> dict[str, str]:
    """Valores de prueba con acentos y emoji — validar render en WhatsApp."""
    return {
        '1': 'Julián (prueba QA)',
        '2': CURSO_NOMBRE_FILTRO,
        '3': 'Módulo 8 — Finanzas rurales',
    }


def _parse_vars(raw: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in raw:
        if '=' not in item:
            raise ValueError(f'--var inválido (use N=valor): {item!r}')
        key, val = item.split('=', 1)
        key = key.strip()
        if not key.isdigit():
            raise ValueError(f'Clave de variable debe ser número Twilio: {key!r}')
        out[key] = val
    return out


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Smoke: plantilla recuperación Impulso → solo teléfono QA',
    )
    parser.add_argument(
        '--telefono',
        default=TEL_QA_DEFAULT,
        help=f'Teléfono destino E.164 sin + (default QA: {TEL_QA_DEFAULT})',
    )
    parser.add_argument(
        '--content-sid',
        default='',
        help='Content SID HX… (si no, env TWILIO_TEMPLATE_RECUPERACION_IMPULSO)',
    )
    parser.add_argument(
        '--var',
        action='append',
        default=[],
        metavar='N=valor',
        help='Variable de plantilla Twilio (repetible). Ej: --var 1="Julián"',
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Solo muestra preview; no envía (default si no pasa --send)',
    )
    parser.add_argument(
        '--send',
        action='store_true',
        help='Envía el mensaje real a Twilio (requiere confirmación implícita: solo QA)',
    )
    args = parser.parse_args()

    tel = ''.join(c for c in str(args.telefono) if c.isdigit())
    if tel.startswith('57'):
        tel_e164 = f'+{tel}'
    else:
        tel_e164 = f'+57{tel}'

    # Seguridad: fuera de QA solo dry-run
    if not tel.endswith('3026480629'):
        print('[FAIL] Este script solo puede enviar al teléfono QA 3026480629.')
        print('       Para otro destino, modificar el script tras aprobación PM.')
        return 1

    content_sid = _resolver_content_sid(args.content_sid)
    if not content_sid:
        print(
            f'[FAIL] Sin Content SID. Definir {ENV_CONTENT_SID}=HX… en EB/.env '
            f'o pasar --content-sid HX…'
        )
        return 1

    variables = _default_variables()
    variables.update(_parse_vars(args.var))

    print('=' * 60)
    print('SMOKE recuperación Impulso Rural — plantilla Twilio')
    print('=' * 60)
    print(f'Destino QA : {tel_e164}')
    print(f'Content SID: {content_sid}')
    print(f'Variables  : {json.dumps(variables, ensure_ascii=False)}')

    preview = fetch_content_preview(content_sid)
    if preview.get('ok'):
        print('\n--- Preview plantilla (Twilio) ---')
        print(f"Nombre   : {preview.get('name')}")
        print(f"Idioma   : {preview.get('language')}")
        print(f"Aprobación: {preview.get('approval')}")
        body = preview.get('body') or ''
        print(f"Cuerpo   :\n{body}")
        if preview.get('buttons'):
            print(f"Botones  : {preview.get('buttons')}")
    else:
        print(f"\n[WARN] Preview no disponible: {preview.get('error')}")

    if args.dry_run or not args.send:
        print('\n[DRY-RUN] No se envió. Para enviar real: añadir --send')
        return 0

    print('\n--- Enviando a Twilio ---')
    resultado = enviar_plantilla_twilio(tel_e164, content_sid, variables=variables)
    print(json.dumps(resultado, ensure_ascii=False, indent=2))

    if resultado.get('success'):
        print('\n[OK] Revisa WhatsApp en el teléfono QA.')
        print('     Valida: acentos (á, é, í, ó, ú, ñ), emojis, nombre del módulo.')
        print(f"     Message SID: {resultado.get('mensaje_id')}")
        print('\nCuando apruebes visualmente, avisa para habilitar consulta + rollback masivo.')
        return 0

    print('\n[FAIL] Twilio rechazó el envío. Revisar variables vs plantilla aprobada.')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
