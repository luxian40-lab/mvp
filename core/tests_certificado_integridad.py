"""Tests: PDF derivado, hash, verify enriquecido, anulación."""
from __future__ import annotations

from io import BytesIO
from unittest.mock import patch

import pytest
from django.test import Client, override_settings
from django.utils import timezone
from PIL import Image

from core.certificado_service import (
    hash_sha256_buffer,
    organizacion_emisora_de,
    png_buffer_a_pdf,
    verificar_certificado_publico,
)
from core.models import Cliente, Curso, Estudiante
from core.models_certificados import Certificado


pytestmark = pytest.mark.django_db


def _png_buf():
    img = Image.new('RGB', (400, 300), color=(255, 255, 255))
    buf = BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf


def test_png_buffer_a_pdf_genera_pdf_valido():
    pdf = png_buffer_a_pdf(_png_buf())
    data = pdf.read()
    assert data[:4] == b'%PDF'
    assert len(data) > 100


def test_hash_sha256_estable():
    buf = _png_buf()
    h1 = hash_sha256_buffer(buf)
    h2 = hash_sha256_buffer(buf)
    assert h1 == h2
    assert len(h1) == 64


def test_organizacion_usa_nombre_cliente_no_contacto():
    cliente = Cliente.objects.create(
        nombre='Fundación Campo',
        nit='900111222-3',
        contacto_principal='Juan Contacto',
        email='c@x.co',
        telefono='573001111111',
        activo=True,
    )
    curso = Curso.objects.create(nombre='C1', cliente=cliente, activo=True, duracion_semanas=5)
    est = Estudiante.objects.create(
        cedula='1234567890',
        nombre='Prod Demo',
        telefono='573001112222',
        cliente=cliente,
        activo=True,
        acepto_terminos=True,
    )
    cert = Certificado(
        estudiante=est,
        curso=curso,
        calificacion_final=92,
        fecha_inicio='2026-01-01',
        fecha_completado='2026-02-01',
    )
    assert organizacion_emisora_de(cert) == 'Fundación Campo'
    assert cert.cedula_enmascarada() == '******7890'
    assert cert.horas_estimadas_curso() == 20


@override_settings(SECURE_SSL_REDIRECT=False)
def test_verificar_publico_metadatos_y_anulado():
    cliente = Cliente.objects.create(
        nombre='Org Cert',
        nit='900222333-4',
        contacto_principal='X',
        email='o@x.co',
        telefono='573002222222',
        activo=True,
    )
    curso = Curso.objects.create(
        nombre='Agro Avanzado', cliente=cliente, activo=True, duracion_semanas=4,
    )
    est = Estudiante.objects.create(
        cedula='9876543210',
        nombre='Luisa Campo',
        telefono='573003333333',
        cliente=cliente,
        activo=True,
        acepto_terminos=True,
    )
    cert = Certificado.objects.create(
        estudiante=est,
        curso=curso,
        calificacion_final=96,
        fecha_inicio='2026-01-01',
        fecha_completado='2026-03-01',
        emitido=True,
        fecha_emision=timezone.now(),
        codigo_verificacion='eki-TEST-META-0001',
        organizacion_emisora='Org Cert',
        hash_sha256='a' * 64,
    )
    with patch('core.certificado_service.asegurar_pdf_certificado', return_value=False):
        data = verificar_certificado_publico('eki-TEST-META-0001')
    assert data['valido'] is True
    assert data['organizacion'] == 'Org Cert'
    assert data['cedula_enmascarada'].endswith('3210')
    assert data['horas_estimadas'] == 16
    assert data['hash_sha256'] == 'a' * 64
    assert not data.get('mencion')
    assert data.get('descarga_url')

    cert.anulado = True
    cert.motivo_anulacion = 'Error de emisión'
    cert.save(update_fields=['anulado', 'motivo_anulacion'])
    data2 = verificar_certificado_publico('eki-TEST-META-0001')
    assert data2['valido'] is False
    assert data2.get('anulado') is True

    http = Client()
    r = http.get('/verificar-certificado/eki-TEST-META-0001/')
    assert r.status_code == 404


@override_settings(
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
    SECURE_SSL_REDIRECT=False,
)
def test_pagina_verificar_muestra_org_y_descarga():
    cliente = Cliente.objects.create(
        nombre='Sponsor Verde',
        nit='900333444-5',
        contacto_principal='Y',
        email='s@x.co',
        telefono='573004444444',
        activo=True,
    )
    curso = Curso.objects.create(nombre='Curso Verde', cliente=cliente, activo=True)
    est = Estudiante.objects.create(
        cedula='5555666677',
        nombre='Ana Verde',
        telefono='573005555555',
        cliente=cliente,
        activo=True,
        acepto_terminos=True,
    )
    Certificado.objects.create(
        estudiante=est,
        curso=curso,
        calificacion_final=88,
        fecha_inicio='2026-01-01',
        fecha_completado='2026-02-01',
        emitido=True,
        fecha_emision=timezone.now(),
        codigo_verificacion='eki-TEST-PAGE-0002',
        organizacion_emisora='Sponsor Verde',
        hash_sha256='b' * 64,
    )
    with patch('core.certificado_service.asegurar_pdf_certificado', return_value=False):
        http = Client()
        r = http.get('/verificar-certificado/eki-TEST-PAGE-0002/')
    assert r.status_code == 200
    assert b'Sponsor Verde' in r.content
    assert b'Ana Verde' in r.content
    assert b'SHA-256' in r.content or b'sha-256' in r.content.lower()
