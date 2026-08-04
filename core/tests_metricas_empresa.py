"""Tests métricas por empresa / Nati."""
import pytest
from decimal import Decimal

from core.metricas_empresa import (
    calcular_semaforo,
    calcular_metricas_empresa,
    resolver_metas_educativa,
)
from core.models import Cliente, Curso, Estudiante, ProgresoEstudiante, MetaMetricaEmpresa
from formulario.factories import ClienteFactory


@pytest.mark.django_db
def test_calcular_semaforo_mayor_es_mejor():
    assert calcular_semaforo(85, 80, "mayor_es_mejor") == "verde"
    assert calcular_semaforo(60, 80, "mayor_es_mejor") == "amarillo"
    assert calcular_semaforo(30, 80, "mayor_es_mejor") == "rojo"


@pytest.mark.django_db
def test_calcular_semaforo_menor_es_mejor():
    assert calcular_semaforo(15, 20, "menor_es_mejor") == "verde"
    assert calcular_semaforo(25, 20, "menor_es_mejor") == "amarillo"


@pytest.mark.django_db
def test_resolver_metas_curso_especifico():
    cliente = ClienteFactory()
    curso = Curso.objects.create(nombre="Test curso", cliente=cliente, activo=True)
    MetaMetricaEmpresa.objects.create(
        cliente=cliente,
        curso=curso,
        meta_finalizacion_porcentaje=Decimal("90"),
        activa=True,
    )
    m = resolver_metas_educativa(cliente.id, curso.id)
    assert m["finalizacion"] == 90.0


@pytest.mark.django_db
def test_metricas_empresa_estados_progreso():
    cliente = ClienteFactory()
    curso = Curso.objects.create(nombre="C1", cliente=cliente, activo=True)
    e1 = Estudiante.objects.create(
        nombre="A", cedula="9001", telefono="573001000001", cliente=cliente, activo=True
    )
    e2 = Estudiante.objects.create(
        nombre="B", cedula="9002", telefono="573001000002", cliente=cliente, activo=True
    )
    ProgresoEstudiante.objects.create(estudiante=e1, curso=curso, completado=True)
    ProgresoEstudiante.objects.create(estudiante=e2, curso=curso, completado=False)

    data = calcular_metricas_empresa(cliente_id=cliente.id, curso_id=curso.id)
    assert data["resumen"]["total_inscritos"] == 2
    assert data["resumen"]["finalizados"] == 1
    assert data["resumen"]["no_iniciados"] == 1
    assert "finalizacion" in data["semaforos"]
    assert len(data.get("progreso_estudiantes", [])) == 2
    assert any("M" in row.get("modulo_actual", "") or row["estado"] == "Completado" for row in data["progreso_estudiantes"])

    slim = calcular_metricas_empresa(
        cliente_id=cliente.id, curso_id=curso.id, incluir_progreso_detalle=False,
    )
    assert slim["resumen"]["total_inscritos"] == 2
    assert slim.get("progreso_estudiantes") == []
    assert slim.get("detalle_incluido") is False
