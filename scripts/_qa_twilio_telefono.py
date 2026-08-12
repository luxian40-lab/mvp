"""Consulta Twilio Message resource por To (sin imprimir credenciales)."""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')

import django

django.setup()

from django.conf import settings

sid = (getattr(settings, 'TWILIO_ACCOUNT_SID', None) or '').strip()
token = (getattr(settings, 'TWILIO_AUTH_TOKEN', None) or '').strip()
if not sid or not token:
    print('TWILIO_CREDS=missing')
    sys.exit(2)

needle = (sys.argv[1] if len(sys.argv) > 1 else '3106077609').replace(' ', '').replace('+', '')
if len(needle) == 10:
    needle = f'57{needle}'
to_wa = f'whatsapp:+{needle}'

from twilio.rest import Client

client = Client(sid, token)
since = datetime.now(timezone.utc) - timedelta(days=2)
print('query_to=', to_wa)
print('since_utc=', since.isoformat())

msgs = client.messages.list(to=to_wa, date_sent_after=since, limit=30)
print('count=', len(msgs))
for m in msgs:
    err = f'{m.error_code}:{m.error_message}' if m.error_code else ''
    body = (m.body or '')[:100].replace('\n', ' ')
    print(
        f'{m.date_sent} | {m.status} | sid={m.sid} | from={m.from_} | '
        f'direction={m.direction} | err={err!r} | body={body!r}'
    )

# También por From variants no; intentar sin whatsapp: prefix por si guardaron E.164
msgs2 = client.messages.list(to=f'+{needle}', date_sent_after=since, limit=10)
print('count_e164=', len(msgs2))
for m in msgs2:
    err = f'{m.error_code}:{m.error_message}' if m.error_code else ''
    print(f'{m.date_sent} | {m.status} | sid={m.sid} | from={m.from_} | err={err!r}')
