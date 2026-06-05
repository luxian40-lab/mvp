"""Enviar respuesta PQRS al estudiante por WhatsApp (admin y portal)."""
from __future__ import annotations

from django.utils import timezone


def _primer_nombre(nombre_estudiante: str) -> str:
    return (nombre_estudiante or '').strip().split()[0] or ''


def _respuesta_ya_saluda(texto: str) -> bool:
    inicio = texto.lower()[:24]
    return inicio.startswith(
        ('hola', 'buenos', 'buenas', 'hey', 'hi ', 'qué tal', 'que tal', 'buen día', 'buen dia')
    )


def mensaje_whatsapp_pqrs(nombre_estudiante: str, respuesta: str) -> str:
    """Arma el WhatsApp: el texto del operador manda; solo añade saludo breve si hace falta."""
    texto = (respuesta or '').strip()
    if not texto:
        return ''
    if _respuesta_ya_saluda(texto):
        return texto
    nombre = _primer_nombre(nombre_estudiante)
    if nombre:
        return f'Hola {nombre},\n\n{texto}'
    return texto


def aplicar_respuesta_pqrs(
    solicitud,
    respuesta_text: str,
    user=None,
    *,
    enviar_whatsapp: bool = True,
) -> tuple[bool, str | None]:
    """
    Guarda la respuesta y opcionalmente la envía por WhatsApp.
    Retorna (éxito, mensaje_error).
    """
    texto = (respuesta_text or '').strip()
    if not texto:
        return False, 'Escribe una respuesta antes de enviar.'

    if enviar_whatsapp:
        from core.utils import enviar_whatsapp_twilio

        est = solicitud.estudiante
        msg = mensaje_whatsapp_pqrs(est.nombre, texto)
        resultado = enviar_whatsapp_twilio(
            est.telefono,
            msg,
            canal_evento='pqrs',
            agente_evento=user.username if user else 'admin',
        )
        if not resultado.get('success'):
            detalle = resultado.get('response') or 'Error desconocido'
            return False, f'No se pudo enviar por WhatsApp: {detalle}'

    ahora = timezone.now()
    solicitud.respuesta = texto
    solicitud.respuesta_portal = texto
    solicitud.fecha_respuesta = ahora
    solicitud.fecha_resolucion = ahora
    if not solicitud.fecha_atencion:
        solicitud.fecha_atencion = ahora
    if user is not None:
        solicitud.respondido_por = user
        solicitud.atendido_por = user.get_full_name() or user.username
    solicitud.estado = 'resuelta'
    solicitud.save()
    return True, None
