"""
Señales: recalcular ResultadoGEI al guardar FichaGEI y enviar WhatsApp al cerrar el módulo N (por defecto 5).
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


def _modulo_numero_para_mensaje_resultado() -> int:
    return int(getattr(settings, "GEI_MODULO_NUMERO_WHATSAPP_RESULTADO", 5) or 5)


@receiver(post_save, sender="formulario.FichaGEI")
def recalcular_resultado_gei(sender, instance, **kwargs):
    """Cada vez que se actualiza la ficha, recalcula y persiste el resultado."""
    from formulario.calculadora import persistir_resultado_gei

    try:
        persistir_resultado_gei(instance)
    except Exception as e:
        logger.exception("Error persistiendo ResultadoGEI para ficha %s: %s", instance.pk, e)


@receiver(post_save, sender="core.ModuloCompletado")
def enviar_balance_gei_tras_modulo(sender, instance, created, **kwargs):
    """
    Al completar el módulo configurado (por defecto 5), envía por WhatsApp el resumen del balance
    si el curso tiene formulario GEI y existe ficha para ese estudiante/curso.
    """
    if not created:
        return
    if not getattr(settings, "GEI_RESULTADO_WHATSAPP_ENABLED", True):
        return

    try:
        modulo = instance.modulo
        if modulo.numero != _modulo_numero_para_mensaje_resultado():
            return
    except Exception:
        return

    progreso = instance.progreso
    curso = progreso.curso
    if not getattr(curso, "tiene_formulario_gei", False):
        return

    estudiante = progreso.estudiante
    from formulario.calculadora import generar_mensaje_resultado_whatsapp, persistir_resultado_gei
    from formulario.models import FichaGEI

    ficha = (
        FichaGEI.objects.filter(estudiante=estudiante, curso=curso)
        .order_by("-fecha_update", "-id")
        .first()
    )
    if not ficha:
        logger.info(
            "Módulo %s completado sin FichaGEI para estudiante=%s curso=%s",
            modulo.numero,
            estudiante.pk,
            curso.pk,
        )
        return

    try:
        persistir_resultado_gei(ficha)
        texto = generar_mensaje_resultado_whatsapp(ficha)
        tel = (estudiante.telefono or "").strip()
        if not tel:
            logger.warning("Sin teléfono para enviar balance GEI estudiante_id=%s", estudiante.pk)
            return
        if not tel.startswith("+"):
            tel = f"+{tel}"

        from core.utils import enviar_whatsapp_twilio

        enviar_whatsapp_twilio(tel, texto)
    except Exception as e:
        logger.exception("Error enviando balance GEI por WhatsApp: %s", e)
