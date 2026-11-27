"""Menú legado del bloque ACTIVO (puntos, ayuda, corregir datos, menú/inicio/hola). Movido tal cual del cuerpo del webhook (fase D7)."""

import logging

from core.conversacion.avance_whatsapp import MARCADOR_BOTON_CONTINUEMOS as _MARCADOR_CONTINUEMOS
from core.conversacion.contexto import CORTAR, Contexto, Respuesta
from core.conversacion.response_templates import parte_mensaje_con_media

logger = logging.getLogger('core.views.webhook_twilio')


def manejar(contexto: Contexto) -> Respuesta | None:
    estados_agente = contexto.locales['estados_agente']
    estudiante = contexto.estudiante
    msg_body = contexto.msg_body
    msg_from = contexto.msg_from
    msg_lower = contexto.locales['msg_lower']
    telefono_limpio = contexto.telefono_limpio
    # Detectar "Mis puntos" (botón o texto) - rama legacy
    if msg_lower in ['2', 'mis puntos', 'puntos', '🏆 mis puntos']:
        from core.canal.whatsapp_service import enviar_gamificacion_visual
        enviar_gamificacion_visual(msg_from, estudiante)
        return CORTAR
    
    # Detectar "Necesito ayuda" / PQRS / Soporte (todo unificado)
    elif msg_lower in ['3', 'necesito ayuda', 'ayuda', '🙋‍♂️ necesito ayuda', 'pqrs', 'soporte', 'queja', 'reclamo', 'solicitud']:
        from core.conversacion.security_handler import procesar_solicitud_soporte
        respuesta = procesar_solicitud_soporte(estudiante, msg_body, 'menu_ayuda')
        try:
            from core.lineas.salida_turno import enviar_respuesta_turno

            enviar_respuesta_turno(msg_from, respuesta, agente='menu_ayuda')
        except Exception:
            pass
        return CORTAR
    
    # Detectar "corregir datos" / "me equivoqué" -> iniciar autocorreccion guiada
    elif msg_lower in ['4', 'corregir datos', 'corregir mis datos', 'cambiar datos', 'cambiar mis datos',
                       'me equivoqué', 'me equivoque', 'editar datos', 'modificar datos',
                       'datos incorrectos', 'mis datos', 'actualizar datos']:
        from core.conversacion.correccion_datos import iniciar_flujo_correccion
        texto_respuesta = iniciar_flujo_correccion(estudiante)
        try:
            from core.lineas.salida_turno import enviar_respuesta_turno

            enviar_respuesta_turno(msg_from, texto_respuesta, agente='correccion_datos')
        except Exception as e:
            logger.error(f"❌ Error enviando corrección datos: {e}")
        return CORTAR
    
    # Detectar "menú" → enviar directamente al curso asignado (sin lista)
    elif msg_lower in ['menu', 'menú', 'inicio', 'hola']:
        if estudiante.estado_onboarding in estados_agente:
            logger.info(
                "menu/inicio/hola durante agente pedagógico (%s) — omitir reenvío de módulo",
                estudiante.estado_onboarding,
            )
        else:
            texto_respuesta = _texto_reenvio_menu(estudiante)
        try:
            _enviar_reenvio_menu(msg_from, telefono_limpio, texto_respuesta)
        except Exception as e:
            logger.error(f"❌ Error enviando curso: {e}")
        return CORTAR
    return None


def _texto_reenvio_menu(estudiante):
    curso, progreso, modulo = _curso_progreso_modulo_menu(estudiante)
    if not curso:
        return _texto_menu_sin_curso()
    if not modulo:
        return f"📚 Tu curso *{curso.nombre}* aún no tiene módulos configurados."
    return _texto_modulo_menu(progreso, modulo)


