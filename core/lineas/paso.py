"""Un paso del módulo (evaluación). El curso llama y, si hubo respuesta, sale."""
import logging

from core.models import ProgresoEstudiante

logger = logging.getLogger(__name__)


def responder_evaluacion_paso(estudiante, msg_body, msg_from, telefono_limpio, estado_chat) -> bool:
    if estado_chat != 'ACTIVO':
        return False
    from core.module_steps import procesar_respuesta_evaluacion_paso

    prog = (
        ProgresoEstudiante.objects.filter(estudiante=estudiante, completado=False)
        .order_by('-fecha_inicio')
        .first()
    )
    ctx = estudiante.contexto_temporal or {}
    fid = ctx.get('curso_activo_id')
    if fid and prog and prog.curso_id != int(fid):
        prog = (
            ProgresoEstudiante.objects.filter(
                estudiante=estudiante, completado=False, curso_id=int(fid),
            ).first()
            or prog
        )
    if not prog:
        return False
    resp = procesar_respuesta_evaluacion_paso(estudiante, prog, msg_body)
    if resp is None:
        return False
    logger.info(
        '📚 [pasos] respuesta evaluación procesada en webhook | est=%s',
        estudiante.id,
    )
    try:
        from core.lineas.envio import enviar_respuesta_linea

        _entregar_paso(estudiante, msg_from, resp, enviar_respuesta_linea)
    except Exception as e:
        logger.error(f'❌ Error enviando respuesta paso módulo: {e}', exc_info=True)
    return True


def _entregar_paso(estudiante, msg_from, resp, enviar) -> None:
    import time

    from core.conversacion.marcas import PAUSA, PLANTILLA, es_marcado, partes, separar_media
    from core.views.twilio_transporte import youtube_hace_solo_enlace_en_texto

    def _una(texto, media):
        if media and youtube_hace_solo_enlace_en_texto(media):
            logger.warning(
                '📎 [pasos] URL parece YouTube (no MP4 directo) | est=%s',
                estudiante.id,
            )
        enviar(msg_from, texto, media_url=media, agente='paso')

    if es_marcado(resp):
        for parte in partes(resp):
            if parte.tipo == PAUSA:
                time.sleep(parte.segundos)
                continue
            if parte.tipo == PLANTILLA:
                _una(*separar_media(parte.texto))
            else:
                _una(parte.texto, parte.media)
            time.sleep(0.5)
        return
    _una(*separar_media((resp or '').strip()))
