"""Tests de la API de integración (LXP) — endpoints GEI."""
from __future__ import annotations

import json

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.test.utils import override_settings
from django.utils import timezone

from core.models import Cliente, Curso, Estudiante
from core.models_extras import GrupoEstudiantes


pytestmark = pytest.mark.django_db


API_KEY_TEST = "lxp-test-key-123"


def _crear_estudiante(cliente=None, idx=1):
    return Estudiante.objects.create(
        cedula=f"LXP{idx:05d}",
        nombre=f"Estudiante LXP {idx}",
        telefono=f"57300999{idx:04d}",
        cliente=cliente,
    )


def _crear_ficha(estudiante, *, cliente=None, curso=None, **campos):
    from formulario.models import FichaGEI
    return FichaGEI.objects.create(
        estudiante=estudiante,
        cliente=cliente,
        curso=curso,
        **campos,
    )


def _client_get(client: Client, url: str, **extra):
    """Helper que evita el 301 de SECURE_SSL_REDIRECT en tests forzando secure=True."""
    return client.get(url, secure=True, HTTP_HOST="127.0.0.1", **extra)


@override_settings(INTEGRACION_API_KEY=API_KEY_TEST, SECURE_SSL_REDIRECT=False)
def test_metricas_sin_key_devuelve_401():
    client = Client()
    resp = _client_get(client, "/api/integracion/educativa/metricas/")
    assert resp.status_code == 401


@override_settings(INTEGRACION_API_KEY=API_KEY_TEST, SECURE_SSL_REDIRECT=False)
def test_metricas_key_invalida_devuelve_401():
    client = Client()
    resp = _client_get(
        client,
        "/api/integracion/educativa/metricas/",
        HTTP_AUTHORIZATION="Bearer key-malo",
    )
    assert resp.status_code == 401


@override_settings(INTEGRACION_API_KEY=API_KEY_TEST, SECURE_SSL_REDIRECT=False)
def test_metricas_incluye_bloque_gei():
    cliente = Cliente.objects.create(
        nombre="ACME LXP",
        contacto_principal="C",
        email="lxp@example.com",
        telefono="573001110000",
    )
    curso = Curso.objects.create(nombre="Curso LXP", descripcion="x")
    estudiante = _crear_estudiante(cliente=cliente)
    _crear_ficha(estudiante, cliente=cliente, curso=curso, nombre_finca="F1", area_ha=2.0)

    client = Client()
    today = timezone.localdate().isoformat()
    resp = _client_get(
        client,
        f"/api/integracion/educativa/metricas/?cliente_id={cliente.id}&desde={today}&hasta={today}",
        HTTP_AUTHORIZATION=f"Bearer {API_KEY_TEST}",
    )
    assert resp.status_code == 200, resp.content[:200]
    body = json.loads(resp.content.decode("utf-8"))
    assert "formularios_gei" in body
    bloque = body["formularios_gei"]
    assert bloque.get("disponible") is True
    assert "fichas_totales" in bloque
    assert "completitud_promedio_pct" in bloque
    assert "campo_con_menor_completitud" in bloque
    assert "sesiones_activas" in bloque


@override_settings(INTEGRACION_API_KEY=API_KEY_TEST, SECURE_SSL_REDIRECT=False)
def test_gei_detalle_paginado_y_auth():
    cliente = Cliente.objects.create(
        nombre="ACME PAG",
        contacto_principal="C",
        email="pag@example.com",
        telefono="573001110000",
    )
    curso = Curso.objects.create(nombre="Curso PAG", descripcion="x")
    estudiante = _crear_estudiante(cliente=cliente, idx=2)
    for i in range(5):
        _crear_ficha(
            estudiante,
            cliente=cliente,
            curso=curso,
            nombre_finca=f"F{i}",
            area_ha=float(i + 1),
        )

    client = Client()
    today = timezone.localdate().isoformat()

    resp_no_auth = _client_get(
        client,
        f"/api/integracion/gei/detalle/?cliente_id={cliente.id}&desde={today}&hasta={today}",
    )
    assert resp_no_auth.status_code == 401

    resp = _client_get(
        client,
        f"/api/integracion/gei/detalle/?cliente_id={cliente.id}&desde={today}&hasta={today}&page=1&page_size=2",
        HTTP_AUTHORIZATION=f"Bearer {API_KEY_TEST}",
    )
    assert resp.status_code == 200, resp.content[:300]
    body = json.loads(resp.content.decode("utf-8"))
    assert body["meta"]["page"] == 1
    assert body["meta"]["page_size"] == 2
    assert body["meta"]["total"] >= 5
    assert len(body["fichas"]) == 2


