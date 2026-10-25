"""CTA de avance: botón de respuesta «Continuemos» (Meta en sesión, plantilla en Twilio)."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import Cliente, Curso, Estudiante

MODO_AVANCE_TEXTO = 'texto'
MODO_AVANCE_BOTON = 'boton'
MODO_AVANCE_AMBOS = 'ambos'

MODO_AVANCE_CHOICES = (
    (MODO_AVANCE_TEXTO, 'Solo escribir listo / continuar'),
    (MODO_AVANCE_BOTON, 'Solo botón WhatsApp (plantilla)'),
    (MODO_AVANCE_AMBOS, 'Texto y botón'),
)

# Id y título del botón. El id entra al curso como si la persona hubiera seguido.
BOTON_CONTINUEMOS_ID = 'continuemos'
BOTON_CONTINUEMOS_TITULO = 'Continuar'
MARCADOR_BOTON_CONTINUEMOS = '[SEND_BUTTON:continuemos]'
# WhatsApp exige cuerpo en un mensaje con botones.
FRASE_PULSE_CONTINUAR = 'Pulse continuar, para seguir aprendiendo.'
CUERPO_BOTON_CONTINUEMOS = FRASE_PULSE_CONTINUAR

# Fin de entrega de módulo (material listo para marcar avance).
CTX_FIN_ENTREGA_MODULO = 'fin_entrega_modulo'
# Paso intermedio dentro del mismo módulo — por ahora solo texto.
CTX_PASO_INTERMEDIO = 'paso_intermedio'
# Mensaje de drip «estamos preparando…» — nunca botón.
CTX_DRIP_BLOQUEO = 'drip_bloqueo'

TEXTO_CTA_LISTO_DEFAULT = CUERPO_BOTON_CONTINUEMOS

TEXTO_DRIP_BLOQUEO_BOTON = (
    'Cuando llegue esa fecha, te enviaremos el siguiente módulo. '
    'No hace falta responder antes.'
)

TEXTO_DRIP_BLOQUEO_TEXTO = TEXTO_DRIP_BLOQUEO_BOTON

# La respuesta por defecto del cuerpo del webhook; la rama del examen la compara para saber si debe pisarla.
TEXTO_NO_ENTENDI = (
    "No entendí. Si quiere avanzar de módulo, pulse continuar, para seguir aprendiendo. "
    "Si necesitas ayuda, escribe *ayuda*.\n\n" + MARCADOR_BOTON_CONTINUEMOS
)

# Misma plantilla que core.whatsapp_service (evita import circular en tests).
SID_BOTON_LISTO_DEFAULT = 'HX33af3a0f2bb63715e03965c2bd642285'


def get_modo_avance_cliente(cliente: Cliente | None) -> str:
    if not cliente:
        return MODO_AVANCE_TEXTO
    modo = (getattr(cliente, 'modo_avance_modulo', None) or MODO_AVANCE_TEXTO).strip()
    if modo not in {MODO_AVANCE_TEXTO, MODO_AVANCE_BOTON, MODO_AVANCE_AMBOS}:
        return MODO_AVANCE_TEXTO
    return modo


def _content_sid_boton(cliente: Cliente | None) -> str:
    if not cliente:
        return ''
    sid = (getattr(cliente, 'content_sid_boton_listo', None) or '').strip()
    if sid:
        return sid
    return SID_BOTON_LISTO_DEFAULT


def cliente_usa_boton_listo(cliente: Cliente | None) -> bool:
    modo = get_modo_avance_cliente(cliente)
    if modo == MODO_AVANCE_TEXTO:
        return False
    return bool(_content_sid_boton(cliente))


def _marcador_plantilla(sid: str) -> str:
    return f'[SEND_TEMPLATE:{sid}]'


def con_boton_continuemos(texto: str = '') -> str:
    """Pega el marcador del botón al final. El envío lo convierte en botón."""
    base = (texto or '').strip()
    if MARCADOR_BOTON_CONTINUEMOS in base:
        return base
    if not base:
        return MARCADOR_BOTON_CONTINUEMOS
    return f'{base}\n\n{MARCADOR_BOTON_CONTINUEMOS}'


def separar_boton_continuemos(texto: str) -> tuple[str, bool]:
    """(cuerpo sin marcador, True si había botón). Cuerpo vacío → frase corta."""
    bruto = str(texto or '')
    if MARCADOR_BOTON_CONTINUEMOS not in bruto:
        return bruto, False
    cuerpo = bruto.replace(MARCADOR_BOTON_CONTINUEMOS, '').strip()
    return (cuerpo or CUERPO_BOTON_CONTINUEMOS), True


def resolver_cta_listo(
    estudiante: Estudiante | None,
    curso: Curso | None,
    contexto: str = CTX_FIN_ENTREGA_MODULO,
) -> str:
    """
    Fragmento para MULTI_MSG ([SEP]…) o cuerpo final.
    Entre secciones y al cerrar el módulo: solo el botón Continuemos.
    drip_bloqueo → vacío (ahí no se pide avanzar).
    """
    del estudiante, curso
    if contexto == CTX_DRIP_BLOQUEO:
        return ''
    return MARCADOR_BOTON_CONTINUEMOS


def es_mensaje_drip_bloqueo(texto: str) -> bool:
    if not texto:
        return False
    t = texto.lower()
    return 'estamos preparando tu siguiente sesión' in t or 'próxima lección se desbloquea' in t


def sid_plantilla_continuemos(cliente: Cliente | None = None) -> str:
    """Plantilla Twilio del botón. Setting o SID del cliente; si no, la global."""
    from django.conf import settings

    explicito = (getattr(settings, 'EKI_TWILIO_SID_BOTON_CONTINUEMOS', '') or '').strip()
    if explicito:
        return explicito
    if cliente:
        propio = (getattr(cliente, 'content_sid_boton_listo', None) or '').strip()
        if propio:
            return propio
    return SID_BOTON_LISTO_DEFAULT


def adaptar_mensaje_drip_bloqueo(texto: str, estudiante: Estudiante | None) -> str:
    """El drip no pide avanzar: quita «responde listo» si algún texto viejo lo trae."""
    del estudiante
    if not texto:
        return texto
    if 'responde *listo*' in texto.lower() or 'responde listo' in texto.lower():
        return texto.replace(
            'Cuando llegue esa fecha, responde *listo* y seguimos automáticamente.',
            TEXTO_DRIP_BLOQUEO_BOTON,
        )
    return texto


def texto_bloqueo_drip_cierre(cliente: Cliente | None) -> str:
    del cliente
    return TEXTO_DRIP_BLOQUEO_BOTON
