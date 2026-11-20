"""Diploma de WhatsApp solo si la línea pide la nota 1–10 y ya está guardada.

La línea 2 tiene nota_cierre apagada: sigue emitiendo sin NPS.
Sin phone id de turno, perfil_de cae en la línea principal (sí pide nota).
"""
from __future__ import annotations


def omite_diploma_sin_nota(estudiante, curso) -> bool:
    if estudiante is None or curso is None:
        return False
    from core.lineas.variante import perfil_de
    from core.models import NotaCierreCurso

    if not perfil_de().nota_cierre:
        return False
    return not NotaCierreCurso.objects.filter(
        estudiante_id=getattr(estudiante, 'pk', None),
        curso_id=getattr(curso, 'pk', None),
    ).exists()