@override_settings(INTEGRACION_API_KEY=API_KEY_TEST, SECURE_SSL_REDIRECT=False)
def test_gei_detalle_requiere_cliente_id():
    client = Client()
    today = timezone.localdate().isoformat()
    resp = _client_get(
        client,
        f"/api/integracion/gei/detalle/?desde={today}&hasta={today}",
        HTTP_AUTHORIZATION=f"Bearer {API_KEY_TEST}",
    )
    assert resp.status_code == 400
    body = json.loads(resp.content.decode("utf-8"))
    assert "cliente_id" in (body.get("error") or "").lower()


@override_settings(INTEGRACION_API_KEY=API_KEY_TEST, SECURE_SSL_REDIRECT=False)
def test_gei_exportar_xlsx_content_type():
    pytest.importorskip("openpyxl")

    cliente = Cliente.objects.create(
        nombre="ACME XLS",
        contacto_principal="C",
        email="xls@example.com",
        telefono="573001110000",
    )
    curso = Curso.objects.create(nombre="Curso XLS", descripcion="x")
    estudiante = _crear_estudiante(cliente=cliente, idx=3)
    _crear_ficha(estudiante, cliente=cliente, curso=curso, nombre_finca="X", area_ha=1.0)

    client = Client()
    today = timezone.localdate().isoformat()
    resp = _client_get(
        client,
        f"/api/integracion/gei/exportar/?cliente_id={cliente.id}&desde={today}&hasta={today}",
        HTTP_AUTHORIZATION=f"Bearer {API_KEY_TEST}",
    )
    assert resp.status_code == 200, resp.content[:200]
    ct = resp.headers.get("Content-Type", "")
    assert "spreadsheetml" in ct or "officedocument" in ct
    cd = resp.headers.get("Content-Disposition", "")
    assert "attachment" in cd
    assert ".xlsx" in cd
    assert resp.content[:2] == b"PK"


@override_settings(SECURE_SSL_REDIRECT=False)
def test_exportar_metricas_excel_sin_auth():
    client = Client()
    resp = _client_get(client, "/admin/dashboard-metrics/exportar/")
    assert resp.status_code == 302
    assert "/admin/login/" in resp.headers.get("Location", "")


@override_settings(SECURE_SSL_REDIRECT=False)
def test_exportar_metricas_excel_staff():
    pytest.importorskip("openpyxl")
    User = get_user_model()
    staff = User.objects.create_user("staff_excel", "staff@example.com", "123", is_staff=True, is_superuser=True)
    client = Client()
    assert client.login(username="staff_excel", password="123")
    resp = _client_get(client, "/admin/dashboard-metrics/exportar/")
    assert resp.status_code == 200
    assert "spreadsheetml" in resp.headers.get("Content-Type", "")
    assert resp.content[:2] == b"PK"


@override_settings(SECURE_SSL_REDIRECT=False)
def test_exportar_metricas_excel_por_cliente():
    pytest.importorskip("openpyxl")
    User = get_user_model()
    User.objects.create_user("staff_excel_2", "staff2@example.com", "123", is_staff=True, is_superuser=True)
    c1 = Cliente.objects.create(nombre="Cliente Uno", contacto_principal="A", email="a@x.co", telefono="573001110001")
    c2 = Cliente.objects.create(nombre="Cliente Dos", contacto_principal="B", email="b@x.co", telefono="573001110002")
    _crear_estudiante(cliente=c1, idx=31)
    _crear_estudiante(cliente=c2, idx=32)
    client = Client()
    assert client.login(username="staff_excel_2", password="123")
    resp = _client_get(client, f"/admin/dashboard-metrics/exportar/?cliente={c1.id}")
    assert resp.status_code == 200
    cd = resp.headers.get("Content-Disposition", "").lower()
    assert "cliente_uno" in cd


