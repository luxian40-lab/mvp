"""Inventario Twilio por ContentSid (solo lectura, sin envíos)."""
from __future__ import annotations

import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mvp_project.settings")

import django

django.setup()

from django.conf import settings
from twilio.rest import Client

CONTENT_SID = (sys.argv[1] if len(sys.argv) > 1 else "").strip()
HOURS = int(sys.argv[2]) if len(sys.argv) > 2 else 12
PAGE_LIMIT = int(sys.argv[3]) if len(sys.argv) > 3 else 2000
FROM_WA = (sys.argv[4] if len(sys.argv) > 4 else "whatsapp:+573202948806").strip()

if not CONTENT_SID.startswith("HX"):
    print("usage: python scripts/_qa_twilio_content_sid.py HX... [hours] [limit] [from_wa]")
    sys.exit(2)

sid = (getattr(settings, "TWILIO_ACCOUNT_SID", None) or "").strip()
token = (getattr(settings, "TWILIO_AUTH_TOKEN", None) or "").strip()
if not sid or not token:
    print("TWILIO_CREDS=missing")
    sys.exit(2)

client = Client(sid, token)
since = datetime.now(timezone.utc) - timedelta(hours=HOURS)
print(f"content_sid={CONTENT_SID}")
print(f"from={FROM_WA}")
print(f"since_utc={since.isoformat()} hours={HOURS} limit={PAGE_LIMIT}")

raw = client.messages.list(from_=FROM_WA, date_sent_after=since, limit=PAGE_LIMIT)
print(f"raw_from_line={len(raw)}")

matched = []
for m in raw:
    cs = (getattr(m, "content_sid", None) or "") or ""
    # Algunas respuestas solo traen content_sid en fetch individual
    if cs == CONTENT_SID:
        matched.append(m)
        continue
    # Fallback: body vacío + messaging reciente — refetch si parece Content
    if not cs and (m.body is None or m.body == "") and m.direction == "outbound-api":
        try:
            full = client.messages(m.sid).fetch()
            fcs = getattr(full, "content_sid", None) or ""
            if fcs == CONTENT_SID:
                matched.append(full)
        except Exception:
            pass

# Si pocos matches, barrido refetch de undelivered/failed recientes (caro pero acotado)
if len(matched) < 3:
    extra = []
    candidates = [
        m
        for m in raw
        if (m.status or "").lower() in ("undelivered", "failed", "delivered", "read", "sent", "queued")
    ][:400]
    for m in candidates:
        if any(x.sid == m.sid for x in matched):
            continue
        try:
            full = client.messages(m.sid).fetch()
        except Exception:
            continue
        if (getattr(full, "content_sid", None) or "") == CONTENT_SID:
            extra.append(full)
    matched.extend(extra)

print(f"matched_content_sid={len(matched)}")

by_status = Counter()
by_error = Counter()
ok_phones = []
err_phones = []

for m in matched:
    st = (m.status or "unknown").lower()
    by_status[st] += 1
    err = m.error_code
    if err:
        by_error[str(err)] += 1
    else:
        by_error["none"] += 1
    to = (m.to or "").replace("whatsapp:", "")
    body = ((m.body or "")[:70]).replace("\n", " ")
    row = f"{m.date_sent} | {st} | to={to} | sid={m.sid} | err={err} | body={body!r}"
    if st in ("delivered", "read", "sent", "receiving", "accepted", "queued", "sending"):
        if st in ("delivered", "read"):
            ok_phones.append(row)
        else:
            ok_phones.append(row + " (en tránsito)")
    else:
        err_phones.append(row)

print("--- por_status ---")
for k, v in by_status.most_common():
    print(f"  {k}: {v}")
print("--- por_error ---")
for k, v in by_error.most_common():
    print(f"  {k}: {v}")

util = by_status.get("read", 0) + by_status.get("delivered", 0)
fail = by_status.get("undelivered", 0) + by_status.get("failed", 0)
total = len(matched) or 1
print(f"util_read_delivered={util} ({100*util/total:.1f}%)")
print(f"fail_undelivered_failed={fail} ({100*fail/total:.1f}%)")

print("--- OK / en tránsito (hasta 40) ---")
for r in ok_phones[:40]:
    print(r)
if len(ok_phones) > 40:
    print(f"... +{len(ok_phones)-40} más")

print("--- ERRORES (todos) ---")
for r in err_phones:
    print(r)

# Teléfonos únicos
ok_set = set()
err_set = set()
for m in matched:
    to = (m.to or "").replace("whatsapp:", "")
    st = (m.status or "").lower()
    if st in ("delivered", "read"):
        ok_set.add(to)
    elif st in ("undelivered", "failed"):
        err_set.add(to)
print(f"unique_ok_phones={len(ok_set)}")
print(f"unique_err_phones={len(err_set)}")
both = ok_set & err_set
if both:
    print(f"phones_with_both_ok_and_err={len(both)}")
