"""Ficha del negocio: tres preguntas de a una, después de ayudar.

Una por conversación (no más de una cada 20 horas), tres en total, ninguna se
repite y todas se saltan con *seguir*. Fuera del ciclo de imports: dice qué
preguntar y guarda la respuesta; quien llama manda el mensaje.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.db import IntegrityError
from django.utils import timezone

CAMPOS = ('dedica', 'etapa', 'equipo')
HORAS_ENTRE_PREGUNTAS = 20
HORAS_PARA_RESPONDER = 24
AGENTE_FICHA = 'sandbox_ficha'

GRACIAS = 'Gracias, ya lo tengo en cuenta. Siga con su pregunta cuando quiera.'
SALTADA = 'Listo, seguimos. Escriba su pregunta cuando quiera.'

_PREGUNTAS = {
    'dedica': (
        'Para ayudarle mejor la próxima vez: ¿a qué se dedica? '
        'Cuénteme qué cultiva, qué produce o qué vende.',
        (),
    ),
    'etapa': (
        '¿Cómo va su negocio hoy?',
        (
            ('ficha_etapa_empezando', 'Apenas empezando'),
            ('ficha_etapa_vende', 'Ya vendo'),
            ('ficha_etapa_crecer', 'Quiero crecer'),
        ),
    ),
    'equipo': (
        '¿Con quién trabaja?',
        (
            ('ficha_equipo_solo', 'Solo'),
            ('ficha_equipo_familia', 'Con mi familia'),
            ('ficha_equipo_trabajadores', 'Con trabajadores'),
        ),
    ),
}
_VALORES = {
    'etapa': {
        'ficha_etapa_empezando': 'empezando',
        'apenas empezando': 'empezando',
        'empezando': 'empezando',
        'ficha_etapa_vende': 'vende',
        'ya vendo': 'vende',
        'vendo': 'vende',
        'ficha_etapa_crecer': 'crecer',
        'quiero crecer': 'crecer',
        'crecer': 'crecer',
    },
    'equipo': {
        'ficha_equipo_solo': 'solo',
        'solo': 'solo',
        'ficha_equipo_familia': 'familia',
        'con mi familia': 'familia',
        'con la familia': 'familia',
        'familia': 'familia',
        'ficha_equipo_trabajadores': 'trabajadores',
        'con trabajadores': 'trabajadores',
        'trabajadores': 'trabajadores',
    },
}
_SALTAR = frozenset({'seguir', 'saltar', 'omitir'})
_SALIDAS = frozenset({
    'menu', 'menú', 'inicio', 'start', 'hola', 'hi', 'hey', 'buenas', 'buen día', 'buenos días', 'reiniciar',
})
_INICIOS_DE_PREGUNTA = (
    'como ', 'cómo ', 'que ', 'qué ', 'por que', 'por qué', 'porque ', 'cual', 'cuál', 'cuanto', 'cuánto',
    'donde', 'dónde', 'cuando ', 'cuándo', 'necesito', 'quiero saber', 'ayuda', 'me ayuda', 'puedo ', 'debo ',
)


def _parece_pregunta(t: str) -> bool:
    return '?' in t or '¿' in t or t.startswith(_INICIOS_DE_PREGUNTA)


@dataclass(frozen=True)
class Pregunta:
    campo: str
    texto: str
    botones: tuple[tuple[str, str], ...]

    @property
    def mensaje(self) -> str:
        pie = '_*seguir* para saltar._' if self.botones else '_Puede responder con un audio. *seguir* para saltar._'
        return f'{self.texto}\n\n{pie}'

    @property
    def mensaje_sin_botones(self) -> str:
        if not self.botones:
            return self.mensaje
        titulos = [titulo for _id, titulo in self.botones]
        opciones = f"{', '.join(titulos[:-1])} o {titulos[-1]}"
        return f'{self.texto}\n\nResponda: {opciones}.\n\n_*seguir* para saltar._'


def _hechas(ficha) -> set[str]:
    return {campo for campo in (ficha.preguntadas or '').split(',') if campo}


def siguiente_pregunta(telefono: str) -> Pregunta | None:
    """La próxima pregunta que toca, o None: ya se hicieron, ya respondió o se preguntó hace poco."""
    from core.models import FichaNegocio

    ficha = FichaNegocio.objects.filter(telefono=telefono).first()
    hechas: set[str] = set()
    if ficha is not None:
        reciente = timezone.now() - timedelta(hours=HORAS_ENTRE_PREGUNTAS)
        if ficha.pendiente_desde is not None and ficha.pendiente_desde > reciente:
            return None
        hechas = _hechas(ficha)
    for campo in CAMPOS:
        if campo in hechas or (ficha is not None and getattr(ficha, campo)):
            continue
        texto, botones = _PREGUNTAS[campo]
        return Pregunta(campo, texto, botones)
    return None


def marcar_preguntada(telefono: str, campo: str) -> None:
    from core.models import FichaNegocio

    try:
        ficha, _ = FichaNegocio.objects.get_or_create(telefono=telefono)
    except IntegrityError:
        ficha = FichaNegocio.objects.get(telefono=telefono)
    hechas = _hechas(ficha) | {campo}
    ficha.preguntadas = ','.join(c for c in CAMPOS if c in hechas)
    ficha.pendiente = campo
    ficha.pendiente_desde = timezone.now()
    ficha.save(update_fields=['preguntadas', 'pendiente', 'pendiente_desde', 'actualizada_en'])


def _cerrar(ficha, *, saltada: bool) -> None:
    ficha.pendiente = ''
    campos = ['pendiente', 'actualizada_en']
    if saltada:
        ficha.saltadas += 1
        campos.append('saltadas')
    ficha.save(update_fields=campos)


def _guardar(ficha, campo: str, valor: str) -> None:
    setattr(ficha, campo, valor)
    ficha.pendiente = ''
    ficha.save(update_fields=[campo, 'pendiente', 'actualizada_en'])


def responder(telefono: str, texto: str) -> str | None:
    """Lo que se le contesta si el mensaje era la respuesta a la ficha. None: el mensaje sigue su camino."""
    from core.conocimiento_agentes import _sin_datos_personales
    from core.models import FichaNegocio

    crudo = ' '.join((texto or '').split())
    t = crudo.lower()
    if not t:
        return None
    ficha = FichaNegocio.objects.filter(telefono=telefono).first()
    if ficha is None:
        return None
    if t.startswith('ficha_'):
        for campo, valores in _VALORES.items():
            if t in valores:
                _guardar(ficha, campo, valores[t])
                return GRACIAS
        return None
    campo = ficha.pendiente
    if not campo:
        return None
    vencida = timezone.now() - timedelta(hours=HORAS_PARA_RESPONDER)
    if ficha.pendiente_desde is None or ficha.pendiente_desde < vencida:
        _cerrar(ficha, saltada=False)
        return None
    if t in _SALTAR:
        _cerrar(ficha, saltada=True)
        return SALTADA
    if t in _SALIDAS:
        _cerrar(ficha, saltada=True)
        return None
    if campo == 'dedica':
        if _parece_pregunta(t):
            _cerrar(ficha, saltada=True)
            return None
        _guardar(ficha, 'dedica', _sin_datos_personales(crudo)[:200])
        return GRACIAS
    valor = _VALORES.get(campo, {}).get(t.rstrip('.!'))
    if valor is None:
        _cerrar(ficha, saltada=True)
        return None
    _guardar(ficha, campo, valor)
    return GRACIAS
