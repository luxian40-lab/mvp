# Provision margen piloto en EB (cliente 21 + curso 22 por defecto).
param(
    [int]$ClienteId = 21,
    [int]$CursoId = 22,
    [string]$Environment = "eki-prod-final",
    [switch]$CrearPortal
)

. "$PSScriptRoot\_eb_env_prod_bash.ps1"

$crearPortalPy = if ($CrearPortal) { "True" } else { "False" }

$bash = @"
$(Get-EbEnvProdBash)
export DJANGO_SETTINGS_MODULE=mvp_project.settings_production
export PYTHONPATH=/var/app/current
cd /var/app/current && source /var/app/venv/*/bin/activate
python3 <<'PY'
import django
django.setup()
from core.models import Cliente, Curso
from calculadora_margen.links import obtener_o_crear_enlace, urls_margen_cliente
from calculadora_margen.analytics import resumen_uso_cliente
from portal.models import PortalUsuario

cid, curid = $ClienteId, $CursoId
c = Cliente.objects.filter(pk=cid).first()
cur = Curso.objects.filter(pk=curid).first()
if not c:
    print("[FAIL] cliente", cid)
    raise SystemExit(1)
e = obtener_o_crear_enlace(c)
u = urls_margen_cliente(c, curso_id=curid)
s = resumen_uso_cliente(c.pk, dias=30)
print("Cliente:", c.nombre, "| id=", c.pk)
print("Curso:", cur.nombre if cur else "?", "| id=", curid)
print("URL org:", u["url_org"])
print("URL token:", u["url_token"])
print("Portal KPIs:", "https://eki.technology/portal/margen/")
for pu in PortalUsuario.objects.filter(organizacion_id=cid)[:5]:
    print("Portal user:", pu.user.email or pu.user.username, "|", pu.rol)
print("Stats 30d: aperturas=", s["aperturas"], "calculos=", s["calculos"], "sesiones=", s["sesiones"])
print("Slug:", e.slug)
if ${crearPortalPy}:
    from django.contrib.auth.models import User
    uname = f"margen_{cid}"
    pwd = "MargenPiloto2026!"
    email = c.email or f"{uname}@eki.local"
    user, created = User.objects.get_or_create(username=uname, defaults={"email": email})
    user.email = email
    user.is_active = True
    user.set_password(pwd)
    user.save()
    PortalUsuario.objects.update_or_create(
        user=user,
        defaults={"organizacion": c, "rol": "admin", "debe_cambiar_credenciales": False, "password_temporal": pwd},
    )
    print("Portal login:", "https://eki.technology/portal/login/")
    print("Portal user:", uname, "| pass:", pwd, "| nuevo=", created)
PY
"@ -replace "`r`n", "`n"

$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($bash))
& eb ssh $Environment --command "echo $b64 | base64 -d | bash"
