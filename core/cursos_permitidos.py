"""Cursos en los que se puede inscribir a un estudiante desde el alta del admin.

Un curso general de eki es un Curso con cliente vacío. No es un cliente
llamado General ni una bandera aparte.

Archivado = activo False. No hay un campo «de prueba»: un curso de una
organización demo (Cliente.es_demo) se trata como de prueba y solo lo ve
la organización dueña u otra organización demo.
"""
from __future__ import annotations

import re

from django.db.models import Count


def cursos_permitidos(organizacion):
    """Cursos activos de esa organización, más los generales.

    Sin organización: solo generales. Una organización demo también ve los
    cursos de otras organizaciones demo. Los inactivos no entran.
    """
    from core.models import Curso

    base = (
        Curso.objects.filter(activo=True)
        .select_related('cliente')
        .annotate(n_modulos=Count('modulos'))
    )
    generales = base.filter(cliente__isnull=True)
    if organizacion is None:
        return generales.order_by('orden', 'nombre', 'id')
    propios = base.filter(cliente_id=organizacion.pk)
    if getattr(organizacion, 'es_demo', False):
        de_demo = base.filter(cliente__es_demo=True)
        return (propios | generales | de_demo).distinct().order_by('orden', 'nombre', 'id')
    return (propios | generales).distinct().order_by('orden', 'nombre', 'id')


def curso_esta_permitido(curso, organizacion) -> bool:
    if curso is None:
        return False
    return cursos_permitidos(organizacion).filter(pk=curso.pk).exists()


def inscripcion_fuera_de_regla(progreso) -> bool:
    """El curso ya inscrito no cumple la regla. Un curso inactivo no entra aquí."""
    curso = progreso.curso
    if curso is None or not curso.activo:
        return False
    org = progreso.estudiante.cliente
    if curso.cliente_id is None:
        return False
    if org is not None and curso.cliente_id == org.pk:
        return False
    if org is not None and getattr(org, 'es_demo', False) and getattr(curso.cliente, 'es_demo', False):
        return False
    return True


def texto_cursos(organizacion, permitidos=None) -> str:
    if organizacion is None:
        return 'Sin organización: solo cursos generales de eki.'
    qs = permitidos if permitidos is not None else cursos_permitidos(organizacion)
    if not qs.filter(cliente_id=organizacion.pk).exists():
        return f'{organizacion.nombre} no tiene cursos propios: se muestran los generales.'
    return f'Solo se muestran los cursos de {organizacion.nombre} y los generales de eki.'


def cursos_agrupados(organizacion):
    """Tres listas: propios, generales y, si la org es demo, cursos de otras demo."""
    propios = []
    generales = []
    otras_demo = []
    for curso in cursos_permitidos(organizacion):
        if curso.cliente_id is None:
            generales.append(curso)
        elif organizacion is not None and curso.cliente_id == organizacion.pk:
            propios.append(curso)
        else:
            otras_demo.append(curso)
    return propios, generales, otras_demo


def parece_nombre_de_prueba(nombre: str) -> bool:
    """Candidato a revisar. No oculta el curso: no hay marca en el modelo."""
    texto = (nombre or '').strip().casefold()
    if not texto:
        return False
    if '[prueba]' in texto or texto.startswith('pruebas'):
        return True
    if texto.startswith('curso test'):
        return True
    match = re.fullmatch(r'nuevo curso (\d+)', texto)
    if match and 5 <= int(match.group(1)) <= 14:
        return True
    return False
