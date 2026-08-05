"""Modo aula Clases (Aprende) — suite mínima."""
from __future__ import annotations

import pytest

from aprende.acceso_modulos import modulos_visibles_aula
from core.gamificacion_modo import MODO_PUNTOS, gamificacion_otorga_puntos
from core.models import Cliente, Curso, Estudiante, Modulo, ProgresoEstudiante
from core.response_templates import get_response_for_intent

pytestmark = pytest.mark.django_db


def _org(nombre: str, tel: str) -> Cliente:
    return Cliente.objects.create(
        nombre=nombre,
        contacto_principal='C',
        email=f'{tel}@example.com',
        telefono=tel,
    )


def test_modo_clases_libera_todas_las_clases_y_apaga_gamif():
    cli = _org('Org Clases', '573009991111')
    curso = Curso.objects.create(
        nombre='Clases Aprende test',
        descripcion='d',
        cliente=cli,
        modo_aula=Curso.MODO_AULA_CLASES,
        usar_gamificacion=True,
    )
    assert curso.usar_gamificacion is False
    assert curso.usar_agentes_ia is False
    m1 = Modulo.objects.create(curso=curso, numero=1, titulo='C1', contenido='x')
    m2 = Modulo.objects.create(curso=curso, numero=2, titulo='C2', contenido='y')
    est = Estudiante.objects.create(
        cedula='CLASES01',
        nombre='Est Clases',
        telefono='573009991112',
        cliente=cli,
        activo=True,
    )
    ProgresoEstudiante.objects.create(
        estudiante=est, curso=curso, modulo_actual=m1, completado=False,
    )
    ids = {m.id for m in modulos_visibles_aula(est, curso)}
    assert ids == {m1.id, m2.id}


def test_listo_en_modo_clases_redirige_a_aprende():
    cli = _org('Org Listo Clases', '573009991301')
    curso = Curso.objects.create(
        nombre='Clases listo test',
        descripcion='d',
        cliente=cli,
        modo_aula=Curso.MODO_AULA_CLASES,
    )
    m1 = Modulo.objects.create(curso=curso, numero=1, titulo='C1', contenido='x')
    est = Estudiante.objects.create(
        cedula='LISTOCL01',
        nombre='Est Listo',
        telefono='573009991302',
        cliente=cli,
        activo=True,
        estado_chat='ACTIVO',
        estado_onboarding='completado',
    )
    ProgresoEstudiante.objects.create(
        estudiante=est, curso=curso, modulo_actual=m1, completado=False,
    )
    resp = get_response_for_intent(
        'continuar_leccion',
        est.nombre,
        estudiante_id=est.id,
        mensaje_original='listo',
    )
    assert 'Aprende' in resp
    assert 'aula' in resp.lower()
    prog = ProgresoEstudiante.objects.get(estudiante=est, curso=curso)
    assert prog.modulo_actual_id == m1.id
    assert not prog.completado


def test_curso_modulos_sigue_tope_avance_y_gamif():
    cli = Cliente.objects.create(
        nombre='Org Normal',
        contacto_principal='N',
        email='normal@example.com',
        telefono='573009991211',
        modo_gamificacion=MODO_PUNTOS,
    )
    curso = Curso.objects.create(
        nombre='Curso WA normal',
        descripcion='d',
        cliente=cli,
        modo_aula=Curso.MODO_AULA_MODULOS,
        usar_gamificacion=True,
        usar_agentes_ia=True,
    )
    curso.refresh_from_db()
    assert curso.es_modo_clases() is False
    assert gamificacion_otorga_puntos(cli, curso) is True
    m1 = Modulo.objects.create(curso=curso, numero=1, titulo='M1', contenido='x')
    m2 = Modulo.objects.create(curso=curso, numero=2, titulo='M2', contenido='y')
    est = Estudiante.objects.create(
        cedula='NORMAL01',
        nombre='Est Normal',
        telefono='573009991212',
        cliente=cli,
        activo=True,
    )
    ProgresoEstudiante.objects.create(
        estudiante=est, curso=curso, modulo_actual=m1, completado=False,
    )
    ids = {m.id for m in modulos_visibles_aula(est, curso)}
    assert ids == {m1.id}
    assert m2.id not in ids
