"""
Carrusel demo de programas (solo prospectos / números no guardados como Estudiante).

Ver docs/WHATSAPP_CARRUSEL_DEMO_PROGRAMAS.md

Por card (2 botones, mismo orden en todas):
  1) Ver descripción  → desc_<slug>
  2) Quiero demo / Solo info → in_riendas | info_<slug>
"""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)

KEYWORDS_CARRUSEL = frozenset({
    'programas',
    'programa',
    'catalogo',
    'catálogo',
    'cursos',
    'ver programas',
    'ver cursos',
    '4',
    '4️⃣',
})

# Tras descripción de Riendas: seguir o no
KEYWORDS_SEGUIR_RIENDAS = frozenset({
    'quiero demo',
    'quiero la demo',
    'si quiero',
    'sí quiero',
    'si, quiero',
    'sí, quiero',
    'seguir',
    'inscribirme demo',
    'in_riendas',
})
KEYWORDS_NO_SEGUIR = frozenset({
    'no gracias',
    'no, gracias',
    'solo mirar',
    'despues',
    'después',
})

DESC_AGROSAVIA = (
    "🌾 *Agrosavia · formación de campo*\n\n"
    "Así se ve un programa técnico en eki: lecciones cortas por WhatsApp, "
    "ejemplos de finca y un cierre práctico.\n\n"
    "⚠️ *Solo muestra* en esta demo: no abre inscripción.\n\n"
    "La demo real es *Tome las riendas de su dinero*. "
    "Escriba *programas* para volver al carrusel, o *riendas* para esa demo."
)

DESC_FEDEPALMA = (
    "🌴 *Fedepalma · buenas prácticas*\n\n"
    "Ejemplo de cómo eki lleva un programa sectorial: módulos claros, "
    "ritmo con *listo* y acompañamiento por chat.\n\n"
    "⚠️ *Solo muestra*: no inicia curso.\n\n"
    "Pruebe la demo *Tome las riendas* escribiendo *riendas*, "
    "o *programas* para el carrusel."
)

DESC_PROFAMILIA = (
    "💚 *Profamilia · bienestar*\n\n"
    "Ejemplo de programa de bienestar en el formato eki: mensajes cortos, "
    "tono cercano y avance paso a paso por WhatsApp.\n\n"
    "⚠️ *Solo muestra*: no abre inscripción.\n\n"
    "La demo activa es *Tome las riendas de su dinero* → escriba *riendas*."
)

DESC_EMPRENDIMIENTO = (
    "🌱 *Emprendimiento Agro Rural*\n\n"
    "Así se ve un programa eki para crear y fortalecer un negocio rural: "
    "ideas claras, pasos cortos por WhatsApp y foco en la finca.\n\n"
    "⚠️ *Solo muestra* en esta vitrina: no abre inscripción.\n\n"
    "La demo real es *Tome las riendas de su dinero* → *riendas*."
)

DESC_MAQUINARIA = (
    "🛠️ *Maquinaria y herramientas para el agro*\n\n"
    "Ejemplo de formación práctica eki: equipos, uso seguro y buenas "
    "prácticas en campo, en lecciones cortas por chat.\n\n"
    "⚠️ *Solo muestra*: no inicia curso.\n\n"
    "Pruebe la demo *Tome las riendas* → *riendas*."
)

DESC_COMERCIALIZACION = (
    "🛒 *Comercialización y ventas*\n\n"
    "Así enseña eki a llevar el producto al mercado: clientes, precio y "
    "ventas con mensajes accionables por WhatsApp.\n\n"
    "⚠️ *Solo muestra*: no abre inscripción.\n\n"
    "Demo activa: *Tome las riendas* → *riendas*."
)

DESC_AGRODIGITAL = (
    "📱 *Agricultura digital e IA para el campo*\n\n"
    "Vitrina de cómo eki acerca datos, apps e inteligencia artificial "
    "al productor, en formato móvil y paso a paso.\n\n"
    "⚠️ *Solo muestra*: no inicia curso.\n\n"
    "Para la demo real escriba *riendas*."
)

