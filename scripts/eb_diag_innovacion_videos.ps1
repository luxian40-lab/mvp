# Diagnóstico prod: Innovación (41/52) + Twilio media. Solo lectura.
$ErrorActionPreference = 'Stop'
$py = @'
import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mvp_project.settings")
django.setup()
from datetime import timedelta
from urllib.request import Request, urlopen
from django.utils import timezone
from core.models import Curso, Modulo, PasoModulo, ProgresoEstudiante, WhatsappLog, ArchivoModulo

CUT = timezone.now() - timedelta(days=2)

def head(url):
    try:
        req = Request(url, method="HEAD", headers={"User-Agent": "eki-diag/1"})
        with urlopen(req, timeout=8) as r:
            return r.status, int(r.headers.get("Content-Length") or 0), (r.headers.get("Content-Type") or "")[:40]
    except Exception as e:
        return type(e).__name__, 0, str(e)[:80]

print("==== CURSOS 41 52 ====")
for cid in (41, 52):
    c = Curso.objects.filter(pk=cid).first()
    print("CURSO", cid, repr(c.nombre if c else None), "activo", getattr(c, "activo", None))
    for m in Modulo.objects.filter(curso_id=cid).order_by("numero", "id"):
        print(
            f"  M{m.numero} id={m.id} pub={m.publicado_wa} modo={m.modo_entrega} "
            f"contenido_len={len((m.contenido or '').strip())} video_url={bool(m.video_url)} "
            f"video_file={bool(m.video_archivo)} arch={ArchivoModulo.objects.filter(modulo=m, activo=True).count()} "
            f"tit={(m.titulo or '')[:40]!r}"
        )
        for p in PasoModulo.objects.filter(modulo=m).select_related("seccion").order_by("orden", "id"):
            url = (p.media_url or "").strip()
            print(
                f"    p{p.id} act={p.activo} ord={p.orden} sec={p.seccion_id} tipo={p.tipo} "
                f"txt={len((p.contenido or '').strip())} apto={p.media_wa_apto} url={url[:140]}"
            )
            if url.lower().split("?")[0].endswith((".mp4", ".m4v", ".mov")):
                print("      HEAD", head(url))

print("==== PROGRESOS 52 ====")
for p in ProgresoEstudiante.objects.filter(curso_id=52).select_related("estudiante", "modulo_actual"):
    e = p.estudiante
    print(
        "  est", e.id, "onb", e.estado_onboarding, "mod", getattr(p.modulo_actual, "numero", None),
        "paso", p.paso_actual_modulo, "done", p.completado, "last", p.fecha_ultimo_avance
    )
    logs = WhatsappLog.objects.filter(estudiante=e, fecha__gte=CUT).order_by("-fecha")[:12]
    for L in logs:
        print(
            "    LOG", L.fecha.isoformat(timespec="minutes"), L.tipo, L.estado,
            "err", (L.error_detalle or "")[:100],
            "msg", (L.mensaje or "").replace("\n", " ")[:90]
        )

print("==== SENT MEDIA MARKER 2d curso52 ====")
est_ids = list(ProgresoEstudiante.objects.filter(curso_id=52).values_list("estudiante_id", flat=True))
n_sent = WhatsappLog.objects.filter(estudiante_id__in=est_ids, tipo="SENT", fecha__gte=CUT).count()
n_media = WhatsappLog.objects.filter(estudiante_id__in=est_ids, tipo="SENT", fecha__gte=CUT, mensaje__icontains="[MEDIA:").count()
n_err = WhatsappLog.objects.filter(estudiante_id__in=est_ids, tipo="SENT", fecha__gte=CUT).exclude(error_detalle="").exclude(error_detalle__isnull=True).count()
print("sent", n_sent, "with_MEDIA", n_media, "with_err", n_err)

print("==== ANY 630 LAST 7d ====")
from django.db.models import Q
q = WhatsappLog.objects.filter(fecha__gte=timezone.now()-timedelta(days=7)).filter(
    Q(error_detalle__icontains="63019") | Q(error_detalle__icontains="63021") | Q(error_detalle__icontains="63005")
)
print("n", q.count())
for L in q.order_by("-fecha")[:15]:
    print(L.fecha, L.estado, (L.error_detalle or "")[:120], (L.mensaje or "")[:60].replace("\n"," "))
'@
$pyB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($py))
$bash = @"
export ELASTIC_BEANSTALK=true
GC=/opt/elasticbeanstalk/bin/get-config
for key in DB_NAME DB_USER DB_PASSWORD DB_HOST DB_PORT AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_STORAGE_BUCKET_NAME AWS_S3_REGION_NAME; do
  export "`$key=`"`$(`$GC environment -k `$key)`""
done
export USE_S3=True
export PYTHONPATH=/var/app/current
cd /var/app/current && source /var/app/venv/*/bin/activate
echo $pyB64 | base64 -d > /tmp/chk_innova2.py
python /tmp/chk_innova2.py
echo '==== GUNICORN TAIL MEDIA ===='
for f in /var/log/web.stdout.log /var/log/httpd/error_log /var/log/nginx/error.log /var/log/eb-docker/containers/eb-current-app/*.log; do
  if [ -f `$f ]; then echo FILE `$f; grep -E '63021|63019|omitiendo media|MEDIA' `$f | tail -n 20; fi
done
ls /var/log/eb-docker/containers/eb-current-app 2>/dev/null | head
"@ -replace "`r`n", "`n"
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($bash))
Write-Host "[INFO] diag innovacion videos prod" -ForegroundColor Cyan
& eb ssh eki-prod-final --command "echo $b64 | base64 -d | bash"
