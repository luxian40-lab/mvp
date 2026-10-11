"""Detalle adversarial Impulso 22 + Agrosavia 35. Solo lectura."""
from datetime import timedelta

from django.utils import timezone

from core.models import (
    Estudiante,
    Modulo,
    PasoModulo,
    ProgresoEstudiante,
    WhatsappLog,
)

CUT = timezone.now() - timedelta(days=14)


def pasos_mod(curso_id, numero):
    m = Modulo.objects.filter(curso_id=curso_id, numero=numero).first()
    print(f'\n-- pasos M{numero} curso={curso_id} id={getattr(m, "id", None)} --')
    if not m:
        return
    for p in PasoModulo.objects.filter(modulo=m, activo=True).order_by('orden', 'id'):
        print(
            f'  p{p.id} ord={p.orden} sec={p.seccion_id} tipo={p.tipo} '
            f'txt={len((p.contenido or "").strip())} url={bool((p.media_url or "").strip())} '
            f'apto={p.media_wa_apto} tit={(p.titulo or "")[:40]!r}'
        )


print('======== DETALLE IMPULSO 22 ========')
pasos_mod(22, 5)
pasos_mod(22, 8)
pasos_mod(22, 10)
pasos_mod(22, 11)

print('\n-- no_entendi 14d impulso --')
tels = [
    (e.telefono or '')[-10:]
    for e in Estudiante.objects.filter(progresos__curso_id=22).distinct()
    if e.telefono
]
n_no = 0
for log in WhatsappLog.objects.filter(fecha__gte=CUT, tipo='SENT').iterator():
    tail = (log.telefono or '')[-10:]
    if tail not in tels:
        continue
    if 'No entendí' in (log.mensaje or ''):
        n_no += 1
        if n_no <= 12:
            print(
                f'  [{log.fecha:%d/%m %H:%M}] …{tail[-4:]} '
                f'{(log.mensaje or "")[:90]!r}'
            )
print(f'  total_no_entendi={n_no}')

print('\n-- habeas/cedula impulso --')
for p in ProgresoEstudiante.objects.filter(curso_id=22).select_related('estudiante'):
    e = p.estudiante
    if e.estado_chat in ('ESPERANDO_HABEAS_DATA', 'ESPERANDO_CEDULA'):
        print(
            f'  {e.id} {(e.nombre or "")[:28]!r} chat={e.estado_chat} '
            f'onb={e.estado_onboarding} last={p.fecha_ultimo_avance}'
        )

print('\n======== DETALLE AGROSAVIA 35 ========')
pasos_mod(35, 1)
print('\n-- progresos agro --')
for p in ProgresoEstudiante.objects.filter(curso_id=35).select_related(
    'estudiante', 'modulo_actual'
):
    e = p.estudiante
    m = p.modulo_actual
    print(
        f'  est={e.id} {(e.nombre or "")[:24]!r} tel=…{(e.telefono or "")[-4:]} '
        f'onb={e.estado_onboarding} chat={e.estado_chat} '
        f'mod={getattr(m, "numero", None)} pub={getattr(m, "publicado_wa", None)} '
        f'done_flag={p.completado} last={p.fecha_ultimo_avance}'
    )

print('\n-- julian 2181 / 0629 --')
est = Estudiante.objects.filter(id=2181).first()
if not est:
    est = Estudiante.objects.filter(telefono__endswith='3026480629').first()
print(f'  est={est}')
if est:
    print(
        f'  onb={est.estado_onboarding} chat={est.estado_chat} ctx={est.contexto_temporal}'
    )
    for log in WhatsappLog.objects.filter(
        telefono__endswith=(est.telefono or '')[-10:]
    ).order_by('-fecha')[:18]:
        print(
            f'  [{log.fecha:%d/%m %H:%M}] {log.tipo} {log.estado} '
            f'audio={log.es_audio} {(log.mensaje or "")[:100]!r} '
            f'err={(log.error_detalle or "")[:60]!r}'
        )

print('\n-- dual telefono 22x35 --')
t22 = {
    (e.telefono or '')[-10:]
    for e in Estudiante.objects.filter(progresos__curso_id=22)
    if e.telefono
}
t35 = {
    (e.telefono or '')[-10:]
    for e in Estudiante.objects.filter(progresos__curso_id=35)
    if e.telefono
}
print('  overlap', t22 & t35)

print('\n-- p243 M8 (inactivo?) --')
p243 = PasoModulo.objects.filter(id=243).first()
if p243:
    print(
        f'  activo={p243.activo} apto={p243.media_wa_apto} '
        f'mod={p243.modulo_id} url={(p243.media_url or "")[-70:]}'
    )

print('\n======== FIN DETALLE ========')
