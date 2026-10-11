# Solo lectura: impacto REDDI curso 52 post-activación videos.
$ErrorActionPreference = 'Stop'
$py = @'
import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mvp_project.settings")
django.setup()
from datetime import timedelta
from django.db.models import Q
from django.utils import timezone
from core.models import (
    Curso, Estudiante, Modulo, ModuloCompletado, PasoModulo,
    ProgresoEstudiante, WhatsappLog,
)
from core.module_steps import pasos_activos_qs

CID = 52
CUT2 = timezone.now() - timedelta(days=2)
CUT7 = timezone.now() - timedelta(days=7)
CUT_REPAIR = timezone.now() - timedelta(hours=30)  # ventana ~repair

c = Curso.objects.filter(pk=CID).select_related("cliente").first()
print("==== CURSO ====")
print(
    f"id={c.id} nombre={c.nombre!r} cliente={getattr(c.cliente,'nombre',None)!r} "
    f"activo={c.activo}"
)

print("\n==== VIDEOS MP4 POR MODULO ====")
for m in Modulo.objects.filter(curso_id=CID).order_by("numero", "id"):
    vids = []
    for p in PasoModulo.objects.filter(modulo=m).select_related("seccion").order_by("orden", "id"):
        url = (p.media_url or "").strip()
        if not url.lower().split("?")[0].endswith((".mp4", ".m4v", ".mov")):
            continue
        vids.append(p)
    act = sum(1 for p in vids if p.activo)
    inact = sum(1 for p in vids if not p.activo)
    aptos = sum(1 for p in vids if p.media_wa_apto is True)
    n_activos_qs = pasos_activos_qs(m).count()
    n_media_act = sum(
        1 for p in pasos_activos_qs(m)
        if (p.media_url or "").lower().split("?")[0].endswith((".mp4", ".m4v", ".mov"))
    )
    print(
        f"  M{m.numero} id={m.id} pub={m.publicado_wa} "
        f"videos={len(vids)} act={act} inact={inact} apto={aptos} "
        f"pasos_activos_qs={n_activos_qs} videos_en_ruta={n_media_act} "
        f"tit={(m.titulo or '')[:40]!r}"
    )
    for p in vids:
        print(
            f"    p{p.id} act={p.activo} apto={p.media_wa_apto} ord={p.orden} "
            f"sec_act={getattr(p.seccion,'activa',None)} {(p.titulo or '')[:45]!r}"
        )

print("\n==== ESTUDIANTES / PROGRESO ====")
progs = list(
    ProgresoEstudiante.objects.filter(curso_id=CID)
    .select_related("estudiante", "modulo_actual")
    .order_by("estudiante_id")
)
print(f"inscritos={len(progs)}")
for prog in progs:
    e = prog.estudiante
    comps = list(
        ModuloCompletado.objects.filter(progreso=prog)
        .select_related("modulo")
        .order_by("modulo__numero")
    )
    comps_s = ",".join(f"M{mc.modulo.numero}" for mc in comps) or "-"
    print(
        f"  est_id={e.id} nombre={(e.nombre or '')[:40]!r} tel=...{(e.telefono or '')[-4:]} "
        f"onb={e.estado_onboarding} activo={e.activo}"
    )
    print(
        f"    prog_id={prog.id} mod={getattr(prog.modulo_actual,'numero',None)} "
        f"paso_idx={prog.paso_actual_modulo} done={prog.completado} "
        f"last={prog.fecha_ultimo_avance} comps=[{comps_s}]"
    )
    # ¿ruta actual tiene video activo?
    mod = prog.modulo_actual
    if mod:
        bits = []
        for p in list(pasos_activos_qs(mod)[:8]):
            has_m = bool((p.media_url or "").strip())
            bits.append(f"#{p.orden} media={has_m}")
        print("    siguientes_activos=", bits)

print("\n==== WHATSAPP LOGS (por estudiante, 7d) ====")
for prog in progs:
    e = prog.estudiante
    tel = (e.telefono or "").strip()
    q = WhatsappLog.objects.filter(fecha__gte=CUT7)
    if e.id:
        q = q.filter(Q(estudiante_id=e.id) | Q(telefono__endswith=tel[-10:] if len(tel) >= 10 else tel))
    else:
        q = q.filter(telefono__endswith=tel[-10:] if len(tel) >= 10 else tel)
    logs = list(q.order_by("-fecha")[:25])
    n_sent = sum(1 for L in logs if (L.tipo or "").upper() == "SENT")
    n_media = sum(1 for L in logs if "[MEDIA:" in (L.mensaje or ""))
    n_630 = sum(
        1 for L in logs
        if any(x in (L.error_detalle or "") for x in ("63019", "63021", "63005"))
    )
    n_fail = sum(
        1 for L in logs
        if (L.estado or "").lower() in ("failed", "undelivered")
        or (L.error_detalle or "").strip()
    )
    print(
        f"  est={e.id} logs7d={len(logs)} sent_sample={n_sent} media_marker={n_media} "
        f"err630={n_630} failish={n_fail}"
    )
    for L in logs[:12]:
        msg = (L.mensaje or "").replace("\n", " ")[:100]
        err = (L.error_detalle or "")[:80]
        print(
            f"    {L.fecha.isoformat(timespec='minutes')} tipo={L.tipo} est={L.estado} "
            f"err={err!r} msg={msg!r}"
        )

print("\n==== SENT MEDIA CURSO52 (2d, por telefono/estudiante) ====")
est_ids = [p.estudiante_id for p in progs]
tels = [(p.estudiante.telefono or "")[-10:] for p in progs if p.estudiante.telefono]
q_sent = WhatsappLog.objects.filter(tipo="SENT", fecha__gte=CUT2)
q_est = Q(estudiante_id__in=est_ids)
for t in tels:
    if t:
        q_est |= Q(telefono__endswith=t)
q_sent = q_sent.filter(q_est)
print("sent2d", q_sent.count())
print("with_MEDIA", q_sent.filter(mensaje__icontains="[MEDIA:").count())
print(
    "with_630",
    q_sent.filter(
        Q(error_detalle__icontains="63019")
        | Q(error_detalle__icontains="63021")
        | Q(error_detalle__icontains="63005")
    ).count(),
)
for L in q_sent.filter(mensaje__icontains="[MEDIA:").order_by("-fecha")[:15]:
    print(
        f"  MEDIA {L.fecha.isoformat(timespec='minutes')} est={L.estudiante_id} "
        f"tel=...{(L.telefono or '')[-4:]} estado={L.estado} "
        f"msg={(L.mensaje or '')[:90].replace(chr(10),' ')}"
    )

print("\n==== VIDEOS LISTOS AUN INACTIVOS (curso52) ====")
n_inact = 0
for p in PasoModulo.objects.filter(
    modulo__curso_id=CID, activo=False, media_wa_apto=True
).exclude(media_url=""):
    url = (p.media_url or "").lower().split("?")[0]
    if url.endswith((".mp4", ".m4v", ".mov")):
        n_inact += 1
        print(f"  p{p.id} M{p.modulo.numero} {(p.titulo or '')[:40]!r}")
print("total_inact_listos", n_inact)

print("\n==== DONE ====")
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
echo $pyB64 | base64 -d > /tmp/qa_reddi52.py
python /tmp/qa_reddi52.py
"@ -replace "`r`n", "`n"
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($bash))
Write-Host "[INFO] QA REDDI curso 52 impacto (solo lectura)" -ForegroundColor Cyan
& eb ssh eki-prod-final --command "echo $b64 | base64 -d | bash"
