"""Inventario Twilio outbound campaña (SIN envíos). Solo lectura Message list."""
from __future__ import annotations

import os
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mvp_project.settings")

import django

django.setup()

from django.conf import settings

sid = (getattr(settings, "TWILIO_ACCOUNT_SID", None) or "").strip()
token = (getattr(settings, "TWILIO_AUTH_TOKEN", None) or "").strip()
if not sid or not token:
    print("TWILIO_CREDS=missing")
    sys.exit(2)

FROM_WA = "whatsapp:+573202948806"
KEYWORDS = (
    "capital humano",
    "cenipa",
    "eki aprende",
    "aprende.eki.technology",
)
HOURS = int(sys.argv[1]) if len(sys.argv) > 1 else 48
PAGE_LIMIT = int(sys.argv[2]) if len(sys.argv) > 2 else 1000

from twilio.rest import Client

client = Client(sid, token)
since = datetime.now(timezone.utc) - timedelta(hours=HOURS)
print(f"from={FROM_WA}")
print(f"since_utc={since.isoformat()}")
print(f"hours={HOURS} page_limit={PAGE_LIMIT}")

# Twilio lista por From + date_sent_after; filtramos keywords en body/client.
raw = client.messages.list(
    from_=FROM_WA,
    date_sent_after=since,
    limit=PAGE_LIMIT,
)
print(f"raw_from_line={len(raw)}")


def matches_campaign(m) -> bool:
    body = (m.body or "").lower()
    if any(k in body for k in KEYWORDS):
        return True
    # Plantillas Content a veces sin body legible; incluir undelivered 63049 y
    # outbound recientes de la misma línea si error 63049.
    if m.error_code == 63049:
        return True
    return False


msgs = [m for m in raw if matches_campaign(m)]
# Si el filtro deja muy poco, reportar también totales de la línea (contexto).
print(f"matched_campaign_or_63049={len(msgs)}")

by_status = Counter()
by_error = Counter()
ok_read = None
fail_63049 = None
examples = []

for m in msgs:
    st = (m.status or "unknown").lower()
    by_status[st] += 1
    if m.error_code:
        by_error[str(m.error_code)] += 1
    else:
        by_error["none"] += 1

    body = (m.body or "")[:80].replace("\n", " ")
    examples.append(
        f"{m.date_sent} | {st} | sid={m.sid} | err={m.error_code} | body={body!r}"
    )
    if ok_read is None and st == "read":
        ok_read = m.sid
    if fail_63049 is None and m.error_code == 63049:
        fail_63049 = m.sid

# Fallback ejemplos desde raw line si filtro vacío
if ok_read is None:
    for m in raw:
        if (m.status or "").lower() == "read":
            ok_read = m.sid
            break
if fail_63049 is None:
    for m in raw:
        if m.error_code == 63049:
            fail_63049 = m.sid
            break

# Agregados línea completa (contexto)
line_status = Counter((m.status or "unknown").lower() for m in raw)
line_error = Counter(str(m.error_code) if m.error_code else "none" for m in raw)

print("--- MATCHED ---")
print(f"total_msgs={len(msgs)}")
print("por_status=", dict(by_status))
print("por_error=", dict(by_error))
print(f"ejemplo_ok_read={ok_read}")
print(f"ejemplo_fail_63049={fail_63049}")

useful = by_status.get("read", 0) + by_status.get("delivered", 0)
n63049 = by_error.get("63049", 0)
total = len(msgs) or 1
print(f"pct_util={100.0 * useful / total:.1f}")
print(f"pct_63049={100.0 * n63049 / total:.1f}")

print("--- LINE_ALL (contexto) ---")
print(f"line_total={len(raw)}")
print("line_por_status=", dict(line_status))
print("line_por_error=", dict(line_error))

print("--- SAMPLE matched (max 25) ---")
for line in examples[:25]:
    print(line)
