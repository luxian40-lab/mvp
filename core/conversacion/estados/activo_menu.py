"""Menú legado del bloque ACTIVO (puntos, ayuda, corregir datos, menú/inicio/hola). Movido tal cual del cuerpo del webhook (fase D7)."""

import logging

from django.conf import settings

from core.avance_whatsapp import MARCADOR_BOTON_CONTINUEMOS as _MARCADOR_CONTINUEMOS
from core.conversacion.contexto import CORTAR, Contexto, Respuesta
from core.models import WhatsappLog
from core.response_templates import parte_mensaje_con_media
from core.views.twilio_transporte import _enviar_mensaje_twilio_segmentado

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
        from core.whatsapp_service import enviar_gamificacion_visual
        enviar_gamificacion_visual(msg_from, estudiante)
        return CORTAR
    
    # Detectar "Necesito ayuda" / PQRS / Soporte (todo unificado)
    elif msg_lower in ['3', 'necesito ayuda', 'ayuda', '🙋‍♂️ necesito ayuda', 'pqrs', 'soporte', 'queja', 'reclamo', 'solicitud']:
        from core.security_handler import procesar_solicitud_soporte
        respuesta = procesar_solicitud_soporte(estudiante, msg_body, 'menu_ayuda')
        try:
            from twilio.rest import Client as TwilioClient
            account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
            auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
            twilio_number = getattr(settings, 'TWILIO_PHONE_NUMBER', 'whatsapp:+573202948806')
            client_tw = TwilioClient(account_sid, auth_token)
            destino = f'whatsapp:{msg_from}' if not msg_from.startswith('whatsapp:') else msg_from
            client_tw.messages.create(body=respuesta, from_=str(twilio_number).strip(), to=str(destino).strip())
            WhatsappLog.objects.create(telefono=telefono_limpio, mensaje=respuesta, tipo='SENT')
        except Exception:
            pass
        return CORTAR
    
    # Detectar "corregir datos" / "me equivoqué" -> iniciar autocorreccion guiada
    elif msg_lower in ['4', 'corregir datos', 'corregir mis datos', 'cambiar datos', 'cambiar mis datos',
                       'me equivoqué', 'me equivoque', 'editar datos', 'modificar datos',
                       'datos incorrectos', 'mis datos', 'actualizar datos']:
        from core.correccion_datos import iniciar_flujo_correccion
        texto_respuesta = iniciar_flujo_correccion(estudiante)
        try:
            from twilio.rest import Client as TwilioClient
            account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
            auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
            twilio_number = getattr(settings, 'TWILIO_PHONE_NUMBER', 'whatsapp:+573202948806')
            client_tw = TwilioClient(account_sid, auth_token)
            destino = f'whatsapp:{msg_from}' if not msg_from.startswith('whatsapp:') else msg_from
            client_tw.messages.create(body=texto_respuesta, from_=str(twilio_number).strip(), to=str(destino).strip())
            WhatsappLog.objects.create(telefono=telefono_limpio, mensaje=texto_respuesta, tipo='SENT')
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
            from core.models import Curso, ProgresoEstudiante
            from core.response_templates import obtener_video_url
            org = estudiante.cliente
            cursos = Curso.objects.filter(cliente=org, activo=True).order_by('orden', 'nombre') if org else Curso.objects.filter(activo=True).order_by('orden', 'nombre')
            progreso_existente = ProgresoEstudiante.objects.filter(
                estudiante=estudiante, completado=False, curso__activo=True
            ).first()
            curso = progreso_existente.curso if progreso_existente else cursos.first()
            if curso:
                progreso, _ = ProgresoEstudiante.objects.get_or_create(
                    estudiante=estudiante, curso=curso, defaults={'completado': False}
                )
                modulo = progreso.modulo_actual
                if not modulo:
                    modulo = curso.modulos.order_by('numero').first()
                    if modulo:
                        progreso.modulo_actual = modulo
                        from core.module_steps import reset_progreso_pasos_modulo
                        reset_progreso_pasos_modulo(progreso, save=False)
                        progreso.save(
                            update_fields=[
                                'modulo_actual',
                                'paso_actual_modulo',
                                'esperando_respuesta_evaluacion_paso',
                                'paso_evaluacion_paso_id',
                            ]
                        )
                if modulo:
                    from core.module_steps import (
                        modulo_usa_pasos,
                        mensaje_recordatorio_paso_actual,
                        pasos_activos_qs,
                        log_y_mensaje_modo_pasos_sin_pasos,
                    )
                    if modulo_usa_pasos(modulo):
                        if not pasos_activos_qs(modulo).exists():
                            texto_respuesta = log_y_mensaje_modo_pasos_sin_pasos(
                                modulo, 'views_menu_inicio'
                            )
                        else:
                            _np_m = pasos_activos_qs(modulo).count()
                            if (
                                progreso.paso_actual_modulo > _np_m
                                and not progreso.esperando_respuesta_evaluacion_paso
                            ):
                                texto_respuesta = (
                                    "✅ Ya recibiste todo el material de esta unidad.\n\n"
                                    "Pulse continuar, para seguir aprendiendo.\n\n"
                                    + _MARCADOR_CONTINUEMOS
                                )
                            else:
                                _rem_m = mensaje_recordatorio_paso_actual(progreso, modulo)
                                texto_respuesta = _rem_m or (
                                    f"📖 *Módulo {modulo.numero}: {modulo.titulo}*\n\n"
                                    "Escribe *continuar* o *listo* cuando quieras seguir."
                                )
                    else:
                        video_url = obtener_video_url(modulo)
                        archivos_multimedia = modulo.archivos_multimedia.filter(activo=True)
                        archivos_msg = ""
                        primera_media_url = None
                        extra_media_urls = []
                        if archivos_multimedia.exists():
                            archivos_msg = ""
                            for idx, archivo in enumerate(archivos_multimedia):
                                icono = {'video': '🎥', 'imagen': '🖼️', 'infografia': '📊', 'pdf': '📄', 'audio': '🎵'}.get(archivo.tipo, '📁')
                                url = archivo.get_url_para_envio()
                                if url:
                                    if not primera_media_url:
                                        primera_media_url = url
                                        archivos_msg += f"\n{icono} {archivo.titulo} (adjunto)"
                                    else:
                                        extra_media_urls.append((url, archivo.titulo, icono))
                                        archivos_msg += f"\n{icono} {archivo.titulo} (adjunto)"
                                else:
                                    archivos_msg += f"\n{icono} {archivo.titulo}"
                        if not archivos_multimedia.exists() and video_url:
                            primera_media_url = video_url
                        from core.module_steps import texto_legacy_whatsapp
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
                            texto_respuesta = "[MULTI_MSG]" + "[SEP]".join(partes_menu)
                        else:
                            texto_respuesta = msg_texto_menu
                else:
                    texto_respuesta = f"📚 Tu curso *{curso.nombre}* aún no tiene módulos configurados."
            else:
                texto_respuesta = (
                    "📚 Aún no tienes un curso asignado. "
                    "Tu coordinador te lo asignará pronto.\n\n"
                    "Si acaba de reportar un problema, cuando quiera retomar, pulse continuar, para seguir aprendiendo. O escriba *menú*.\n\n"
                    + _MARCADOR_CONTINUEMOS
                )
            try:
                from twilio.rest import Client as TwilioClient
                account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
                auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
                twilio_number = getattr(settings, 'TWILIO_PHONE_NUMBER', 'whatsapp:+573202948806')
                client_tw = TwilioClient(account_sid, auth_token)
                destino = f'whatsapp:{msg_from}' if not msg_from.startswith('whatsapp:') else msg_from
                twilio_from = str(twilio_number).strip()

                if texto_respuesta.startswith('[MULTI_MSG]'):
                    import re as re_menu_m
                    partes_mm = texto_respuesta.replace('[MULTI_MSG]', '', 1).split('[SEP]')
                    for parte_mm in partes_mm:
                        if not parte_mm.strip():
                            continue
                        parte_txt = parte_mm.strip()
                        delay_mm = re_menu_m.match(r'^\[DELAY:(\d+)\]$', parte_txt)
                        if delay_mm:
                            import time
                            time.sleep(int(delay_mm.group(1)))
                            continue
                        media_mm = re_menu_m.search(r'\[MEDIA:(.*?)\]', parte_txt)
                        parte_media_mm = None
                        if media_mm:
                            parte_media_mm = media_mm.group(1).strip()
                            parte_txt = parte_txt.replace(media_mm.group(0), '').strip()
                        cuerpo_mm = parte_txt.strip() if parte_txt else ''
                        enviados_mm = _enviar_mensaje_twilio_segmentado(
                            client=client_tw,
                            from_number=twilio_from,
                            to_number=str(destino).strip(),
                            body=cuerpo_mm if cuerpo_mm else ' ',
                            media_url=parte_media_mm,
                        )
                        import time
                        time.sleep(0.5)
                        from core.twilio_media import mensaje_log_con_media
                        for seg_i, (msg_mm, texto_env) in enumerate(enviados_mm, start=1):
                            WhatsappLog.objects.create(
                                telefono=telefono_limpio,
                                mensaje=mensaje_log_con_media(
                                    texto_env or cuerpo_mm or parte_txt,
                                    parte_media_mm if seg_i == 1 else None,
                                )[:1500],
                                mensaje_id=getattr(msg_mm, 'sid', None),
                                tipo='SENT',
                            )
                else:
                    media_url_menu = None
                    import re as re_menu
                    media_m = re_menu.search(r'\[MEDIA:(.*?)\]', texto_respuesta)
                    if media_m:
                        media_url_menu = media_m.group(1).strip()
                        texto_respuesta = texto_respuesta.replace(media_m.group(0), '').strip()
                    enviados_menu = _enviar_mensaje_twilio_segmentado(
                        client=client_tw,
                        from_number=twilio_from,
                        to_number=str(destino).strip(),
                        body=texto_respuesta,
                        media_url=media_url_menu,
                    )
                    from core.twilio_media import mensaje_log_con_media
                    for seg_i, (msg_menu, texto_env) in enumerate(enviados_menu, start=1):
                        WhatsappLog.objects.create(
                            telefono=telefono_limpio,
                            mensaje=mensaje_log_con_media(
                                texto_env or texto_respuesta,
                                media_url_menu if seg_i == 1 else None,
                            )[:1500],
                            mensaje_id=getattr(msg_menu, 'sid', None),
                            tipo='SENT',
                        )
            except Exception as e:
                logger.error(f"❌ Error enviando curso: {e}")
            return CORTAR
    return None
