"""Lectura del flag y operaciones de versión. Flag off: no escribe ni fija cohorte."""
from __future__ import annotations

from django.conf import settings
from django.db import transaction
from django.db.models import Max
from django.utils import timezone


def versiones_activas() -> bool:
    return bool(getattr(settings, 'EKI_CURSO_VERSIONES', False))


def version_de_progreso(progreso) -> object | None:
    """Versión fijada al progreso. Con flag apagado siempre None (entrega como hoy)."""
    if not versiones_activas():
        return None
    return getattr(progreso, 'curso_version_id', None) and getattr(progreso, 'curso_version', None)


def version_para_inscripcion(curso):
    """Versión que recibe un progreso nuevo. Flag off o sin publicada → None."""
    if not versiones_activas():
        return None
    return getattr(curso, 'version_publicada', None)


def publicar(curso, *, nota: str = ''):
    """Crea una versión publicada inmutable y la deja como version_publicada.

    - Flag apagado: no escribe; devuelve None.
    - No toca ProgresoEstudiante: quien ya estudia sigue sin versión o con la suya.
    - La versión publicada anterior del curso pasa a archivado.
    """
    if not versiones_activas():
        return None

    from core.cursos.autoria.ensamblado import congelar_ensamblado
    from core.cursos.autoria.modelos import CursoVersion

    with transaction.atomic():
        locked = type(curso).objects.select_for_update().get(pk=curso.pk)
        snap = congelar_ensamblado(locked)
        ultimo = (
            CursoVersion.objects.filter(curso=locked)
            .aggregate(m=Max('numero'))
            .get('m')
            or 0
        )
        CursoVersion.objects.filter(
            curso=locked,
            estado=CursoVersion.PUBLICADO,
        ).update(estado=CursoVersion.ARCHIVADO)

        version = CursoVersion.objects.create(
            curso=locked,
            numero=ultimo + 1,
            estado=CursoVersion.PUBLICADO,
            ensamblado=snap,
            nota=(nota or '')[:200],
            publicado_en=timezone.now(),
        )
        locked.version_publicada = version
        locked.save(update_fields=['version_publicada'])
    # El caller sigue con el mismo objeto en memoria.
    curso.version_publicada = version
    return version
