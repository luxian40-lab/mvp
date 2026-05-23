"""Envío de mensajes push (recordatorios curso vía Twilio)."""
from __future__ import annotations

import logging

from django.db.models import Count, Q

from core.models import Estudiante, ProgresoEstudiante
from core.models_extras import EnvioMensajePush, GrupoEstudiantes, MensajePush

logger = logging.getLogger(__name__)


def resolver_audiencia(mensaje: MensajePush, grupo: GrupoEstudiantes | None = None):
    """Estudiantes destino según cliente, curso, tipo y grupo opcional."""
    qs = Estudiante.objects.filter(activo=True)
    if mensaje.cliente_id:
        qs = qs.filter(cliente_id=mensaje.cliente_id)
    if grupo:
        qs = qs.filter(grupos=grupo)
    if mensaje.tipo == 'recordatorio_inscripcion' and mensaje.curso_id:
        qs = qs.filter(progresos__curso_id=mensaje.curso_id, progresos__completado=False)
        qs = qs.annotate(
            n_mods=Count('progresos__modulos_completados', filter=Q(progresos__curso_id=mensaje.curso_id)),
        ).filter(n_mods=0)
    elif mensaje.curso_id:
        qs = qs.filter(progresos__curso_id=mensaje.curso_id, progresos__completado=False).distinct()
    return qs.select_related('cliente')


def enviar_mensaje_push_a_estudiante(mensaje: MensajePush, estudiante: Estudiante) -> dict:
    """Envía un push; no altera onboarding ni reinicia curso."""
    from core.enviar_plantillas import enviar_plantilla_twilio
    from core.utils import enviar_whatsapp_twilio

    if not estudiante.telefono:
        return {'success': False, 'error': 'Sin teléfono'}

    progreso = None
    curso = mensaje.curso
    if curso:
        progreso = ProgresoEstudiante.objects.filter(estudiante=estudiante, curso=curso).first()
    texto = mensaje.render_texto(estudiante, curso=curso)
    sid = (mensaje.twilio_content_sid or '').strip()
    if not sid and mensaje.plantilla_id:
        sid = (getattr(mensaje.plantilla, 'twilio_template_sid', None) or '').strip()

    if sid:
        resultado = enviar_plantilla_twilio(
            estudiante.telefono,
            sid,
            variables={'1': estudiante.nombre or 'estudiante', '2': curso.nombre if curso else 'curso'},
        )
    else:
        resultado = enviar_whatsapp_twilio(estudiante.telefono, texto)

    EnvioMensajePush.objects.create(
        mensaje_push=mensaje,
        estudiante=estudiante,
        telefono=estudiante.telefono,
        exito=bool(resultado.get('success')),
        detalle=(resultado.get('error') or resultado.get('mensaje_id') or '')[:255],
    )
    if resultado.get('success') and progreso:
        ctx = estudiante.contexto_temporal or {}
        ctx['ultimo_push_curso_id'] = progreso.curso_id
        estudiante.contexto_temporal = ctx
        estudiante.save(update_fields=['contexto_temporal'])
    return resultado


def enviar_mensaje_push_masivo(mensaje: MensajePush, grupo=None) -> dict:
    enviados = errores = 0
    for est in resolver_audiencia(mensaje, grupo=grupo):
        r = enviar_mensaje_push_a_estudiante(mensaje, est)
        if r.get('success'):
            enviados += 1
        else:
            errores += 1
    logger.info('[Push] %s: enviados=%s errores=%s', mensaje.nombre, enviados, errores)
    return {'enviados': enviados, 'errores': errores}
