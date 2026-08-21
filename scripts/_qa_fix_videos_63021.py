"""
Repara videos que fallaron con Twilio 63021: descarga → H.264+AAC → S3 whatsapp_ready.

Uso (con .env Twilio + AWS):
  python scripts/_qa_fix_videos_63021.py
  python scripts/_qa_fix_videos_63021.py --reenviar

Por defecto procesa los SIDs de Impulso (Sarita + segundo) del 2026-08-21.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / '.env')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')

import django

django.setup()

from twilio.rest import Client

from core.twilio_media import (
    _public_s3_url,
    _subir_bytes_s3,
    optimizar_mp4_bytes_whatsapp,
    preparar_url_media_whatsapp,
    probe_mp4_codecs,
)

DEFAULT_SIDS = [
    'MM2aa558d22efa705557e8faddc3f49605',  # Bienvenida · 3197239578
    'MMb7f492d55b67c82239b3fe19b0babe8e',  # Diagnóstico · 3197239578
    'MMd4e7b4ed95e02072a624816dabbe897f',  # Módulo 1 · 3223032955
]


def _download_twilio_media(client: Client, message_sid: str) -> tuple[bytes, str]:
    medias = list(client.messages(message_sid).media.list(limit=3))
    if not medias:
        raise RuntimeError(f'Sin media en {message_sid}')
    mu = medias[0]
    uri = (mu.uri or '').replace('.json', '')
    # Twilio media binary
    import requests

    url = f'https://api.twilio.com{uri}'
    r = requests.get(
        url,
        auth=(os.environ['TWILIO_ACCOUNT_SID'], os.environ['TWILIO_AUTH_TOKEN']),
        timeout=120,
    )
    r.raise_for_status()
    return r.content, (mu.content_type or 'video/mp4')


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--sid', action='append', dest='sids', help='MessageSid MM…')
    parser.add_argument('--reenviar', action='store_true', help='Reenviar a To del mensaje')
    args = parser.parse_args()
    sids = args.sids or DEFAULT_SIDS

    client = Client(os.environ['TWILIO_ACCOUNT_SID'], os.environ['TWILIO_AUTH_TOKEN'])
    for sid in sids:
        print('====', sid)
        msg = client.messages(sid).fetch()
        to = (msg.to or '').replace('whatsapp:', '')
        body = ((msg.body or '')[:60]).encode('ascii', 'replace').decode()
        print('  to=', to, 'status=', msg.status, 'err=', msg.error_code, body)
        try:
            raw, ctype = _download_twilio_media(client, sid)
        except Exception as exc:
            print('  download FAIL', exc)
            continue
        print('  downloaded', len(raw), 'bytes', ctype)
        codecs_before = probe_mp4_codecs(raw)
        print('  codecs before', codecs_before)
        fixed = optimizar_mp4_bytes_whatsapp(raw) or raw
        codecs_after = probe_mp4_codecs(fixed)
        print('  codecs after', codecs_after, 'bytes', len(fixed))
        digest = hashlib.sha1(sid.encode()).hexdigest()[:16]
        key = f'media/whatsapp_ready/repair_{digest}_wa_h264.mp4'
        url = _subir_bytes_s3(key, fixed, 'video/mp4')
        if not url:
            url = _public_s3_url(key)
            print('  upload FAIL; public guess', url)
            continue
        print('  uploaded', url)
        ready = preparar_url_media_whatsapp(url)
        print('  preparar_url', ready)
        if args.reenviar and to:
            from core.utils import enviar_whatsapp_twilio

            res = enviar_whatsapp_twilio(
                telefono=to,
                texto='📡 Reenviamos el video del módulo (versión corregida para WhatsApp).',
                media_url=ready or url,
            )
            print('  reenviar', res.get('success'), res.get('mensaje_id') or res.get('response'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
