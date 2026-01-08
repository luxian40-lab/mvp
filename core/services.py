import time
from .models import EnvioLog
from .utils import enviar_whatsapp_twilio
import logging

logger = logging.getLogger(__name__)

def ejecutar_campana_servicio(campana):
    """
    Ejecuta el envío real de mensajes WhatsApp a los destinatarios de la campaña.
    """
    # Filtramos destinatarios activos
    destinatarios = campana.destinatarios.filter(activo=True)
    mensaje_base = campana.plantilla.cuerpo_mensaje
    
    resultados = {
        "total": destinatarios.count(),
        "exitosos": 0,
        "fallidos": 0
    }

    logger.info(f"🚀 INICIANDO CAMPAÑA: {campana.nombre} - {resultados['total']} destinatarios")
    print(f"🚀 CAMPAÑA: {campana.nombre} - {resultados['total']} destinatarios")
    
    for estudiante in destinatarios:
        try:
            # 1. Personalizar mensaje
            mensaje_personalizado = mensaje_base.replace("{nombre}", estudiante.nombre)
            mensaje_personalizado = mensaje_personalizado.replace("{telefono}", estudiante.telefono)
            
            print(f"📤 Enviando a {estudiante.nombre} ({estudiante.telefono})")
            print(f"💬 Mensaje: {mensaje_personalizado[:100]}...")
            
            # 2. Enviar mensaje real por WhatsApp
            resultado = enviar_whatsapp_twilio(
                telefono=estudiante.telefono,
                texto=mensaje_personalizado
            )
            
            print(f"🔍 Resultado: {resultado}")
            
            if resultado.get('success'):  # ← Cambio: 'success' en vez de 'exito'
                # 3. Guardar Log de Éxito
                EnvioLog.objects.create(
                    campana=campana,
                    estudiante=estudiante,
                    estado='ENVIADO',
                    respuesta_api=f"Message SID: {resultado.get('mensaje_id', 'N/A')}"
                )
                resultados["exitosos"] += 1
                logger.info(f"✅ Enviado a {estudiante.nombre} ({estudiante.telefono})")
            else:
                raise Exception(resultado.get('response', 'Error desconocido'))

        except Exception as e:
            # 4. Guardar Log de Fallo
            EnvioLog.objects.create(
                campana=campana,
                estudiante=estudiante,
                estado='FALLIDO',
                respuesta_api=str(e)
            )
            resultados["fallidos"] += 1
            logger.error(f"❌ Falló {estudiante.nombre}: {str(e)}")
        
        # Pequeño delay para no saturar la API
        time.sleep(0.5)

    # Marcar campaña como ejecutada
    campana.ejecutada = True
    campana.save()
    
    logger.info(f"🏁 CAMPAÑA COMPLETADA: {resultados['exitosos']} exitosos, {resultados['fallidos']} fallidos")
    
    return resultados