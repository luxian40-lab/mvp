"""Inventario Twilio por plantilla Content (match por body; ContentSid no viene en Message)."""
from __future__ import annotations

import os
import re
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

# Evitar UnicodeEncodeError en Windows cp1252
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mvp_project.settings")
import logging

logging.disable(logging.WARNING)

import django

django.setup()

from django.conf import settings
from twilio.rest import Client

HX = (sys.argv[1] if len(sys.argv) > 1 else "HX7ce56abf1cbf5b3671b1de7a3144366f").strip()
HOURS = int(sys.argv[2]) if len(sys.argv) > 2 else 4
FROM_WA = "whatsapp:+573202948806"

client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

content = client.content.v1.contents(HX).fetch()
friendly = getattr(content, "friendly_name", "") or ""
types = getattr(content, "types", None) or {}
body_tpl = ""
if isinstance(types, dict):
    text = types.get("twilio/text") or types.get("twilio/quick-reply") or {}
    if isinstance(text, dict):
        body_tpl = text.get("body") or ""
print(f"HX={HX}")
print(f"friendly_name={friendly}")
print(f"body_tpl_snip={(body_tpl[:180] or '').replace(chr(10), ' ')}")

# Anclas: frases fijas del template (sin variables {{}})
anchors = []
for part in re.split(r"\{\{[^}]+\}\}", body_tpl):
    part = re.sub(r"\s+", " ", part).strip()
    if len(part) >= 12:
        anchors.append(part.lower())
# fallbacks conocidos 10x / cenipa
for a in (
    "programa capital humano 10x",
    "capital humano 10x",
    "cenipa",
    "10x2cenipalma",
):
    if a not in anchors:
        anchors.append(a)

print(f"anchors={anchors[:6]}")

since = datetime.now(timezone.utc) - timedelta(hours=HOURS)
raw = client.messages.list(from_=FROM_WA, date_sent_after=since, limit=2000)
print(f"raw_from_line={len(raw)} since={since.isoformat()}")


def matches(m) -> bool:
    body = (m.body or "").lower()
    if not body:
        return False
    return any(a in body for a in anchors if a)


matched = [m for m in raw if matches(m)]
print(f"matched_by_body={len(matched)}")

by_status = Counter()
by_error = Counter()
ok_rows = []
err_rows = []

for m in sorted(matched, key=lambda x: x.date_sent or since, reverse=True):
    st = (m.status or "unknown").lower()
    by_status[st] += 1
    if m.error_code:
        by_error[str(m.error_code)] += 1
        err_msg = (m.error_message or "")[:80]
    else:
        by_error["none"] += 1
        err_msg = ""
    to = (m.to or "").replace("whatsapp:", "")
    body = (m.body or "")[:70].replace("\n", " ")
    row = f"{m.date_sent} | {st} | to={to} | sid={m.sid} | err={m.error_code} {err_msg} | {body}"
    if st in ("undelivered", "failed"):
        err_rows.append(row)
    else:
        ok_rows.append(row)

print("--- por_status ---")
for k, v in by_status.most_common():
    print(f"  {k}: {v}")
print("--- por_error ---")
for k, v in by_error.most_common():
    print(f"  {k}: {v}")

util = by_status.get("read", 0) + by_status.get("delivered", 0)
fail = by_status.get("undelivered", 0) + by_status.get("failed", 0)
total = len(matched) or 1
print(f"util_read_delivered={util}/{len(matched)} ({100 * util / total:.1f}%)")
print(f"fail={fail}/{len(matched)} ({100 * fail / total:.1f}%)")

print("--- LLEGARON (read/delivered/sent) ---")
for r in ok_rows:
    print(r)
print("--- ERRORES ---")
for r in err_rows:
    print(r)

ok_phones = {
    (m.to or "").replace("whatsapp:", "")
    for m in matched
    if (m.status or "").lower() in ("read", "delivered")
}
err_phones = {
    (m.to or "").replace("whatsapp:", "")
    for m in matched
    if (m.status or "").lower() in ("undelivered", "failed")
}
print(f"unique_ok={len(ok_phones)} unique_err={len(err_phones)}")
print("OK_PHONES", ", ".join(sorted(ok_phones)))
print("ERR_PHONES", ", ".join(sorted(err_phones)))
