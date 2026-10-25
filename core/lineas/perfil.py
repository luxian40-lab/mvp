"""Perfil de línea: lo que cada línea hace, como capacidades explícitas.

Una línea nueva es un perfil nuevo, no un `if` nuevo. Toda capacidad nueva
entra apagada en todos los perfiles y se prende donde aplique.
Este módulo no importa nada de `core`.
"""
from __future__ import annotations

from dataclasses import dataclass

USO_COMPLETA = 'completa'
USO_SOLO_CURSOS = 'solo_cursos'


@dataclass(frozen=True)
class PerfilLinea:
    uso: str
    menu: bool = False
    carrusel: bool = False
    varios_cursos: bool = False
    planes: bool = False
    asesores: bool = False
    agentes_en_curso: bool = False
    certificado: bool = False
    aula: bool = False
    campanas: bool = False
    usa_waba_principal: bool = False
    curso_directo: bool = False


PERFIL_COMPLETA = PerfilLinea(
    uso=USO_COMPLETA,
    menu=True,
    carrusel=True,
    varios_cursos=True,
    planes=True,
    asesores=True,
    agentes_en_curso=True,
    certificado=True,
    aula=True,
    campanas=True,
    usa_waba_principal=True,
)

PERFIL_SOLO_CURSOS = PerfilLinea(
    uso=USO_SOLO_CURSOS,
    agentes_en_curso=True,
    certificado=True,
    campanas=True,
    curso_directo=True,
)

_POR_USO = {
    USO_COMPLETA: PERFIL_COMPLETA,
    USO_SOLO_CURSOS: PERFIL_SOLO_CURSOS,
}


def perfil_por_uso(uso: str | None) -> PerfilLinea:
    """Uso desconocido o vacío = línea principal, como hoy."""
    return _POR_USO.get(str(uso or '').strip(), PERFIL_COMPLETA)
