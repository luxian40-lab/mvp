import time
from .models import EnvioLog
from .utils import enviar_whatsapp_twilio
import logging

logger = logging.getLogger(__name__)

def ejecutar_campana_servicio(campana):
    """
    Ejecuta el envío real de mensajes WhatsApp a los destinatarios de la campaña.
    Soporta:
      - template_twilio_id: Envío directo con Content Template de Twilio
      - plantilla Django: Envío con texto personalizado (cuerpo_mensaje)
    """
    # Determinar destinatarios según tipo de audiencia
    if hasattr(campana, 'tipo_audiencia') and campana.tipo_audiencia == 'grupo' and campana.grupo:
        destinatarios = campana.grupo.estudiantes.filter(activo=True)
        logger.info(f"Campana grupal: {campana.grupo.nombre} ({destinatarios.count()} estudiantes)")
    else:
        destinatarios = campana.destinatarios.filter(activo=True)
        logger.info(f"Campana individual: {destinatarios.count()} destinatarios")
    
    # Determinar modo de envío
    usa_template_twilio = bool(campana.template_twilio_id)
    usa_plantilla_django = (
        not usa_template_twilio 
        and campana.plantilla 
        and (
            getattr(campana.plantilla, 'content_sid', None) 
            or getattr(campana.plantilla, 'cuerpo_mensaje', None)
        )
    )
    
    if usa_template_twilio:
        content_sid = campana.template_twilio_id.strip()
        logger.info(f"Modo: Content Template de Twilio ({content_sid})")
    elif usa_plantilla_django and getattr(campana.plantilla, 'content_sid', None):
        content_sid = campana.plantilla.content_sid.strip()
        logger.info(f"Modo: Plantilla Django con content_sid ({content_sid})")
    elif usa_plantilla_django and getattr(campana.plantilla, 'cuerpo_mensaje', None):
        content_sid = None
        mensaje_base = campana.plantilla.cuerpo_mensaje
        logger.info(f"Modo: Plantilla Django con cuerpo_mensaje")
    else:
        raise ValueError(
            f"La campana '{campana.nombre}' no tiene un Content SID de Twilio "
            f"ni una plantilla Django con contenido configurado."
        )
    
    resultados = {
        "total": destinatarios.count(),
        "exitosos": 0,
        "fallidos": 0
    }

    logger.info(f"INICIANDO CAMPANA: {campana.nombre} - {resultados['total']} destinatarios")
    
    for estudiante in destinatarios:
        try:
            # Si es campaña de curso, poner al estudiante en flujo de onboarding
            if getattr(campana, 'es_campana_curso', False):
                estudiante.estado_chat = 'ESPERANDO_HABEAS_DATA'
                estudiante.acepto_terminos = False
                estudiante.estado_onboarding = 'nuevo'
                estudiante.save()
                # Si hay curso destino, crear progreso
                if getattr(campana, 'curso_destino', None):
                    from .models import ProgresoEstudiante
                    ProgresoEstudiante.objects.get_or_create(
                        estudiante=estudiante,
                        curso=campana.curso_destino,
                        defaults={'completado': False}
                    )
            
            if content_sid:
                # Envío con Content Template de Twilio
                from .whatsapp_service import enviar_template_twilio
                variables = {'1': estudiante.nombre or 'Estudiante'}
                resultado = enviar_template_twilio(
                    telefono=estudiante.telefono,
                    content_sid=content_sid,
                    variables=variables
                )
            else:
                # Envío con texto personalizado de plantilla Django
                mensaje_personalizado = mensaje_base.replace("{nombre}", estudiante.nombre or '')
                mensaje_personalizado = mensaje_personalizado.replace("{telefono}", estudiante.telefono or '')
                resultado = enviar_whatsapp_twilio(
                    telefono=estudiante.telefono,
                    texto=mensaje_personalizado
                )
            
            if resultado.get('success'):
                EnvioLog.objects.create(
                    campana=campana,
                    estudiante=estudiante,
                    estado='ENVIADO',
                    respuesta_api=f"Message SID: {resultado.get('mensaje_id', 'N/A')}"
                )
                resultados["exitosos"] += 1
                logger.info(f"Enviado a {estudiante.nombre} ({estudiante.telefono})")
            else:
                raise Exception(resultado.get('response', 'Error desconocido'))

        except Exception as e:
            EnvioLog.objects.create(
                campana=campana,
                estudiante=estudiante,
                estado='FALLIDO',
                respuesta_api=str(e)
            )
            resultados["fallidos"] += 1
            logger.error(f"Fallo {estudiante.nombre}: {str(e)}")
        
        # Delay para no saturar la API
        time.sleep(0.5)

    # Marcar campaña como ejecutada y guardar stats
    campana.ejecutada = True
    campana.total_enviados = resultados["exitosos"]
    campana.save()
    
    logger.info(f"CAMPANA COMPLETADA: {resultados['exitosos']} exitosos, {resultados['fallidos']} fallidos")
    
    return resultados