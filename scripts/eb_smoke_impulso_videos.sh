#!/bin/bash
# Smoke WA: 3 videos Impulso (M1, M8, M9) → teléfono QA autorizado.
set -eu
export ELASTIC_BEANSTALK=true
GC=/opt/elasticbeanstalk/bin/get-config
for key in DB_NAME DB_USER DB_PASSWORD DB_HOST DB_PORT TWILIO_ACCOUNT_SID TWILIO_AUTH_TOKEN TWILIO_WHATSAPP_NUMBER TWILIO_PHONE_NUMBER TWILIO_WHATSAPP_FROM AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_STORAGE_BUCKET_NAME AWS_S3_REGION_NAME; do
  export "$key=$($GC environment -k $key 2>/dev/null)"
done
export USE_S3=True
export DJANGO_SETTINGS_MODULE=mvp_project.settings_production
cd /var/app/current
source /var/app/venv/*/bin/activate
python3 <<'PY'
import time

import django

django.setup()

from core.models import Estudiante, PasoModulo, WhatsappLog
from core.utils import enviar_whatsapp_twilio

TEL = "573026480629"
SAMPLES = [
    (140, "M1 bienvenida"),
    (249, "M8 finanzas"),
    (245, "M9 competencia"),
    (252, "M10 video 1"),
    (255, "M10 video 2"),
    (258, "M11 video"),
]

est = Estudiante.objects.filter(telefono__endswith="3026480629").order_by("-id").first()
print("estudiante:", est.id if est else None, getattr(est, "nombre", None))

results = []
for paso_id, label in SAMPLES:
    paso = PasoModulo.objects.filter(pk=paso_id, modulo__curso_id=22, activo=True).first()
    if not paso or not (paso.media_url or "").strip():
        print(f"SKIP {label}: paso {paso_id}")
        results.append((label, "SKIP"))
        continue
    txt = f"[QA eki] Smoke Impulso {label}. Si ves el video, responde OK."
    print(f"ENVIANDO {label} paso={paso_id}")
    r = enviar_whatsapp_twilio(TEL, txt, media_url=paso.media_url.strip())
    ok = r.get("success")
    print(f"  success={ok} sid={r.get('mensaje_id')}")
    results.append((label, "OK" if ok else "FAIL"))
    time.sleep(2)

print("\n=== RESUMEN ===")
for label, st in results:
    print(label, st)

print("\nUltimos logs:")
for lg in WhatsappLog.objects.filter(telefono__endswith="3026480629").order_by("-fecha")[:6]:
    err = (lg.error_detalle or "")[:80]
    print(lg.fecha.strftime("%H:%M:%S"), lg.respuesta_api or lg.estado, err)
PY
