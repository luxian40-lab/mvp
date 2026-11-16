"""Autoría versionada (bloque 4). Flag EKI_CURSO_VERSIONES apagado = sin efecto en entrega."""

from core.cursos.autoria.servicio import (
    publicar,
    version_de_progreso,
    version_para_inscripcion,
    versiones_activas,
)

__all__ = (
    'versiones_activas',
    'version_de_progreso',
    'version_para_inscripcion',
    'publicar',
)
