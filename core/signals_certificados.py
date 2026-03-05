"""
Signals para Certificados
Auto-generación al completar cursos
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import ProgresoEstudiante
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=ProgresoEstudiante)
def generar_certificado_al_completar(sender, instance, created, **kwargs):
    """
    Genera automáticamente el certificado cuando el estudiante completa un curso.
    Solo genera — NO envía por WhatsApp (views.py se encarga del envío
    dentro del flujo de multi-mensaje de felicitación).
    """
    # Solo procesar si completado cambió a True y hay fecha_completado
    if instance.completado and instance.fecha_completado:
        from .certificado_service import crear_certificado_automatico, generar_y_guardar_certificado
        from .models_certificados import Certificado
        
        try:
            # Verificar si ya existe certificado para evitar duplicados
            certificado_existente = Certificado.objects.filter(
                estudiante=instance.estudiante,
                curso=instance.curso
            ).first()
            
            if certificado_existente:
                logger.info(f"✅ Certificado ya existe para {instance.estudiante.nombre} - {instance.curso.nombre} (código: {certificado_existente.codigo_verificacion})")
                return
            
            # Crear y generar certificado (solo generación, sin envío WhatsApp)
            logger.info(f"🎓 Generando certificado para {instance.estudiante.nombre} - {instance.curso.nombre}")
            certificado = crear_certificado_automatico(instance.estudiante, instance.curso)
            
            if certificado:
                # Asegurar que tiene imagen/PDF generado
                if not certificado.archivo_imagen and not certificado.archivo_pdf:
                    logger.info(f"📄 Generando archivo del certificado...")
                    generar_y_guardar_certificado(certificado)
                
                logger.info(f"✅ Certificado generado: {certificado.codigo_verificacion} (envío via views.py)")
            else:
                logger.error(f"❌ Error al crear certificado para {instance.estudiante.nombre}")
                
        except Exception as e:
            logger.error(f"❌ Error en signal de certificado para {instance.estudiante.nombre}: {str(e)}", exc_info=True)
