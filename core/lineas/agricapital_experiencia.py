"""Experiencia AgriCapital: dudas, copy en tú, voces y ritmo de burbujas.

Solo aplica si EKI_AGRICAPITAL_CLIENTE_ID coincide con el cliente.
Vacío u otro cliente = sin efecto.
"""
from __future__ import annotations

import re
import unicodedata

from core.lineas.registro_agricapital import es_cliente_agricapital

NOMBRE_FORMADOR = 'Formador'
NOMBRE_COMPANERO = 'Compañero'
DELAY_BURBUJA_SEG = 1

TEXTO_REINTENTO_RETO = (
    'Eso no cuenta como respuesta al reto, así que no recibe nota.\n\n'
    'Cuando puedas, escribe con tus palabras qué harías, o manda un audio '
    'o una foto de tu evidencia.\n\n'
    '_Si el problema es que no descarga o no ves una imagen, dilo y te ayudo '
    'sin calificar el reto._'
)

TEXTO_TIP_MEDIA = (
    'Si no descarga o no ves la imagen o el video, revisa tu señal y vuelve '
    'a tocar el archivo. Si sigue igual, escribe *ayuda* y te acompañamos.\n\n'
    'El curso no avanza con este mensaje: cuando quieras seguir, toca *Continuar*.'
)

TEXTO_NO_ENTENDI = (
    'No entendí. Si quieres avanzar de módulo, toca *Continuar*. '
    'Si necesitas ayuda, escribe *ayuda*.'
)

TEXTO_PUNTOS_INICIO = (
    '*Nuestra experiencia de formación funciona a través de puntos*\n\n'
    'A medida que avances en el curso, tendrás retos para aplicar lo aprendido.\n\n'
    '¡Vamos a aprender y avanzar juntos!'
)

TEXTO_COMIENZA_MODULO = '*Comenzamos con el primer módulo de tu curso...*'

TEXTO_DRIP_BLOQUEO = (
    '*¡Excelente energía!*\n\n'
    'Estamos preparando tu siguiente sesión; aún no enviamos el siguiente '
    'módulo para que puedas asimilar lo aprendido.\n\n'
    'Tu próxima lección se desbloquea el *{fecha}*.\n'
    'Mientras tanto, repasa el material del módulo que acabas de completar.\n\n'
    '{cierre}'
)

TEXTO_DRIP_CIERRE = 'Ese día escribe *continuar* para recibirlo.'
TEXTO_DRIP_CIERRE_AVISO = (
    'Ese día te avisamos por aquí; toca *Continuar* para recibirlo.'
)

TEXTO_OFERTA_CURSOS = 'Elige un curso. La clase sigue en este chat.'
TEXTO_SIN_CURSOS = (
    'Tu registro quedó. Esta organización todavía no tiene cursos en el enlace.'
)
TEXTO_INSCRITO = 'Quedaste en {nombre}.'
TEXTO_OTRO_CURSO = 'Ese curso no está en el enlace de tu organización.'

PROMPT_COMPANERO = f"""Eres {NOMBRE_COMPANERO}, el compañero de estudio de AgriCapital en eki.
TRATO DE TÚ siempre ("tú", "tu", "te").
Tu rol: ayudar a repasar el dominio del curso antes del reto del Formador.

REGLAS:
1. TRATO DE TÚ siempre.
2. Máximo 120 palabras. Responde con sustancia: qué, cómo y un ejemplo claro.
3. Ancla la respuesta al DOMINIO DEL CURSO (nombre, descripción y módulos).
4. Usa el contexto del curso. No inventes números ni protocolos ajenos.
5. PROHIBIDO religión, política, fútbol u otros temas externos al curso.
6. PROHIBIDO usar emojis.
7. NO te niegues a responder una pregunta del dominio del curso.
8. NO hagas preguntas de seguimiento ni invites a seguir conversando.
9. Tu nombre es {NOMBRE_COMPANERO}; no uses otro alias (ni copiloto, ni asesor)."""

_NO_CALIFICABLE_EXACTAS = frozenset({
    'ayuda',
    'soporte',
    'ticket',
    'help',
    'no',
    'si',
    'sí',
    'ok',
    'okay',
    'vale',
    'bien',
    'malo',
    'gracias',
    'no entendi',
    'no entendí',
    'no entiendo',
    'no descarga',
    'no se descarga',
    'no puedo descargar',
    'no puedo ver la imagen',
    'no veo la imagen',
    'no abre la imagen',
    'no puedo ver el video',
    'no veo el video',
    'no abre el video',
    'no me llega la imagen',
    'no me llega el video',
    'no carga la imagen',
    'no carga el video',
})

# Misma regla, trato de usted (Lhaura y resto). AgriCapital sigue en tú.
TEXTO_REINTENTO_RETO_USTED = (
    'Eso no cuenta como respuesta al reto, así que no recibe nota.\n\n'
    'Cuando pueda, escriba con sus palabras qué haría, o mande un audio '
    'o una foto de su evidencia.\n\n'
    '_Si el problema es que no descarga o no ve una imagen, dígalo y le ayudamos '
    'sin calificar el reto._'
)

def _norm(texto: str) -> str:
    t = (texto or '').strip().lower()
    t = ''.join(
        c for c in unicodedata.normalize('NFD', t) if unicodedata.category(c) != 'Mn'
    )
    t = re.sub(r'\s+', ' ', t)
    return t.strip(' .!?,;:')


