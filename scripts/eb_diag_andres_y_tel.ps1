# Solo lectura: logs de un teléfono y búsqueda de Andrés (Twilio vs Meta).
param([string]$Telefono = '573026480629', [int]$Horas = 36)
$ErrorActionPreference = 'Stop'
$py = @'
import os, sys, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mvp_project.settings")
django.setup()
from datetime import timedelta
from django.utils import timezone
from core.models import Estudiante, ProgresoEstudiante, SandboxCanalSesion, WhatsappLog

TEL = sys.argv[1]
CUT = timezone.now() - timedelta(hours=int(sys.argv[2]))

def linea(msg):
    m = msg or ""
    if m.startswith("wamid") or "HBgM" in m:
        return "meta"
    if m.startswith("SM") or m.startswith("MM"):
        return "twilio"
    return "?"

print("==== TEL", TEL, "====")
for e in Estudiante.objects.filter(telefono__endswith=TEL[-10:]):
    print("est", e.id, e.nombre, e.telefono, "onb", e.estado_onboarding)
    for p in ProgresoEstudiante.objects.filter(estudiante=e, completado=False).select_related("curso"):
        print("  abierto", p.curso_id, p.curso.nombre[:40], "paso", p.paso_actual_modulo, "mod", getattr(p.modulo_actual, "numero", None))
for L in WhatsappLog.objects.filter(telefono__endswith=TEL[-10:], fecha__gte=CUT).order_by("fecha"):
    print(timezone.localtime(L.fecha).strftime("%m-%d %H:%M:%S"), linea(L.mensaje_id), L.tipo, L.estado,
          (L.agente_usado or "-"), "|", (L.mensaje or "").replace("\n", " ")[:110])

print("==== ANDRES ====")
qs = Estudiante.objects.filter(nombre__icontains="andres") | Estudiante.objects.filter(nombre__icontains="andrés")
for e in qs.order_by("id")[:30]:
    ult = WhatsappLog.objects.filter(telefono=e.telefono).order_by("-fecha").first()
    canal = linea(ult.mensaje_id) if ult else "sin_log"
    cuando = timezone.localtime(ult.fecha).strftime("%m-%d %H:%M") if ult else "-"
    print("est", e.id, repr(e.nombre), e.telefono, "cliente", e.cliente_id, "ultimo", cuando, canal, (ult.agente_usado if ult else ""))
'@
$pyB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($py))
$bash = @"
GC=/opt/elasticbeanstalk/bin/get-config
for key in DB_NAME DB_USER DB_PASSWORD DB_HOST DB_PORT; do export "`$key=`"`$(`$GC environment -k `$key)`""; done
export ELASTIC_BEANSTALK=true PYTHONPATH=/var/app/current
cd /var/app/current && source /var/app/venv/*/bin/activate
echo $pyB64 | base64 -d > /tmp/diag_andres.py
python /tmp/diag_andres.py $Telefono $Horas 2>&1 | grep -E '^(====|est |  abierto|[0-9][0-9]-)'
"@ -replace "`r`n", "`n"
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($bash))
& eb ssh eki-prod-final --command "echo $b64 | base64 -d | bash"
