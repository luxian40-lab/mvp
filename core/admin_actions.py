"""
Admin actions para enviar campañas con plantillas aprobadas
"""
from django.contrib import admin
from django.contrib import messages
from .enviar_plantillas import enviar_campana_con_plantilla


@admin.action(description='📤 Enviar campaña con plantilla aprobada')
def enviar_campana_action(modeladmin, request, queryset):
    """
    Acción del admin para enviar campañas seleccionadas usando plantillas aprobadas.
    """
    if queryset.count() > 1:
        modeladmin.message_user(
            request,
            "⚠️ Solo puedes enviar una campaña a la vez",
            level=messages.WARNING
        )
        return
    
    campana = queryset.first()
    
    # Validar que tenga plantilla con Content SID
    if not campana.plantilla.twilio_template_sid:
        modeladmin.message_user(
            request,
            f"❌ La plantilla '{campana.plantilla.nombre_interno}' no tiene Content SID configurado. "
            f"Debes crear y aprobar la plantilla en Twilio primero.",
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
    
    # Enviar campaña
    resultado = enviar_campana_con_plantilla(campana.id)
    
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
            f"❌ Error al enviar campaña: {resultado.get('error', 'Error desconocido')}",
            level=messages.ERROR
        )