def estudiante_es_agricapital(estudiante) -> bool:
    return es_cliente_agricapital(getattr(estudiante, 'cliente_id', None))


def cliente_es_agricapital(cliente) -> bool:
    if cliente is None:
        return False
    return es_cliente_agricapital(getattr(cliente, 'pk', None))


def curso_es_agricapital(curso) -> bool:
    if curso is None:
        return False
    return es_cliente_agricapital(getattr(curso, 'cliente_id', None))


def es_duda_media_agricapital(mensaje: str) -> bool:
    t = _norm(mensaje)
    if not t or len(t) > 120:
        return False
    if t in _NO_CALIFICABLE_EXACTAS and any(
        p in t for p in ('descarg', 'imagen', 'video', 'carga', 'abre', 'veo', 'ver')
    ):
        return True
    if 'descarg' in t and any(p in t for p in ('no', 'puedo', 'falla')):
        return True
    if ('imagen' in t or 'video' in t or 'foto' in t or 'audio' in t) and any(
        p in t
        for p in (
            'no puedo ver',
            'no veo',
            'no abre',
            'no carga',
            'no llega',
            'no me llega',
            'no descarga',
            'no se ve',
        )
    ):
        return True
    return False


def es_mensaje_no_calificable_reto(mensaje: str) -> bool:
    t = _norm(mensaje)
    if not t:
        return False
    if t in _NO_CALIFICABLE_EXACTAS:
        return True
    if t.startswith('ayuda ') or t.startswith('necesito ayuda'):
        return True
    if es_duda_media_agricapital(mensaje):
        return True
    if 'no entendi' in t or 'no entiend' in t:
        return True
    return False


def texto_reintento_reto_agricapital() -> str:
    return TEXTO_REINTENTO_RETO


def texto_reintento_reto(estudiante=None) -> str:
    """Copy de reintento: AgriCapital en tú; el resto en usted."""
    if estudiante is not None and estudiante_es_agricapital(estudiante):
        return TEXTO_REINTENTO_RETO
    return TEXTO_REINTENTO_RETO_USTED


def texto_tip_media_agricapital() -> str:
    return TEXTO_TIP_MEDIA


def texto_no_entendi_agricapital() -> str:
    from core.avance_whatsapp import MARCADOR_BOTON_CONTINUEMOS

    return TEXTO_NO_ENTENDI + '\n\n' + MARCADOR_BOTON_CONTINUEMOS


def presentacion_inicio_agricapital(curso_nombre: str, estudiante_nombre: str) -> tuple[str, str]:
    """S4: solo Formador + Compañero, en tú."""
    from core.agentes_whatsapp import mensaje_con_titular_agente

    nombre = (estudiante_nombre or 'Estudiante').strip() or 'Estudiante'
    curso = (curso_nombre or 'tu curso').strip() or 'tu curso'
    cuerpo_fac = (
        f'Hola {nombre}. Soy el Formador.\n\n'
        f'Seré tu formador en el curso *{curso}*. '
        f'Te plantearé retos prácticos para que apliques lo aprendido.'
    )
    cuerpo_asist = (
        f'Y yo soy el Compañero.\n\n'
        f'Estaré pendiente de ti en este proceso. '
        f'Si tienes dudas antes de los retos, te ayudo a repasar.'
    )
    return (
        mensaje_con_titular_agente(NOMBRE_FORMADOR, cuerpo_fac),
        mensaje_con_titular_agente(NOMBRE_COMPANERO, cuerpo_asist),
    )


def prompt_companero_agricapital() -> str:
    return PROMPT_COMPANERO


def texto_bloqueo_drip_agricapital(fecha_txt: str, *, con_aviso: bool = False) -> str:
    cierre = TEXTO_DRIP_CIERRE_AVISO if con_aviso else TEXTO_DRIP_CIERRE
    return TEXTO_DRIP_BLOQUEO.format(fecha=fecha_txt, cierre=cierre)


def _es_solo_pausa(parte: str) -> bool:
    from core.conversacion.multimsg import DELAY

    t = (parte or '').strip()
    if not t.startswith(DELAY) or not t.endswith(']'):
        return False
    medio = t[len(DELAY):-1]
    return medio.isdigit()


def _marca_pausa(segundos: int) -> str:
    from core.conversacion.multimsg import DELAY

    return f'{DELAY}{int(segundos)}]'


def con_pausas_entre_burbujas(texto: str, *, segundos: int = DELAY_BURBUJA_SEG) -> str:
    """S6: inserta pausa entre partes de un MULTI_MSG si aún no hay."""
    from core.conversacion.multimsg import MULTI_MSG, SEP, partes_multimsg

    bruto = texto or ''
    if not bruto.startswith(MULTI_MSG):
        return bruto
    partes = [p.strip() for p in partes_multimsg(bruto) if (p or '').strip()]
    if len(partes) < 2:
        return bruto
    out: list[str] = []
    for parte in partes:
        if _es_solo_pausa(parte):
            if out and _es_solo_pausa(out[-1]):
                out[-1] = parte
            else:
                out.append(parte)
            continue
        if out and not _es_solo_pausa(out[-1]):
            out.append(_marca_pausa(segundos))
        out.append(parte)
    return MULTI_MSG + SEP.join(out)


def preparar_salida_agricapital(estudiante, texto: str) -> str:
    """Aplica ritmo de burbujas solo si el estudiante es AgriCapital."""
    if not estudiante_es_agricapital(estudiante):
        return texto or ''
    return con_pausas_entre_burbujas(texto or '')
