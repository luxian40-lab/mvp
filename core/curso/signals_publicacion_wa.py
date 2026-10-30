"""Señales publicación WA — alertas Slack en cursos activos."""
from django.db.models.signals import post_save
from django.dispatch import receiver

from core.models import Modulo


@receiver(post_save, sender=Modulo)
def modulo_borrador_slack_curso_activo(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        from core.modulo_publicacion import notificar_borrador_curso_activo

        notificar_borrador_curso_activo(instance)
    except Exception:
        pass
