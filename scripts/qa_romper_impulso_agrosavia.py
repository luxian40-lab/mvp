"""QA adversarial: Impulso 22 (Zoraida) + Agrosavia 35. Solo lectura."""
from collections import Counter
from datetime import timedelta
from urllib.request import Request, urlopen

from django.utils import timezone

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
from core.helpers_examenes import evaluar_checkpoint_reto_ia

CUT = timezone.now() - timedelta(days=14)


def _head_ok(url, timeout=6):
    if not url or url.startswith('/'):
        return None
    try:
        req = Request(url, method='HEAD', headers={'User-Agent': 'eki-qa-romper/1.0'})
        with urlopen(req, timeout=timeout) as resp:
            return resp.status, int(resp.headers.get('Content-Length') or 0)
    except Exception as e:
        return f'ERR:{type(e).__name__}', 0


def auditar(curso_id, etiqueta):
    c = Curso.objects.filter(id=curso_id).first()
    print(f'\n======== {etiqueta} id={curso_id} ========')
    if not c:
        print('  NO EXISTE')
        return
    print(
        f"  nombre={c.nombre!r} activo={c.activo} ia={c.usar_agentes_ia} "
        f"gami={c.usar_gamificacion} drip_dias={c.dias_espera_entre_modulos} "
        f"asist={c.nombre_agente_asistente!r} tutor={c.nombre_agente_tutor!r} "
        f"perfil={getattr(c, 'perfil_facilitador', None)!r} "
        f"guia_curso_len={len(c.preguntas_ejemplo_ia or '')}"
    )
    mods = list(Modulo.objects.filter(curso=c).order_by('numero'))
    n_pub = sum(1 for m in mods if getattr(m, 'publicado_wa', False))
    print(f'  modulos={len(mods)} publicados_wa={n_pub}')
    total_pub = n_pub or len(mods)
    for m in mods:
        n_preg = PreguntaModulo.objects.filter(modulo=m, activa=True).count()
        n_pasos = PasoModulo.objects.filter(modulo=m, activo=True).count()
        n_vacios = 0
        n_media = 0
        n_no_apto = 0
        n_sin_flag = 0
        for p in PasoModulo.objects.filter(modulo=m, activo=True):
            has_txt = bool((p.contenido or '').strip())
            url = (p.media_url or '').strip()
            if url:
                n_media += 1
                if p.media_wa_apto is False:
                    n_no_apto += 1
                elif p.media_wa_apto is not True:
                    n_sin_flag += 1
            if not has_txt and not url:
                n_vacios += 1
        d = evaluar_checkpoint_reto_ia(m, total_pub, bool(c.usar_agentes_ia))
        print(
            f"  M{m.numero} id={m.id} pub={m.publicado_wa} modo={m.modo_entrega} "
            f"chk={m.facilitador_checkpoint} tipo={(m.tipo_reto_ia or '')[:18]!r} "
            f"guia={len(m.reto_guia_ia or '')} exam={m.examen_obligatorio} "
            f"preg={n_preg} pasos={n_pasos} vacios={n_vacios} media={n_media} "
            f"no_apto={n_no_apto} sin_flag={n_sin_flag} "
            f"drip={getattr(m, 'habilitado_desde', None)} "
            f"es_reto={d.es_reto} regla={d.regla_aplicada} "
            f"tit={(m.titulo or '')[:36]!r}"
        )

    print('  -- HEAD media no apta / video --')
    for p in PasoModulo.objects.filter(modulo__curso=c).exclude(media_url='').exclude(media_url__isnull=True):
        url = p.media_url or ''
        low = url.lower().split('?')[0]
        if p.media_wa_apto is False or low.endswith(('.mp4', '.m4v', '.mov', '.mp3')):
            st, nbytes = _head_ok(url)
            print(
                f"    p{p.id} M{p.modulo.numero} apto={p.media_wa_apto} "
                f"head={st} bytes={nbytes} {url[-70:]}"
            )

    progs = list(
        ProgresoEstudiante.objects.filter(curso=c).select_related('estudiante', 'modulo_actual')
    )
    print(f'  progresos={len(progs)}')
    onb = Counter()
    chat = Counter()
    pos = Counter()
    for p in progs:
        e = p.estudiante
        onb[e.estado_onboarding] += 1
        chat[e.estado_chat] += 1
        pos[getattr(p.modulo_actual, 'numero', None)] += 1
    print('  onboarding', dict(onb.most_common()))
    print('  chat', dict(chat.most_common()))
    print('  posicion_modulo', dict(sorted((k or 0, v) for k, v in pos.items())))

    tels = [(e.telefono or '')[-10:] for e in (p.estudiante for p in progs) if e.telefono]
    fails = 0
    noent = 0
    audio_fail = 0
    for log in WhatsappLog.objects.filter(fecha__gte=CUT).iterator():
        tail = (log.telefono or '')[-10:]
        if tail not in tels:
            continue
        if log.error_detalle or (log.estado or '').lower() in ('failed', 'undelivered'):
            fails += 1
            print(
                f"    FAIL [{log.fecha:%d/%m %H:%M}] …{(log.telefono or '')[-4:]} "
                f"{log.estado} {(log.error_detalle or '')[:80]!r}"
            )
        if 'No entendí' in (log.mensaje or ''):
            noent += 1
        if log.es_audio and '[AUDIO_NO_TRANSCRITO]' in (log.mensaje or ''):
            audio_fail += 1
    print(f'  logs14d fail={fails} no_entendi={noent} audio_fail={audio_fail}')

    print('  -- atascados agentes --')
    ids = [p.estudiante_id for p in progs]
    for e in Estudiante.objects.filter(id__in=ids).exclude(
        estado_onboarding__in=['completado', 'nuevo', 'curso_finalizado']
    ):
        ctx = e.contexto_temporal or {}
        p = next((x for x in progs if x.estudiante_id == e.id), None)
        done = ModuloCompletado.objects.filter(progreso=p).count() if p else 0
        print(
            f"    {e.id} {(e.nombre or '')[:28]!r} onb={e.estado_onboarding} "
            f"tipo={ctx.get('tipo')} preg={ctx.get('preguntas_hechas')} "
            f"mod_act={getattr(p.modulo_actual, 'numero', None) if p else None} "
            f"done={done} last={getattr(p, 'fecha_ultimo_avance', None)}"
        )


auditar(22, 'IMPULSO ZORAIDA')
auditar(35, 'AGROSAVIA')
print('\n======== FIN ========')