DESC_RIENDAS = (
    "💰 *Tome las riendas de su dinero* (demo eki)\n\n"
    "Ordene ingresos y gastos, tome decisiones simples y aplique lo aprendido "
    "en la semana — todo por WhatsApp, a su ritmo.\n\n"
    "Esta es la *única* tarjeta que abre contacto real de demo.\n\n"
    "✅ Si quiere seguir: escriba *quiero demo*\n"
    "👀 Si solo estaba mirando: escriba *no gracias*\n"
    "📚 Carrusel otra vez: *programas*"
)

TEXTO_CTA_RIENDAS = (
    "🚀 *¡Vamos con la demo!*\n\n"
    "*Tome las riendas de su dinero* — formación práctica eki por WhatsApp.\n\n"
    "Para que un asesor lo contacte:\n"
    "👉 Escriba *1* (eki para mi empresa) y luego su *correo*.\n\n"
    "O escriba *programas* si quiere ver el carrusel otra vez."
)

TEXTO_INFO_VITRINA = (
    "ℹ️ *Solo información*\n\n"
    "Esa tarjeta es una *muestra visual* de cómo se ven los programas en eki. "
    "No inscribe ni abre un curso.\n\n"
    "La demo que sí inicia contacto es *Tome las riendas de su dinero*.\n"
    "Escriba *riendas* o *programas*."
)

TEXTO_NO_SEGUIR = (
    "Perfecto, sin compromiso 🙂\n\n"
    "Cuando quiera, escriba *programas* para ver el carrusel "
    "o *riendas* si se anima a la demo de finanzas."
)

TEXTO_FALLBACK_LISTA = (
    "✨ *Así se aprende con eki*\n\n"
    "Deslice con la imaginación (el carrusel con fotos se activa "
    "cuando Meta apruebe la plantilla):\n\n"
    "🌾 Agrosavia — *Ver descripción* / Solo info\n"
    "🌴 Fedepalma — *Ver descripción* / Solo info\n"
    "💰 *eki · Riendas* — *Ver descripción* / *Quiero demo*\n"
    "💚 Profamilia — *Ver descripción* / Solo info\n\n"
    "Escriba *riendas* para la demo, *descripcion riendas* para leerla, "
    "o *1* si es empresa."
)

# Mapa payload → respuesta
_RESPUESTAS_PAYLOAD: dict[str, str] = {
    'desc_agrosavia': DESC_AGROSAVIA,
    'desc_fedepalma': DESC_FEDEPALMA,
    'desc_profamilia': DESC_PROFAMILIA,
    'desc_riendas': DESC_RIENDAS,
    'desc_emprendimiento': DESC_EMPRENDIMIENTO,
    'desc_maquinaria': DESC_MAQUINARIA,
    'desc_comercializacion': DESC_COMERCIALIZACION,
    'desc_agrodigital': DESC_AGRODIGITAL,
    'in_riendas': TEXTO_CTA_RIENDAS,
    'info_agrosavia': TEXTO_INFO_VITRINA,
    'info_fedepalma': TEXTO_INFO_VITRINA,
    'info_profamilia': TEXTO_INFO_VITRINA,
    'info_emprendimiento': TEXTO_INFO_VITRINA,
    'info_maquinaria': TEXTO_INFO_VITRINA,
    'info_comercializacion': TEXTO_INFO_VITRINA,
    'info_agrodigital': TEXTO_INFO_VITRINA,
    # Compat payloads v1 (un botón)
    'demo_riendas': TEXTO_CTA_RIENDAS,
    'demo_vitrina_agrosavia': DESC_AGROSAVIA,
    'demo_vitrina_fedepalma': DESC_FEDEPALMA,
    'demo_vitrina_profamilia': DESC_PROFAMILIA,
}


def demo_carousel_habilitado() -> bool:
    return bool(getattr(settings, 'EKI_DEMO_CAROUSEL_ENABLED', True))


def content_sid_carrusel() -> str:
    return str(getattr(settings, 'EKI_DEMO_CAROUSEL_CONTENT_SID', '') or '').strip()


def es_keyword_carrusel(texto: str) -> bool:
    t = (texto or '').strip().lower().replace('*', '').strip()
    return t in KEYWORDS_CARRUSEL


