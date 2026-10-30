"""Nombres que portal, aprende, studio y formulario prestan a core.

Core no importa esas apps. Ellas llaman registrar() al cargarse.
"""
from __future__ import annotations

_registro: dict[str, object] = {}


def registrar(nombre: str, obj: object) -> None:
    _registro[nombre] = obj


def __getattr__(nombre: str):
    try:
        return _registro[nombre]
    except KeyError:
        raise AttributeError(
            f'{nombre} todavía no está registrado en core.puentes'
        ) from None
