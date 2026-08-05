"""*listo* en curso modo Clases no avanza por WhatsApp."""
from __future__ import annotations

import pytest

from core.models import Cliente, Curso, Estudiante, Modulo, ProgresoEstudiante
from core.response_templates import get_response_for_intent

pytestmark = pytest.mark.django_db


def test_listo_en_modo_clases_redirige_a_aprende():
    cli = Cliente.objects.create(
        nombre='Org Listo Clases',
        contacto_principal='C',
        email='lc@example.com',
        telefono='573009991301',
    )
    curso = Curso.objects.create(
        nombre='10x listo test',
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
        estudiante=est, curso=curso, modulo_actual=m1, completado=False
    )

    resp = get_response_for_intent(
        'continuar_leccion',
        est.nombre,
        estudiante_id=est.id,
        mensaje_original='listo',
    )
    assert 'Aprende' in resp
    assert 'listo' in resp.lower()
    assert 'aula' in resp.lower()
    # No debió marcar módulo completado / avanzar
    est.refresh_from_db()
    prog = ProgresoEstudiante.objects.get(estudiante=est, curso=curso)
    assert prog.modulo_actual_id == m1.id
    assert not prog.completado
