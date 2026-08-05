"""Modo aula clases: todas las lecciones visibles sin avance WA."""
from __future__ import annotations

import pytest

from aprende.acceso_modulos import modulos_visibles_aula
from core.models import Cliente, Curso, Estudiante, Modulo, ProgresoEstudiante

pytestmark = pytest.mark.django_db


def test_modo_clases_libera_todas_las_clases():
    cli = Cliente.objects.create(
        nombre="Org Clases",
        contacto_principal="C",
        email="clases@example.com",
        telefono="573009991111",
    )
    curso = Curso.objects.create(
        nombre="10x test",
        descripcion="d",
        cliente=cli,
        modo_aula=Curso.MODO_AULA_CLASES,
        usar_gamificacion=True,  # save() debe apagarlo
    )
    assert curso.usar_gamificacion is False
    assert curso.usar_agentes_ia is False
    m1 = Modulo.objects.create(curso=curso, numero=1, titulo="C1", contenido="x")
    m2 = Modulo.objects.create(curso=curso, numero=2, titulo="C2", contenido="y")
    est = Estudiante.objects.create(
        cedula="CLASES01",
        nombre="Est Clases",
        telefono="573009991112",
        cliente=cli,
        activo=True,
    )
    ProgresoEstudiante.objects.create(
        estudiante=est, curso=curso, modulo_actual=m1, completado=False
    )

    ids = {m.id for m in modulos_visibles_aula(est, curso)}
    assert ids == {m1.id, m2.id}