@override_settings(SECURE_SSL_REDIRECT=False)
def test_exportar_metricas_excel_por_grupo():
    pytest.importorskip("openpyxl")
    User = get_user_model()
    User.objects.create_user("staff_excel_3", "staff3@example.com", "123", is_staff=True, is_superuser=True)
    cliente = Cliente.objects.create(nombre="Cliente Grupo", contacto_principal="C", email="cg@x.co", telefono="573001110003")
    e1 = _crear_estudiante(cliente=cliente, idx=41)
    _crear_estudiante(cliente=cliente, idx=42)
    grupo = GrupoEstudiantes.objects.create(nombre="Grupo Piloto", emoji="👥", cliente=cliente)
    grupo.estudiantes.add(e1)

    client = Client()
    assert client.login(username="staff_excel_3", password="123")
    resp = _client_get(client, f"/admin/dashboard-metrics/exportar/?cliente={cliente.id}&grupo={grupo.id}")
    assert resp.status_code == 200
    assert "spreadsheetml" in resp.headers.get("Content-Type", "")
    cd = resp.headers.get("Content-Disposition", "").lower()
    assert "grupo_piloto" in cd


@override_settings(
    INTEGRACION_API_KEY='',
    INTEGRACION_API_REQUIRE_KEY=True,
    SECURE_SSL_REDIRECT=False,
)
def test_api_key_vacia_con_require_key_503():
    """En prod, key vacía no abre la puerta."""
    client = Client()
    resp = _client_get(client, '/api/integracion/educativa/metricas/')
    assert resp.status_code == 503
    body = json.loads(resp.content.decode('utf-8'))
    assert body.get('success') is False


@override_settings(
    INTEGRACION_API_KEY=API_KEY_TEST,
    INTEGRACION_API_REQUIRE_KEY=True,
    SECURE_SSL_REDIRECT=False,
)
def test_api_estudiante_sin_key_401():
    client = Client()
    resp = _client_get(client, '/api/estudiante/573009990001/')
    assert resp.status_code == 401


@override_settings(
    INTEGRACION_API_KEY=API_KEY_TEST,
    INTEGRACION_API_REQUIRE_KEY=True,
    SECURE_SSL_REDIRECT=False,
)
def test_api_estudiante_con_key_ok():
    cliente = Cliente.objects.create(
        nombre='ACME Est',
        contacto_principal='C',
        email='est@example.com',
        telefono='573001110099',
    )
    estudiante = _crear_estudiante(cliente=cliente, idx=99)
    client = Client()
    resp = _client_get(
        client,
        f'/api/estudiante/{estudiante.telefono}/',
        HTTP_AUTHORIZATION=f'Bearer {API_KEY_TEST}',
    )
    assert resp.status_code == 200
    body = json.loads(resp.content.decode('utf-8'))
    assert body.get('success') is True


@override_settings(
    INTEGRACION_API_KEY=API_KEY_TEST,
    INTEGRACION_API_REQUIRE_KEY=True,
    INTEGRACION_API_RATE_LIMIT=2,
    INTEGRACION_API_RATE_PERIOD=60,
    SECURE_SSL_REDIRECT=False,
)
def test_api_lxp_rate_limit_429(settings):
    from django.core.cache import cache

    cache.clear()
    client = Client()
    headers = {'HTTP_AUTHORIZATION': f'Bearer {API_KEY_TEST}'}
    assert _client_get(client, '/api/integracion/educativa/metricas/?cliente_id=1', **headers).status_code in (200, 400)
    assert _client_get(client, '/api/integracion/educativa/metricas/?cliente_id=1', **headers).status_code in (200, 400)
    resp = _client_get(client, '/api/integracion/educativa/metricas/?cliente_id=1', **headers)
    assert resp.status_code == 429
