"""CTA de avance por módulo: texto *listo* o plantilla Twilio con botón (por cliente)."""
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

# Fin de entrega de módulo (material listo para marcar avance).
CTX_FIN_ENTREGA_MODULO = 'fin_entrega_modulo'
# Paso intermedio dentro del mismo módulo — por ahora solo texto.
CTX_PASO_INTERMEDIO = 'paso_intermedio'
# Mensaje de drip «estamos preparando…» — nunca botón.
CTX_DRIP_BLOQUEO = 'drip_bloqueo'

TEXTO_CTA_LISTO_DEFAULT = (
    'Tómese su tiempo para ver el material. Mientras usted aprende, aquí iremos '
    'organizando los recursos del siguiente nivel. En cuanto termine, solo responda '
    '*listo* para continuar.'
)

TEXTO_DRIP_BLOQUEO_BOTON = (
    'Cuando llegue esa fecha, te enviaremos el siguiente módulo. '
    'No hace falta responder antes.'
)

TEXTO_DRIP_BLOQUEO_TEXTO = (
    'Cuando llegue esa fecha, responde *listo* y seguimos automáticamente.'
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


def resolver_cta_listo(
    estudiante: Estudiante | None,
    curso: Curso | None,
    contexto: str = CTX_FIN_ENTREGA_MODULO,
) -> str:
    """
    Fragmento para MULTI_MSG ([SEP]…) o cuerpo final.
    drip_bloqueo → siempre vacío (el texto va en format_mensaje_bloqueo_*).
    """
    if contexto == CTX_DRIP_BLOQUEO:
        return ''

    cliente = getattr(estudiante, 'cliente', None) if estudiante else None
    if curso and getattr(curso, 'cliente_id', None):
        cliente = curso.cliente or cliente

    modo = get_modo_avance_cliente(cliente)
    sid = _content_sid_boton(cliente)

    if contexto == CTX_PASO_INTERMEDIO or modo == MODO_AVANCE_TEXTO or not sid:
        if contexto == CTX_PASO_INTERMEDIO:
            from .module_steps import MSG_LISTO_CONTINUAR_EN_MODULO
            return MSG_LISTO_CONTINUAR_EN_MODULO
        return TEXTO_CTA_LISTO_DEFAULT

    marcador = _marcador_plantilla(sid)
    if modo == MODO_AVANCE_BOTON:
        return marcador
    return f'{TEXTO_CTA_LISTO_DEFAULT}[SEP]{marcador}'


def es_mensaje_drip_bloqueo(texto: str) -> bool:
    if not texto:
        return False
    t = texto.lower()
    return 'estamos preparando tu siguiente sesión' in t or 'próxima lección se desbloquea' in t


def adaptar_mensaje_drip_bloqueo(texto: str, estudiante: Estudiante | None) -> str:
    """En modo botón: quita «responde listo» del bloqueo drip (no reenviar botón ahí)."""
    if not texto or not estudiante:
        return texto
    cliente = getattr(estudiante, 'cliente', None)
    if not cliente_usa_boton_listo(cliente):
        return texto
    if 'responde *listo*' in texto.lower() or 'responde listo' in texto.lower():
        return texto.replace(
            'Cuando llegue esa fecha, responde *listo* y seguimos automáticamente.',
            TEXTO_DRIP_BLOQUEO_BOTON,
        )
    return texto


def texto_bloqueo_drip_cierre(cliente: Cliente | None) -> str:
    if cliente_usa_boton_listo(cliente):
        return TEXTO_DRIP_BLOQUEO_BOTON
    return TEXTO_DRIP_BLOQUEO_TEXTO
