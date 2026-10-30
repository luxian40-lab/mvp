"""Señales para emitir eventos IA observables (Parte 2A)."""

from django.db.models.signals import post_save
from django.dispatch import receiver

from core.models import ModuloCompletado


@receiver(post_save, sender=ModuloCompletado)
def emitir_evento_modulo_completado(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        from core.eventos_ia import emit_modulo_completado

        emit_modulo_completado(instance, origen='signal')
    except Exception:
        pass
