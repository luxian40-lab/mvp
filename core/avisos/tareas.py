from celery import shared_task


@shared_task
def aviso_modulo_disponible():
    """Aviso «Módulo disponible» por calendario. Con EKI_AVISO_MODULO_DISPONIBLE_ENABLED en false no envía."""
    from core.avisos.modulo_disponible import ejecutar

    return ejecutar()
