"""Tests avance drip-aware en métricas."""
import pytest
from django.utils import timezone
from datetime import timedelta

from core.metricas_empresa import calcular_metricas_empresa
from core.models import (
    Cliente,
    Curso,
    Estudiante,
    Modulo,
    ModuloCompletado,
    ProgresoEstudiante,
    HabilitacionModuloDripCliente,
)
from formulario.factories import ClienteFactory


@pytest.mark.django_db
def test_avance_drip_solo_modulo_uno_disponible():
    cliente = ClienteFactory()
    curso = Curso.objects.create(nombre='Drip test', cliente=cliente, activo=True)
    m1 = Modulo.objects.create(curso=curso, numero=1, titulo='M1', descripcion='d', contenido='c')
    m2 = Modulo.objects.create(curso=curso, numero=2, titulo='M2', descripcion='d', contenido='c')
    futuro = timezone.now() + timedelta(days=30)
    HabilitacionModuloDripCliente.objects.create(
        cliente=cliente, curso=curso, modulo=m2, habilitado_desde=futuro, activo=True,
    )
    est = Estudiante.objects.create(
        nombre='Prod', cedula='8001', telefono='573008000001', cliente=cliente, activo=True,
    )
    prog = ProgresoEstudiante.objects.create(estudiante=est, curso=curso, completado=False)
    ModuloCompletado.objects.create(progreso=prog, modulo=m1)

    data = calcular_metricas_empresa(cliente_id=cliente.id, curso_id=curso.id)
    row = data['progreso_estudiantes'][0]
    assert row['modulos_total'] == 2
    assert row['avance_pct'] == 50
    assert row['modulos_total_drip'] == 1
    assert row['avance_pct_drip'] == 100
    assert data['resumen']['promedio_avance_drip_pct'] == 100.0


@pytest.mark.django_db
def test_modulo_hasta_numero_fija_denominador():
    cliente = ClienteFactory()
    curso = Curso.objects.create(nombre='Hasta M1', cliente=cliente, activo=True)
    m1 = Modulo.objects.create(curso=curso, numero=1, titulo='M1', descripcion='d', contenido='c')
    Modulo.objects.create(curso=curso, numero=2, titulo='M2', descripcion='d', contenido='c')
    est = Estudiante.objects.create(
        nombre='X', cedula='8002', telefono='573008000002', cliente=cliente, activo=True,
    )
    prog = ProgresoEstudiante.objects.create(estudiante=est, curso=curso, completado=False)
    ModuloCompletado.objects.create(progreso=prog, modulo=m1)

    data = calcular_metricas_empresa(
        cliente_id=cliente.id,
        curso_id=curso.id,
        modulo_hasta_numero=1,
        usar_drip_calendario=False,
    )
    assert data['progreso_estudiantes'][0]['avance_pct_drip'] == 100
    assert data['drip']['modulos_en_denominador'] == 1
