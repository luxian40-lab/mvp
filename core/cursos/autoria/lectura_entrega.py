"""Lectura de entrega desde CursoVersion.ensamblado (residual B4).

Flag ``EKI_CURSO_VERSIONES`` apagado o progreso sin versión → None / árbol vivo.
"""
from __future__ import annotations

from core.cursos.autoria.servicio import version_de_progreso, versiones_activas


def ensamblado_de_progreso(progreso) -> dict | None:
    """Snapshot anclado al progreso, o None si la entrega sigue el árbol vivo."""
    if not versiones_activas():
        return None
    version = version_de_progreso(progreso)
    if version is None:
        return None
    snap = getattr(version, 'ensamblado', None)
    if not isinstance(snap, dict) or not snap:
        return None
    return snap


def modulo_en_ensamblado(snap: dict | None, modulo_id) -> dict | None:
    if not snap or modulo_id is None:
        return None
    try:
        mid = int(modulo_id)
    except (TypeError, ValueError):
        return None
    for mod in snap.get('modulos') or []:
        if int(mod.get('id') or 0) == mid:
            return mod
    return None


def paso_en_ensamblado(snap: dict | None, paso_id) -> dict | None:
    if not snap or paso_id is None:
        return None
    try:
        pid = int(paso_id)
    except (TypeError, ValueError):
        return None
    for mod in snap.get('modulos') or []:
        for sec in mod.get('secciones') or []:
            for paso in sec.get('pasos') or []:
                if int(paso.get('id') or 0) == pid:
                    return paso
    return None


def _filas_modulos_ordenadas(snap: dict) -> list[dict]:
    return sorted(
        snap.get('modulos') or [],
        key=lambda m: (int(m.get('numero') or 0), int(m.get('id') or 0)),
    )


def siguiente_modulo_orm_desde_snap(curso, snap: dict, modulo_actual):
    """Siguiente ``Modulo`` ORM según el snap (misma regla: no salta borradores).

    Usa ``publicado_wa`` del ensamblado, no el del árbol vivo.
    """
    from core.models import Modulo
    from core.models.modulos import curso_usa_gate_publicacion_wa

    filas = _filas_modulos_ordenadas(snap)
    gate = curso_usa_gate_publicacion_wa(curso)

    if modulo_actual is None:
        if not filas:
            return None
        primero = filas[0]
        if gate and not primero.get('publicado_wa'):
            return None
        return Modulo.objects.filter(pk=primero.get('id')).first()

    try:
        num = int(modulo_actual.numero)
    except (TypeError, ValueError, AttributeError):
        return None

    siguientes = [m for m in filas if int(m.get('numero') or 0) > num]
    if not siguientes:
        return None
    cand = siguientes[0]
    if gate and not cand.get('publicado_wa'):
        return None
    return Modulo.objects.filter(pk=cand.get('id')).first()


def titulo_modulo_para_entrega(progreso, modulo) -> str:
    """Título desde snapshot si hay cohorte versionada; si no, el vivo."""
    snap = ensamblado_de_progreso(progreso)
    fila = modulo_en_ensamblado(snap, getattr(modulo, 'id', None))
    if fila is not None:
        return fila.get('titulo') or ''
    return getattr(modulo, 'titulo', None) or ''


def contenido_paso_para_entrega(progreso, paso) -> str:
    """Contenido del paso desde snapshot si hay cohorte; si no, el vivo."""
    snap = ensamblado_de_progreso(progreso)
    fila = paso_en_ensamblado(snap, getattr(paso, 'id', None))
    if fila is not None:
        return fila.get('contenido') or ''
    return getattr(paso, 'contenido', None) or ''


def modo_entrega_modulo_para_entrega(progreso, modulo) -> str:
    """modo_entrega desde snap (default auto si snap viejo); si no, el vivo."""
    snap = ensamblado_de_progreso(progreso)
    fila = modulo_en_ensamblado(snap, getattr(modulo, 'id', None))
    if fila is not None:
        return fila.get('modo_entrega') or 'auto'
    return getattr(modulo, 'modo_entrega', None) or 'auto'
