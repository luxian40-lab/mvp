from .models import SesionFormulario


def debe_usar_agente_formulario(estudiante) -> bool:
    """
    Indica si el mensaje debe atenderse con el agente de formulario (flujo secuencial),
    en lugar del bot educativo con RAG.
    """
    if estudiante is None or not getattr(estudiante, "pk", None):
        return False
    return SesionFormulario.objects.filter(estudiante=estudiante, completado=False).exists()
