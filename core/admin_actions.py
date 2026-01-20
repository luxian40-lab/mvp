"""
Admin actions para enviar campañas con plantillas aprobadas
"""
from django.contrib import admin
from django.contrib import messages
from .enviar_plantillas import enviar_campana_con_plantilla


@admin.action(description='� Ejecutar campaña (envío directo)')
def enviar_campana_action(modeladmin, request, queryset):
    """
    Acción del admin para enviar campañas seleccionadas usando envío directo.
    Más simple y flexible que usar Content Templates.
    """
    if queryset.count() > 1:
        modeladmin.message_user(
            request,
            "⚠️ Solo puedes enviar una campaña a la vez",
            level=messages.WARNING
        )
        return

    campana = queryset.first()

    # Validar que tenga plantilla
    if not campana.plantilla:
        modeladmin.message_user(
            request,
            "❌ La campaña no tiene plantilla seleccionada.",
            level=messages.ERROR
        )
        return

    # Validar que tenga destinatarios
    if not campana.destinatarios.exists():
        modeladmin.message_user(
            request,
            "❌ La campaña no tiene destinatarios. Agrega estudiantes primero.",
            level=messages.ERROR
        )
        return

    # Enviar campaña usando envío directo
    from .services import ejecutar_campana_servicio

    try:
        resultado = ejecutar_campana_servicio(campana)

        if resultado['success']:
            modeladmin.message_user(
                request,
                f"✅ Campaña enviada: {resultado['enviados']} exitosos, "
                f"{resultado['fallidos']} fallidos de {resultado['total']} total",
                level=messages.SUCCESS
            )
        else:
            modeladmin.message_user(
                request,
                f"❌ Error ejecutando campaña: {resultado.get('error', 'Error desconocido')}",
                level=messages.ERROR
            )
    except Exception as e:
        modeladmin.message_user(
            request,
            f"❌ Error inesperado: {str(e)}",
            level=messages.ERROR
        )
            level=messages.SUCCESS
        )
    else:
        modeladmin.message_user(
            request,
            f"❌ Error al enviar campaña: {resultado.get('error', 'Error desconocido')}",
            level=messages.ERROR
        )