def _curso_progreso_modulo_menu(estudiante):
    from core.models import Curso, ProgresoEstudiante

    org = estudiante.cliente
    cursos = (
        Curso.objects.filter(cliente=org, activo=True).order_by('orden', 'nombre')
        if org
        else Curso.objects.filter(activo=True).order_by('orden', 'nombre')
    )
    progreso_existente = ProgresoEstudiante.objects.filter(
        estudiante=estudiante, completado=False, curso__activo=True
    ).first()
    curso = progreso_existente.curso if progreso_existente else cursos.first()
    if not curso:
        return None, None, None
    progreso, _ = ProgresoEstudiante.objects.get_or_create(
        estudiante=estudiante, curso=curso, defaults={'completado': False}
    )
    modulo = progreso.modulo_actual
    if not modulo:
        modulo = curso.modulos.order_by('numero').first()
        if modulo:
            progreso.modulo_actual = modulo
            from core.curso.module_steps import reset_progreso_pasos_modulo

            reset_progreso_pasos_modulo(progreso, save=False)
            progreso.save(
                update_fields=[
                    'modulo_actual',
                    'paso_actual_modulo',
                    'esperando_respuesta_evaluacion_paso',
                    'paso_evaluacion_paso_id',
                ]
            )
    return curso, progreso, modulo


def _texto_menu_sin_curso():
    return (
        "📚 Aún no tienes un curso asignado. "
        "Tu coordinador te lo asignará pronto.\n\n"
        "Si acaba de reportar un problema, cuando quiera retomar, pulse continuar, para seguir aprendiendo. O escriba *menú*.\n\n"
        + _MARCADOR_CONTINUEMOS
    )


def _texto_modulo_menu(progreso, modulo):
    from core.curso.module_steps import modulo_usa_pasos

    if modulo_usa_pasos(modulo):
        return _texto_modulo_modo_pasos(progreso, modulo)
    return _texto_modulo_legacy_multimedia(modulo)


def _texto_modulo_modo_pasos(progreso, modulo):
    from core.curso.module_steps import (
        log_y_mensaje_modo_pasos_sin_pasos,
        mensaje_recordatorio_paso_actual,
        pasos_activos_qs,
    )

    if not pasos_activos_qs(modulo).exists():
        return log_y_mensaje_modo_pasos_sin_pasos(modulo, 'views_menu_inicio')
    _np_m = pasos_activos_qs(modulo).count()
    if (
        progreso.paso_actual_modulo > _np_m
        and not progreso.esperando_respuesta_evaluacion_paso
    ):
        return (
            "✅ Ya recibiste todo el material de esta unidad.\n\n"
            "Pulse continuar, para seguir aprendiendo.\n\n"
            + _MARCADOR_CONTINUEMOS
        )
    _rem_m = mensaje_recordatorio_paso_actual(progreso, modulo)
    return _rem_m or (
        f"📖 *Módulo {modulo.numero}: {modulo.titulo}*\n\n"
        "Escribe *continuar* o *listo* cuando quieras seguir."
    )


def _texto_modulo_legacy_multimedia(modulo):
    from core.conversacion.response_templates import obtener_video_url
    from core.curso.module_steps import texto_legacy_whatsapp

    video_url = obtener_video_url(modulo)
    archivos_multimedia = modulo.archivos_multimedia.filter(activo=True)
    primera_media_url = None
    extra_media_urls = []
    if archivos_multimedia.exists():
        for archivo in archivos_multimedia:
            icono = {'video': '🎥', 'imagen': '🖼️', 'infografia': '📊', 'pdf': '📄', 'audio': '🎵'}.get(
                archivo.tipo, '📁'
            )
            url = archivo.get_url_para_envio()
            if url:
                if not primera_media_url:
                    primera_media_url = url
                else:
                    extra_media_urls.append((url, archivo.titulo, icono))
            elif not url:
                pass
    if not archivos_multimedia.exists() and video_url:
        primera_media_url = video_url
    msg_texto_menu = (
        f"📖 *Módulo {modulo.numero}: {modulo.titulo}*\n\n"
        f"{texto_legacy_whatsapp(modulo)}"
    )
    partes_menu = [msg_texto_menu]
    if primera_media_url:
        partes_menu.append(parte_mensaje_con_media(primera_media_url))
    for extra_url, _extra_titulo, _extra_icono in extra_media_urls:
        partes_menu.append(parte_mensaje_con_media(extra_url))
    if len(partes_menu) > 1:
        return "[MULTI_MSG]" + "[SEP]".join(partes_menu)
    return msg_texto_menu


def _enviar_reenvio_menu(msg_from, telefono_limpio, texto_respuesta):
    from core.lineas.salida_turno import entregar_en_turno

    entregar_en_turno(
        msg_from, telefono_limpio, texto_respuesta, agente='menu_curso',
    )