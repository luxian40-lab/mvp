"""Camino Impulso 22 hasta M11: contenido + logs de las 3. Solo lectura."""
from collections import Counter
from datetime import timedelta

from django.utils import timezone

from core.helpers_examenes import evaluar_checkpoint_reto_ia
from core.models import (
    Curso,
    Estudiante,
    Modulo,
    ModuloCompletado,
    PasoModulo,
    PreguntaModulo,
    ProgresoEstudiante,
    WhatsappLog,
)
from core.modulo_publicacion import siguiente_modulo_publicado_wa

CUT = timezone.now() - timedelta(days=60)
IDS = (1937, 1963, 1964)
c = Curso.objects.get(id=22)
print(f'curso={c.nombre!r} ia={c.usar_agentes_ia} drip_dias={c.dias_espera_entre_modulos}')

print('\n======== M1..M11 ========')
mods = list(Modulo.objects.filter(curso_id=22, numero__gte=1, numero__lte=11).order_by('numero'))
for m in mods:
    n_preg = PreguntaModulo.objects.filter(modulo=m, activa=True).count()
    pasos = list(PasoModulo.objects.filter(modulo=m, activo=True).order_by('orden', 'id'))
    vacios = sum(1 for p in pasos if not (p.contenido or '').strip() and not (p.media_url or '').strip())
    no_apto = [p.id for p in pasos if p.media_url and p.media_wa_apto is False]
    sin_flag = [p.id for p in pasos if p.media_url and p.media_wa_apto is None]
    d = evaluar_checkpoint_reto_ia(m, 12, True)
    sig = siguiente_modulo_publicado_wa(c, m)
    print(
        f'  M{m.numero} id={m.id} pub={m.publicado_wa} modo={m.modo_entrega} '
        f'chk={m.facilitador_checkpoint} exam={m.examen_obligatorio} preg={n_preg} '
        f'pasos={len(pasos)} vacios={vacios} no_apto={no_apto} sin_flag={sin_flag} '
        f'drip={getattr(m, "habilitado_desde", None)} reto={d.es_reto} '
        f'sig={getattr(sig, "numero", None)} tit={(m.titulo or "")[:32]!r}'
    )
    for p in pasos:
        url = (p.media_url or '').strip()
        if not url and (p.contenido or '').strip():
            continue
        if url or not (p.contenido or '').strip():
            print(
                f'    p{p.id} o={p.orden} tipo={p.tipo} eval={p.es_evaluacion} '
                f'txt={len((p.contenido or "").strip())} url={bool(url)} '
                f'apto={p.media_wa_apto} ext={url.split("?")[0][-18:]} '
                f'tit={(p.titulo or "")[:36]!r}'
            )

print('\n======== LAS 3 ========')
for eid in IDS:
    e = Estudiante.objects.get(id=eid)
    p = ProgresoEstudiante.objects.filter(estudiante=e, curso_id=22).select_related(
        'modulo_actual'
    ).first()
    done = list(
        ModuloCompletado.objects.filter(progreso=p).values_list('modulo__numero', flat=True)
    ) if p else []
    tel = (e.telefono or '')[-10:]
    print(
        f'\n-- {e.id} {e.nombre!r} tel=…{tel[-4:]} onb={e.estado_onboarding} '
        f'chat={e.estado_chat} mod_act={getattr(getattr(p, "modulo_actual", None), "numero", None)} '
        f'paso={getattr(p, "paso_actual_modulo", None)} done={sorted(done)} '
        f'ctx={e.contexto_temporal}'
    )
    n_fail = n_no = n_audio = 0
    last_in = last_out = None
    sample_fail = []
    for log in WhatsappLog.objects.filter(telefono__endswith=tel).order_by('-fecha')[:80]:
        if last_out is None and log.tipo == 'SENT':
            last_out = log
        if last_in is None and log.tipo == 'INCOMING':
            last_in = log
        st = (log.estado or '').lower()
        if log.error_detalle or st in ('failed', 'undelivered'):
            n_fail += 1
            if len(sample_fail) < 4:
                sample_fail.append(
                    f'{log.fecha:%d/%m %H:%M} {log.estado} {(log.error_detalle or "")[:70]}'
                )
        if log.tipo == 'SENT' and 'No entendí' in (log.mensaje or ''):
            n_no += 1
        if log.es_audio or '[AUDIO_NO_TRANSCRITO]' in (log.mensaje or ''):
            n_audio += 1
    print(f'  fail={n_fail} no_entendi={n_no} audio_flags={n_audio}')
    if last_in:
        print(f'  last_in [{last_in.fecha:%d/%m %H:%M}] {(last_in.mensaje or "")[:90]!r}')
    if last_out:
        print(
            f'  last_out [{last_out.fecha:%d/%m %H:%M}] {last_out.estado} '
            f'{(last_out.mensaje or "")[:90]!r} err={(last_out.error_detalle or "")[:50]!r}'
        )
    for s in sample_fail:
        print(f'  FAIL {s}')

print('\n======== QUIEN LLEGO A M7+ ========')
for mc in (
    ModuloCompletado.objects.filter(progreso__curso_id=22, modulo__numero__gte=7)
    .select_related('progreso__estudiante', 'modulo')
    .order_by('modulo__numero', 'id')
):
    e = mc.progreso.estudiante
    print(
        f'  M{mc.modulo.numero} est={e.id} {(e.nombre or "")[:22]!r} '
        f'onb={e.estado_onboarding} fecha={mc.fecha_completado}'
    )

print('\n======== LOGS FAIL CURSO 22 (60d) ========')
tels = {
    (e.telefono or '')[-10:]
    for e in Estudiante.objects.filter(progresos__curso_id=22)
    if e.telefono
}
ctr = Counter()
for log in WhatsappLog.objects.filter(fecha__gte=CUT).iterator():
    tail = (log.telefono or '')[-10:]
    if tail not in tels:
        continue
    st = (log.estado or '').lower()
    err = log.error_detalle or ''
    if err or st in ('failed', 'undelivered'):
        code = 'otro'
        for cde in ('63019', '63021', '63005', '21610', '21211'):
            if cde in err:
                code = cde
                break
        ctr[code] += 1
        if sum(ctr.values()) <= 12:
            print(
                f'  [{log.fecha:%d/%m %H:%M}] …{tail[-4:]} {log.estado} '
                f'{err[:80]!r} msg={(log.mensaje or "")[:50]!r}'
            )
print('  tally', dict(ctr))
print('\n======== FIN ========')
