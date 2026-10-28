"""Resolución de perfil de facilitador (Claudia vs tecnicoagro). Claudia no se elimina."""
from __future__ import annotations

from typing import TYPE_CHECKING

from django.conf import settings

from core.prompts_tecnicoagro import (
    NOMBRE_DEFAULT_TECNICOAGRO,
    PERFIL_CLAUDIA,
    PERFIL_TECNICOAGRO,
    system_prompt_evaluacion_tecnicoagro,
    system_prompt_reto_tecnicoagro,
)

if TYPE_CHECKING:
    from core.models import Curso


def resolver_perfil_facilitador(curso: Curso | None) -> str:
    """Curso override > Cliente > Claudia."""
    if curso is None:
        return PERFIL_CLAUDIA
    propio = (getattr(curso, 'perfil_facilitador', None) or '').strip()
    if propio in (PERFIL_CLAUDIA, PERFIL_TECNICOAGRO):
        return propio
    cliente = getattr(curso, 'cliente', None)
    if cliente is not None:
        cli = (getattr(cliente, 'perfil_facilitador', None) or '').strip()
        if cli in (PERFIL_CLAUDIA, PERFIL_TECNICOAGRO):
            return cli
    return PERFIL_CLAUDIA


def es_perfil_tecnicoagro(curso: Curso | None) -> bool:
    return resolver_perfil_facilitador(curso) == PERFIL_TECNICOAGRO


CONTEXTO_RURAL = 'rural'
CONTEXTO_URBANO = 'urbano'
CONTEXTO_MIXTO = 'mixto'
FRASE_CONTEXTO = {
    CONTEXTO_RURAL: (
        'Participantes rurales: use ejemplos de finca, vereda, cosecha, animales o mercado campesino, '
        'según el tema del curso.'
    ),
    CONTEXTO_URBANO: (
        'Participantes urbanos: use ejemplos de negocio, tienda, emprendimiento, clientes y redes sociales. '
        'No hable de fincas, cultivos ni animales.'
    ),
    CONTEXTO_MIXTO: (
        'Participantes de campo y de ciudad: use ejemplos del tema del curso sin asumir que tienen finca '
        'ni que viven en la ciudad.'
    ),
}
# Frases rurales fijas de los textos generales del Formador y el Compañero, con su versión neutra.
_RURAL_FIJO = (
    (
        '(finanzas del hogar, emprendimiento rural, agricultura, otro — según ese contexto, sin inventar otro dominio)',
        '(según ese contexto, sin inventar otro dominio)',
    ),
    ('cercano al contexto rural/urbano que corresponda al curso', 'cercano al contexto de los participantes'),
    ('un ejemplo de campo', 'un ejemplo de su contexto'),
    ('fuentes AGROSAVIA/web del contexto', 'fuentes del contexto'),
    ('pensando en campesinos y emprendedores rurales de Colombia', 'pensando en los participantes del curso'),
    ('para ruralidad colombiana', 'para los participantes del curso'),
)


def resolver_contexto_participantes(curso: Curso | None) -> str:
    """Curso > Cliente > mixto."""
    validos = (CONTEXTO_RURAL, CONTEXTO_URBANO, CONTEXTO_MIXTO)
    if curso is None:
        return CONTEXTO_MIXTO
    propio = (getattr(curso, 'contexto_participantes', None) or '').strip()
    if propio in validos:
        return propio
    cliente = getattr(curso, 'cliente', None)
    del_cliente = (getattr(cliente, 'contexto_participantes', None) or '').strip() if cliente else ''
    return del_cliente if del_cliente in validos else CONTEXTO_MIXTO


def _contexto_aplica(curso: Curso | None) -> bool:
    return bool(getattr(settings, 'EKI_CONTEXTO_PARTICIPANTES_ENABLED', False)) and not es_perfil_tecnicoagro(curso)


def sin_rural_fijo(texto: str, curso: Curso | None) -> str:
    if not _contexto_aplica(curso):
        return texto
    for fijo, neutro in _RURAL_FIJO:
        texto = texto.replace(fijo, neutro)
    return texto


def ajustar_prompt_contexto(prompt: str, curso: Curso | None) -> str:
    """Con el flag: sin lo rural fijo y con a quién va dirigido el curso. Apagado o tecnicoagro, igual."""
    if not _contexto_aplica(curso):
        return prompt
    frase = FRASE_CONTEXTO[resolver_contexto_participantes(curso)]
    return f"{sin_rural_fijo(prompt, curso)}\n\nCONTEXTO DE LOS PARTICIPANTES: {frase}"


NOMBRE_FORMADOR = 'Formador'
NOMBRE_COMPANERO = 'Compañero'
_NOMBRES_DE_CURSO = frozenset({
    '', 'formador', 'compañero', 'companero', 'claudia', 'dario', 'darío',
    'geronimo', 'gerónimo', 'maria', 'maría',
})


def _nombre_propio_tecnico(valor: str) -> str:
    limpio = (valor or '').strip()
    if limpio.casefold() in _NOMBRES_DE_CURSO:
        return ''
    return limpio


def nombre_display_facilitador(curso: Curso | None, fallback: str = NOMBRE_FORMADOR) -> str:
    """Nombre visible en WhatsApp. En los cursos eki es el Formador."""
    if es_perfil_tecnicoagro(curso) and curso is not None:
        custom = _nombre_propio_tecnico(getattr(curso, 'nombre_agente_tutor', None) or '')
        if custom:
            return custom
        cliente = getattr(curso, 'cliente', None)
        if cliente is not None:
            custom_cli = _nombre_propio_tecnico(getattr(cliente, 'nombre_agente_tutor', None) or '')
            if custom_cli:
                return custom_cli
        return NOMBRE_DEFAULT_TECNICOAGRO
    return fallback or NOMBRE_FORMADOR


def system_prompt_reto_para_curso(curso: Curso | None) -> str:
    from core.tutor_ia_modulo import PROMPT_FACILITADOR_RETO

    if es_perfil_tecnicoagro(curso):
        return system_prompt_reto_tecnicoagro()
    return PROMPT_FACILITADOR_RETO


def system_prompt_evaluacion_para_curso(curso: Curso | None, *, usar_notas: bool) -> str:
    from core.tutor_ia_modulo import (
        PROMPT_FACILITADOR_EVALUACION,
        PROMPT_FACILITADOR_EVALUACION_NOTAS,
    )

    if es_perfil_tecnicoagro(curso):
        return system_prompt_evaluacion_tecnicoagro(usar_notas=usar_notas)
    return (
        PROMPT_FACILITADOR_EVALUACION_NOTAS
        if usar_notas
        else PROMPT_FACILITADOR_EVALUACION
    )


def etiqueta_rol_facilitador(curso: Curso | None) -> str:
    """Prefijo de mensaje (Facilitadora vs asistente técnico)."""
    if es_perfil_tecnicoagro(curso):
        return 'Asistente técnico'
        return 'Formador'
