"""Resolución de perfil de facilitador (Claudia vs tecnicoagro). Claudia no se elimina."""
from __future__ import annotations

from typing import TYPE_CHECKING

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


def nombre_display_facilitador(curso: Curso | None, fallback: str = 'Claudia') -> str:
    """Nombre visible en WhatsApp (presentación / cabeceras)."""
    if curso is not None:
        custom = (getattr(curso, 'nombre_agente_tutor', None) or '').strip()
        if custom:
            return custom
        cliente = getattr(curso, 'cliente', None)
        if cliente is not None:
            custom_cli = (getattr(cliente, 'nombre_agente_tutor', None) or '').strip()
            if custom_cli:
                return custom_cli
    if es_perfil_tecnicoagro(curso):
        return NOMBRE_DEFAULT_TECNICOAGRO
    return fallback or 'Claudia'


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
    return 'Facilitadora'
