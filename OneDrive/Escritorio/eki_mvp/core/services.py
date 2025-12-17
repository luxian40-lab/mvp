import time
from .models import EnvioLog

def ejecutar_campana_servicio(campana):
    """
    Simula el envío de mensajes y guarda el registro (Log).
    """
    # Filtramos destinatarios activos
    destinatarios = campana.destinatarios.filter(activo=True)
    mensaje_base = campana.plantilla.cuerpo_mensaje
    
    resultados = {
        "total": destinatarios.count(),
        "exitosos": 0,
        "fallidos": 0
    }

    print(f"🚀 INICIANDO CAMPAÑA: {campana.nombre}")
    
    for estudiante in destinatarios:
        try:
            # 1. Simular personalización
            mensaje_personalizado = mensaje_base.replace("{nombre}", estudiante.nombre)
            
            # 2. Simular envío (delay de 0.1s)
            time.sleep(0.1) 
            
            # Simular un error si el nombre dice "Error"
            if "Error" in estudiante.nombre:
                raise Exception("Número inválido simulado")

            # 3. Guardar Log de Éxito
            EnvioLog.objects.create(
                campana=campana,
                estudiante=estudiante,
                estado='ENVIADO',
                respuesta_api="Message ID: wamid.12345"
            )
            resultados["exitosos"] += 1
            print(f"✅ Enviado a {estudiante.nombre}")

        except Exception as e:
            # 4. Guardar Log de Fallo
            EnvioLog.objects.create(
                campana=campana,
                estudiante=estudiante,
                estado='FALLIDO',
                respuesta_api=str(e)
            )
            resultados["fallidos"] += 1
            print(f"❌ Falló {estudiante.nombre}")

    # Marcar campaña como ejecutada
    campana.ejecutada = True
    campana.save()
    
    return resultados