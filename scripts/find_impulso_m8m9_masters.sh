#!/bin/bash
set -eu
export ELASTIC_BEANSTALK=true
GC=/opt/elasticbeanstalk/bin/get-config
eval "$(sudo "$GC" environment | python3 -c 'import json,shlex,sys; [print(f"export {k}={shlex.quote(str(v))}") for k,v in json.load(sys.stdin).items()]')"
cd /var/app/current
source /var/app/venv/*/bin/activate
export PYTHONPATH=/var/app/current
export DJANGO_SETTINGS_MODULE=mvp_project.settings_production
python3 <<'PY'
import django
django.setup()
from core.models import PasoModulo, EventoIA
import boto3
from django.conf import settings

for pid in (243, 245, 248):
    p = PasoModulo.objects.get(id=pid)
    print("PASO", pid, "apto", p.media_wa_apto)
    print(" URL", p.media_url)

# Buscar masters en S3 (sin wa_safe) para modulo 154/155
s3 = boto3.client("s3", region_name="us-east-2")
bucket = getattr(settings, "AWS_STORAGE_BUCKET_NAME", "eki-produccion")
for prefix in (
    "modulos/pasos/2026/08/",
    "modulos/pasos/wa_safe/2026/08/",
):
    print("\n=== LIST", prefix, "===")
    token = None
    while True:
        kw = {"Bucket": bucket, "Prefix": prefix, "MaxKeys": 200}
        if token:
            kw["ContinuationToken"] = token
        resp = s3.list_objects_v2(**kw)
        for obj in resp.get("Contents") or []:
            key = obj["Key"]
            if "modulo_154" in key or "modulo_155" in key or "0233" in key or "_026_" in key or "_29_" in key:
                print(obj["LastModified"], obj["Size"], key)
        token = resp.get("NextContinuationToken")
        if not token:
            break

# EventoIA / logs mentions
for ev in EventoIA.objects.filter(payload__icontains="243").order_by("-id")[:5]:
    print("EV", ev.id, ev.tipo, str(ev.payload)[:200])
PY
