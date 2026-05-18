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
    Respaldo: si se completó el módulo del balance (p. ej. 5) y NO hay formulario
    bloque balance activo, envía WhatsApp aquí. Si hay formulario balance, el envío
    ocurre al cerrar esa sesión en formulario.agent._cerrar_sesion.
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

    from django.db.models import Q

    from formulario.gei_flujos import es_formulario_balance_gei
    from formulario.models import FichaGEI, TipoFormulario

    estudiante = progreso.estudiante
    cliente_id = getattr(estudiante, "cliente_id", None)
    tf_qs = TipoFormulario.objects.filter(
        curso=curso,
        modulo=modulo,
        activo=True,
    )
    if cliente_id:
        tf_qs = tf_qs.filter(Q(cliente_id=cliente_id) | Q(cliente__isnull=True))
    else:
        tf_qs = tf_qs.filter(cliente__isnull=True)
    tf_balance = tf_qs.order_by("-cliente_id", "id").first()
    if tf_balance and es_formulario_balance_gei(tf_balance):
        logger.debug(
            "Balance GEI por WhatsApp diferido al formulario bloque balance (TF id=%s).",
            tf_balance.id,
        )
        return

    ficha = (
        FichaGEI.objects.filter(estudiante=estudiante, curso=curso)
        .order_by("-fecha_update", "-id")
        .first()
    )
    if not ficha:
        logger.info(
            "Módulo %s completado sin FichaGEI estudiante=%s curso=%s",
            modulo.numero,
            estudiante.pk,
            curso.pk,
        )
        return

    from formulario.whatsapp_gei import enviar_balance_gei_whatsapp

    enviar_balance_gei_whatsapp(ficha, estudiante)
