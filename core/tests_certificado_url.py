import pytest
from django.test import Client, override_settings
from django.utils import timezone

from core.models import Cliente, Curso, Estudiante
from core.models_certificados import Certificado


@pytest.mark.django_db
def test_obtener_url_verificacion_usa_eki():
    cliente = Cliente.objects.create(
        nombre="Org",
        nit="900000000-0",
        contacto_principal="A",
        email="a@b.co",
        telefono="573009990001",
        activo=True,
    )
    curso = Curso.objects.create(
        nombre="Curso X",
        descripcion="Desc",
        cliente=cliente,
        activo=True,
    )
    est = Estudiante.objects.create(
        cedula="111111111",
        nombre="Test",
        telefono="573009990002",
        cliente=cliente,
        estado_chat="ACTIVO",
        acepto_terminos=True,
        activo=True,
    )
    cert = Certificado.objects.create(
        estudiante=est,
        curso=curso,
        calificacion_final=90,
        fecha_inicio="2026-01-01",
        fecha_completado="2026-02-01",
        emitido=True,
        fecha_emision=timezone.now(),
    )
    url = cert.obtener_url_verificacion()
    assert "/verificar-certificado/" in url
    assert cert.codigo_verificacion in url
    assert "netlify" not in url
    assert "admin.eki" not in url
    assert "certificados.eki.technology" in url


@pytest.mark.django_db
@override_settings(
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
    SECURE_SSL_REDIRECT=False,
)
def test_pagina_verificar_certificado_valido_e_invalido():
    cliente = Cliente.objects.create(
        nombre="Org V",
        nit="900000000-1",
        contacto_principal="A",
        email="v@b.co",
        telefono="573009990011",
        activo=True,
    )
    curso = Curso.objects.create(nombre="Curso Val", cliente=cliente, activo=True)
    est = Estudiante.objects.create(
        cedula="222222222",
        nombre="Ana Valida",
        telefono="573009990012",
        cliente=cliente,
        estado_chat="ACTIVO",
        acepto_terminos=True,
        activo=True,
    )
    cert = Certificado.objects.create(
        estudiante=est,
        curso=curso,
        calificacion_final=88,
        fecha_inicio="2026-01-01",
        fecha_completado="2026-02-01",
        emitido=True,
        fecha_emision=timezone.now(),
        codigo_verificacion="eki-TEST-VALI-D001",
    )
    http = Client()
    # URL en mayúsculas (como tras escanear / tipografiar) debe resolver igual
    r = http.get("/verificar-certificado/EKI-TEST-VALI-D001/")
    assert r.status_code == 200
    body = r.content.lower()
    assert b"valido" in body or b"v\xc3\xa1lido" in r.content
    assert b"Ana Valida" in r.content
    assert b"Curso Val" in r.content

    r2 = http.get("/verificar-certificado/EKI-NOEX-ISTE-0000/")
    assert r2.status_code == 404
    assert b"No encontramos" in r2.content or b"no v" in r2.content.lower()

    r3 = http.get("/verificar/?code=eki-TEST-VALI-D001")
    assert r3.status_code == 302
    assert "verificar-certificado" in r3["Location"]

    r_home = http.get("/verificar/")
    assert r_home.status_code == 200
    assert b"Verificar un certificado" in r_home.content
    assert b"No est" not in r_home.content or b"Verificar un certificado" in r_home.content


@pytest.mark.django_db
@override_settings(
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
    SECURE_SSL_REDIRECT=False,
)
def test_ficha_publica_respeta_hero_y_tamano_plantilla():
    from core.models_certificados import PlantillaCertificado

    cliente = Cliente.objects.create(
        nombre="Org Hero",
        nit="900000000-2",
        contacto_principal="A",
        email="h@b.co",
        telefono="573009990021",
        activo=True,
    )
    curso = Curso.objects.create(nombre="Curso Destacado", cliente=cliente, activo=True)
    PlantillaCertificado.objects.create(
        nombre="Plantilla Hero Curso",
        curso=curso,
        cliente=cliente,
        modo_plantilla='diseno_eki',
        activa=True,
        verificacion_hero='curso',
        verificacion_tamano_hero='xl',
        verificacion_mostrar_hash=False,
    )
    est = Estudiante.objects.create(
        cedula="333333333",
        nombre="Luis Hero",
        telefono="573009990022",
        cliente=cliente,
        estado_chat="ACTIVO",
        acepto_terminos=True,
        activo=True,
    )
    Certificado.objects.create(
        estudiante=est,
        curso=curso,
        calificacion_final=95,
        fecha_inicio="2026-01-01",
        fecha_completado="2026-02-01",
        emitido=True,
        fecha_emision=timezone.now(),
        codigo_verificacion="eki-TEST-HERO-0001",
    )
    r = Client().get("/verificar-certificado/eki-TEST-HERO-0001/")
    assert r.status_code == 200
    assert b"hero-xl" in r.content
    assert b"Curso Destacado" in r.content
    # Título hero = curso; el nombre del estudiante sigue en meta/lede
    assert b"<h1 class=\"hero-xl\">Curso Destacado</h1>" in r.content
