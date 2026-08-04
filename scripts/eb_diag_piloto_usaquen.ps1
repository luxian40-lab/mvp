# Diagnóstico piloto empleabilidad (logs WA + misiones) en prod.
$ErrorActionPreference = 'Stop'
$py = @'
import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mvp_project.settings")
django.setup()
from datetime import timedelta
from django.utils import timezone
from core.models import Estudiante, WhatsappLog, MisionEmpleabilidad, AliadoEmpleabilidad

tel = "573026480629"
est = Estudiante.objects.filter(telefono=tel).first()
print("EST", getattr(est, "id", None), "cliente", getattr(est, "cliente_id", None))
print("estado_chat", getattr(est, "estado_chat", None), "onboarding", getattr(est, "estado_onboarding", None))
if est:
    ctx = est.contexto_temporal or {}
    for k in sorted(ctx):
        if any(x in k.lower() for x in ("emple", "aliado", "mision", "radar")):
            print("CTX", k, "=", ctx.get(k))

desde = timezone.now() - timedelta(hours=12)
qs = WhatsappLog.objects.filter(telefono__endswith="3026480629", fecha__gte=desde).order_by("-fecha")[:30]
print("LOGS_N", qs.count())
for L in qs:
    msg = (L.mensaje or "").replace("\n", " | ")[:200]
    print(str(L.fecha), L.tipo, msg)

print("--- MISIONES ---")
if est:
    for m in MisionEmpleabilidad.objects.filter(estudiante=est).select_related("aliado").order_by("-fecha_descubierta")[:10]:
        print(m.id, m.estado, "cod", m.codigo_validado, "dist", m.distancia_metros, "aliado", m.aliado_id, getattr(m.aliado, "nombre_empresa", None), m.fecha_descubierta)

a = AliadoEmpleabilidad.objects.filter(codigo_secreto="EKI-USQ-01").first()
print("--- ALIADO ---")
if a:
    print(a.id, a.nombre_empresa, a.latitud, a.longitud, "activo", a.vacantes_activas, "cliente", a.cliente_id)
'@
$pyB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($py))
$bash = @"
export ELASTIC_BEANSTALK=true
GC=/opt/elasticbeanstalk/bin/get-config
for key in DB_NAME DB_USER DB_PASSWORD DB_HOST DB_PORT; do
  export "`$key=`"`$(`$GC environment -k `$key)`""
done
export USE_S3=True
export PYTHONPATH=/var/app/current
cd /var/app/current && source /var/app/venv/*/bin/activate
echo $pyB64 | base64 -d > /tmp/chk_piloto.py
python /tmp/chk_piloto.py
"@ -replace "`r`n", "`n"
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($bash))
Write-Host "[INFO] Checking pilot logs on prod..." -ForegroundColor Cyan
& eb ssh eki-prod-final --command "echo $b64 | base64 -d | bash"
