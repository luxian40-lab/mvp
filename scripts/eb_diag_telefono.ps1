# Diagnóstico prod de un teléfono (solo lectura): estudiante, progreso, sesión línea Meta, logs WA y app.
param([Parameter(Mandatory = $true)][string]$Telefono, [int]$Horas = 24)
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
print("==== ESTUDIANTE ====")
for e in Estudiante.objects.filter(telefono__endswith=TEL[-10:]):
    print("est", e.id, e.telefono, "cliente", e.cliente_id, getattr(e.cliente, "plan_linea_meta", None),
          "onb", e.estado_onboarding, "ctx", str(e.contexto_temporal)[:200])
    for p in ProgresoEstudiante.objects.filter(estudiante=e).select_related("curso", "modulo_actual"):
        print("  prog", p.id, "curso", p.curso_id, repr(p.curso.nombre[:40]), "activo", p.curso.activo,
              "mod", getattr(p.modulo_actual, "numero", None), "paso", p.paso_actual_modulo,
              "done", p.completado, "inicio", p.fecha_inicio, "ultimo", p.fecha_ultimo_avance)
print("==== SESION LINEA ====")
for s in SandboxCanalSesion.objects.filter(telefono__endswith=TEL[-10:]):
    print("ses", s.telefono, "modo", s.modo, "plan", repr(s.plan), "habeas", s.habeas_aceptado,
          "preg", s.preguntas_mes, "racha", s.racha_actual, "aviso", repr(s.aviso_pendiente[:80]))
print("==== WHATSAPP LOG ====")
for L in WhatsappLog.objects.filter(telefono__endswith=TEL[-10:], fecha__gte=CUT).order_by("fecha"):
    print(timezone.localtime(L.fecha).strftime("%H:%M:%S"), L.tipo, L.estado, L.agente_usado,
          "id", (L.mensaje_id or "")[:28], "err", (L.error_detalle or "")[:120],
          "|", (L.mensaje or "").replace("\n", " ")[:140])
'@
$pyB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($py))
$bash = @"
export ELASTIC_BEANSTALK=true
GC=/opt/elasticbeanstalk/bin/get-config
for key in DB_NAME DB_USER DB_PASSWORD DB_HOST DB_PORT; do
  export "`$key=`"`$(`$GC environment -k `$key)`""
done
export PYTHONPATH=/var/app/current
cd /var/app/current && source /var/app/venv/*/bin/activate
echo $pyB64 | base64 -d > /tmp/diag_tel.py
python /tmp/diag_tel.py $Telefono $Horas 2>&1 | grep -v '^\[' 
echo '==== APP LOG (tel) ===='
for f in /var/log/web.stdout.log /var/log/celery*.log /var/log/eb-engine.log; do
  if [ -f `$f ]; then echo FILE `$f; grep -a -E '$($Telefono.Substring($Telefono.Length-10))|Traceback|Error' `$f | tail -n 60; fi
done
"@ -replace "`r`n", "`n"
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($bash))
& eb ssh eki-prod-final --command "echo $b64 | base64 -d | bash"
