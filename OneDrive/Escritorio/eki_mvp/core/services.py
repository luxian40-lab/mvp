import time
from .models import EnvioLog
from .utils import enviar_whatsapp

def ejecutar_campana_servicio(campana):
    """
    Envía mensajes (con o sin imagen) y guarda el registro (Log).
    """
    # Filtramos destinatarios activos
    destinatarios = campana.destinatarios.filter(activo=True)
    mensaje_base = campana.plantilla.cuerpo_mensaje
    
    # Obtener URL de imagen si la plantilla la tiene
    url_imagen = None
    if campana.plantilla.tiene_imagen and campana.plantilla.url_imagen:
        url_imagen = campana.plantilla.url_imagen
    
    resultados = {
        "total": destinatarios.count(),
        "exitosos": 0,
        "fallidos": 0
    }

    print(f"🚀 INICIANDO CAMPAÑA: {campana.nombre}")
    if url_imagen:
        print(f"📸 Con imagen: {url_imagen}")
    
    for estudiante in destinatarios:
        try:
            # 1. Personalización del mensaje
            mensaje_personalizado = mensaje_base.replace("{nombre}", estudiante.nombre)
            
            # 2. Enviar mensaje (con o sin imagen)
            resultado = enviar_whatsapp(
                telefono=estudiante.telefono,
                texto=mensaje_personalizado,
                url_imagen=url_imagen
            )
            
            if resultado['success']:
                # 3. Guardar Log de Éxito
                EnvioLog.objects.create(
                    campana=campana,
                    estudiante=estudiante,
                    estado='ENVIADO',
                    respuesta_api=f"Message ID: {resultado.get('mensaje_id', 'N/A')}"
                )
                resultados["exitosos"] += 1
                print(f"✅ Enviado a {estudiante.nombre}")
            else:
                raise Exception(str(resultado.get('response', 'Error desconocido')))

        except Exception as e:
            # 4. Guardar Log de Fallo
            EnvioLog.objects.create(
                campana=campana,
                estudiante=estudiante,
                estado='FALLIDO',
                respuesta_api=str(e)
            )
            resultados["fallidos"] += 1
            print(f"❌ Falló {estudiante.nombre}: {str(e)}")

    # Marcar campaña como ejecutada
    campana.ejecutada = True
    campana.save()
    
    return resultados