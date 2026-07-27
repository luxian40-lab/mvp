"""Tests catálogo Nat (ProductoCatalogo) y selección de organización."""

from __future__ import annotations

import pytest

from core.models import Cliente, ProductoCatalogo
from core.nati import armar_system_prompt, obtener_contexto_productos


pytestmark = pytest.mark.django_db


@pytest.fixture
def cliente_org():
    return Cliente.objects.create(
        nombre='Agronexo Demo',
        contacto_principal='Ana',
        email='ana@agronexo.test',
        telefono='573001112233',
        nombre_bot='Nat',
    )


def test_obtener_contexto_productos_vacio_sin_cliente():
    assert obtener_contexto_productos(None) == ''


def test_obtener_contexto_productos_vacio_sin_productos(cliente_org):
    assert obtener_contexto_productos(cliente_org) == ''


def test_obtener_contexto_productos_incluye_datos(cliente_org):
    ProductoCatalogo.objects.create(
        cliente=cliente_org,
        nombre='Fungicida X',
        descripcion='Control de roya',
        problema_que_resuelve='roya café manchas amarillas',
        dosis='300 g por 200 L',
        precio_cop=85000,
        unidad='500 g',
        url_producto='https://ejemplo.com/fungicida-x',
        categoria='fungicida',
    )
    ctx = obtener_contexto_productos(cliente_org)
    assert 'CATÁLOGO DE PRODUCTOS' in ctx
    assert 'Fungicida X' in ctx
    assert 'roya café' in ctx
    assert 'https://ejemplo.com/fungicida-x' in ctx


def test_armar_system_prompt_incluye_catalogo_y_reglas(cliente_org):
    ProductoCatalogo.objects.create(
        cliente=cliente_org,
        nombre='Urea foliar',
        descripcion='Nitrógeno rápido',
        problema_que_resuelve='deficiencia nitrógeno amarilleo',
    )
    prompt = armar_system_prompt(cliente=cliente_org)
    assert 'Urea foliar' in prompt
    assert 'CÓMO RECOMENDAR PRODUCTOS' in prompt
    assert 'NUNCA inventes precios' in prompt


def test_armar_system_prompt_sin_catalogo_mensaje_fallback(cliente_org):
    prompt = armar_system_prompt(cliente=cliente_org)
    assert 'PLAN B' in prompt
    assert 'No hay fichas comerciales' in prompt or 'SIN CATÁLOGO' in prompt
    assert 'principio activo' in prompt.lower() or 'fórmula' in prompt.lower()
    assert 'No invente' in prompt or 'no invente' in prompt.lower()


def test_armar_system_prompt_con_catalogo_incluye_plan_b_si_no_encaja(cliente_org):
    ProductoCatalogo.objects.create(
        cliente=cliente_org,
        nombre='Urea foliar',
        descripcion='Nitrógeno rápido',
        problema_que_resuelve='deficiencia nitrógeno amarilleo',
    )
    prompt = armar_system_prompt(cliente=cliente_org)
    assert 'PLAN B' in prompt
    assert 'principio activo' in prompt.lower() or 'fórmula genérica' in prompt.lower()