def es_payload_carrusel(payload: str) -> bool:
    p = (payload or '').strip()
    if p in _RESPUESTAS_PAYLOAD:
        return True
    if p.startswith(('desc_', 'info_', 'in_', 'demo_vitrina_', 'demo_')):
        return True
    return False


def respuesta_por_payload(payload: str) -> str:
    p = (payload or '').strip()
    if p in _RESPUESTAS_PAYLOAD:
        return _RESPUESTAS_PAYLOAD[p]
    if p.startswith('desc_') or p.startswith('demo_vitrina_'):
        return TEXTO_INFO_VITRINA
    if p.startswith('info_'):
        return TEXTO_INFO_VITRINA
    if p in {'in_riendas', 'demo_riendas'}:
        return TEXTO_CTA_RIENDAS
    return TEXTO_FALLBACK_LISTA


def respuesta_por_texto(texto: str) -> str | None:
    t = (texto or '').strip().lower().replace('*', '').strip()
    if t in KEYWORDS_SEGUIR_RIENDAS or t == 'riendas':
        return TEXTO_CTA_RIENDAS
    if t in KEYWORDS_NO_SEGUIR:
        return TEXTO_NO_SEGUIR
    if t in {
        'descripcion riendas',
        'descripción riendas',
        'ver descripcion riendas',
        'ver descripción riendas',
        'desc riendas',
    }:
        return DESC_RIENDAS
    if t in {'agrosavia', 'descripcion agrosavia', 'descripción agrosavia'}:
        return DESC_AGROSAVIA
    if t in {'fedepalma', 'descripcion fedepalma', 'descripción fedepalma'}:
        return DESC_FEDEPALMA
    if t in {'profamilia', 'descripcion profamilia', 'descripción profamilia'}:
        return DESC_PROFAMILIA
    # Títulos de botón que a veces llegan en Body
    if t == 'ver descripción' or t == 'ver descripcion':
        return None  # sin card id no sabemos cuál; pedir carrusel
    if t in {'quiero demo', 'solo info'}:
        return TEXTO_CTA_RIENDAS if 'demo' in t else TEXTO_INFO_VITRINA
    return None


def enviar_carrusel_demo(telefono: str) -> dict[str, Any]:
    """Envía plantilla carousel si hay Content SID; si no, lista en texto."""
    from core.whatsapp_service import enviar_template_twilio
    from core.utils import enviar_whatsapp_twilio

    sid = content_sid_carrusel()
    if sid.startswith('HX'):
        resultado = enviar_template_twilio(telefono, sid, variables=None)
        if resultado.get('success'):
            return resultado
        logger.warning(
            'Carrusel demo: falló envío HX=%s; fallback texto | %s',
            sid,
            resultado.get('response'),
        )
    return enviar_whatsapp_twilio(telefono, TEXTO_FALLBACK_LISTA)


def intentar_flujo_prospecto_carrusel(
    *,
    telefono: str,
    msg_from: str,
    msg_body: str,
    button_payload: str = '',
    solo_botones: bool = False,
) -> bool:
    """
    True si consumió el turno (envió respuesta y el caller debe return).

    Por defecto: prospectos (payloads + keywords *programas* / *4*).
    Con ``solo_botones=True``: también para Estudiante (taps del carrusel),
    sin robar *listo* ni el menú numérico del LMS.
    """
    if not demo_carousel_habilitado():
        return False

    payload = (button_payload or '').strip()
    if not payload:
        body_raw = (msg_body or '').strip()
        if es_payload_carrusel(body_raw):
            payload = body_raw

    if es_payload_carrusel(payload):
        from core.utils import enviar_whatsapp_twilio
        enviar_whatsapp_twilio(msg_from or telefono, respuesta_por_payload(payload))
        return True

    texto_card = respuesta_por_texto(msg_body)
    if texto_card:
        from core.utils import enviar_whatsapp_twilio
        enviar_whatsapp_twilio(msg_from or telefono, texto_card)
        return True

    if solo_botones:
        return False

    if es_keyword_carrusel(msg_body):
        enviar_carrusel_demo(msg_from or telefono)
        return True

    return False
