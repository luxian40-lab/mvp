"""Estado esperando_codigo_empleabilidad. Movido del cuerpo de _procesar_twilio_webhook_cuerpo sin cambios."""
import logging

from django.utils import timezone

from core.conversacion.contexto import Contexto, Respuesta

logger = logging.getLogger('core.views.webhook_twilio')


def manejar(contexto: Contexto) -> Respuesta:
    estudiante = contexto.estudiante
    msg_body = contexto.msg_body
    texto_respuesta = contexto.texto_respuesta
    from core.models import AliadoEmpleabilidad, MisionEmpleabilidad
    from core.gamificacion import PerfilGamificacion, Badge, BadgeEstudiante
    ctx_emp = estudiante.contexto_temporal or {}
    aliado_id = ctx_emp.get('aliado_empleabilidad_objetivo_id')
    mision_id = ctx_emp.get('mision_empleabilidad_id')
    aliado = None
    if aliado_id:
        aliado = AliadoEmpleabilidad.objects.filter(id=aliado_id, vacantes_activas=True).first()
    mision = None
    if mision_id:
        mision = MisionEmpleabilidad.objects.filter(id=mision_id, estudiante=estudiante).first()

    codigo_ingresado = msg_body.strip().lower()
    codigo_esperado = str(aliado.codigo_secreto).strip().lower() if aliado else ''
    if aliado and codigo_ingresado == codigo_esperado:
        perfil, _ = PerfilGamificacion.objects.get_or_create(estudiante=estudiante)
        puntos_cfg = int(getattr(estudiante.cliente, 'empleabilidad_puntos_validacion', 30) or 30)
        perfil.agregar_puntos(puntos_cfg, f"Radar Empleabilidad: {aliado.nombre_empresa}")
        badge = Badge.objects.filter(tipo='ESPECIAL', activo=True, nombre__icontains='emple').first()
        if badge:
            BadgeEstudiante.objects.get_or_create(estudiante=estudiante, badge=badge)

        if mision and mision.estado != 'completada':
            mision.estado = 'completada'
            mision.codigo_validado = True
            mision.puntos_otorgados = puntos_cfg
            mision.fecha_completada = timezone.now()
            mision.save(update_fields=['estado', 'codigo_validado', 'puntos_otorgados', 'fecha_completada'])

        try:
            from core.tasks import enviar_email_org_admin_async

            asunto = f"Match empleabilidad: {estudiante.nombre} - {aliado.nombre_empresa}"
            mensaje_html = (
                f"<p>El estudiante <strong>{estudiante.nombre}</strong> "
                f"(tel: {estudiante.telefono}) validó el código secreto de "
                f"<strong>{aliado.nombre_empresa}</strong>.</p>"
                f"<p>Iniciar contacto para proceso de contratación.</p>"
            )
            enviar_email_org_admin_async.delay(estudiante.id, asunto, mensaje_html)
        except Exception as e:
            logger.warning(f"⚠️ No se pudo encolar notificación de empleabilidad: {e}")

        ctx_emp['ultimo_match_empleabilidad_aliado_id'] = aliado.id
        ctx_emp['ultimo_match_empleabilidad_fecha'] = timezone.now().isoformat()
        estudiante.contexto_temporal = ctx_emp
        estudiante.estado_onboarding = 'curso_finalizado'
        estudiante.save(update_fields=['contexto_temporal', 'estado_onboarding'])
        texto_respuesta = (
            f"🏆 *¡Logro desbloqueado!*\n\n"
            f"Validaste el código de *{aliado.nombre_empresa}*.\n"
            "✅ Ya notificamos al equipo para iniciar el proceso de empleabilidad."
        )
        estudiante.estado_onboarding = 'curso_finalizado'
    elif codigo_ingresado in ('listo', 'continuar'):
        texto_respuesta = (
            "📍 Estás en el *radar de empleabilidad*.\n\n"
            "No uses *listo* aquí: envía el *código secreto* del punto "
            "(el que te indiquemos en la prueba / en la entrada)."
        )
        estudiante.estado_onboarding = 'esperando_codigo_empleabilidad'
    else:
        if mision and mision.estado == 'descubierta':
            mision.estado = 'reclamada'
            mision.fecha_reclamada = timezone.now()
            mision.save(update_fields=['estado', 'fecha_reclamada'])
        texto_respuesta = (
            "🔐 El código no coincide.\n\n"
            "Verifica el código secreto en la entrada de la empresa y vuelve a enviarlo."
        )
        estudiante.estado_onboarding = 'esperando_codigo_empleabilidad'
    estudiante.save(update_fields=['estado_onboarding'])
    return Respuesta(texto=texto_respuesta)
