"""Corte 3: stickers del lienzo, sin manchas RGB de Canva."""
from __future__ import annotations

import json
from io import BytesIO

import numpy as np
import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse
from PIL import Image

from core.certificados.utils_certificados import (
    generar_certificado_marcadores,
    resolver_layout_stickers,
)
from core.models_certificados import PlantillaCertificado

URL = 'https://certificados.eki.technology/verificar-certificado/EKI-STICKER/'

LAYOUT = {
    'nombre': {'x': 300, 'y': 80},
    'cedula': {'x': 300, 'y': 140},
    'fecha': {'x': 300, 'y': 190},
    'qr': {'x': 500, 'y': 320, 'lado': 80},
}


def _png_blanco(size=(600, 420)) -> bytes:
    buf = BytesIO()
    Image.new('RGB', size, (255, 255, 255)).save(buf, format='PNG')
    return buf.getvalue()


def test_resolver_vacio_usa_rgb():
    assert resolver_layout_stickers(None) is None
    assert resolver_layout_stickers({}) is None
    assert resolver_layout_stickers({'nombre': {'x': 1, 'y': 1}}) is None


def test_resolver_completo():
    out = resolver_layout_stickers(LAYOUT)
    assert out['nombre'] == {'x': 300, 'y': 80}
    assert out['qr']['lado'] == 80


def test_stickers_pintan_sin_manchas_rgb():
    out = generar_certificado_marcadores(
        plantilla_bytes=_png_blanco(),
        nombre_estudiante='Ana Sticker',
        cedula_estudiante='1020304050',
        url_verificacion=URL,
        layout=LAYOUT,
        ajuste_qr_y=0,
    )
    img = Image.open(out).convert('RGB')
    assert img.size == (600, 420)
    crop = np.array(img.crop((460, 280, 540, 360)))
    assert crop.min() < 40
    assert crop.max() > 200


def test_sin_layout_sigue_exigiendo_marcador_qr():
    with pytest.raises(ValueError, match='marcador'):
        generar_certificado_marcadores(
            plantilla_bytes=_png_blanco(),
            nombre_estudiante='X',
            cedula_estudiante='1',
            url_verificacion=URL,
        )


@pytest.mark.django_db
def test_preview_admin_usa_stickers():
    user_model = get_user_model()
    staff = user_model.objects.create_user(
        username='staff-stickers',
        password='test12345',
        is_staff=True,
        is_superuser=True,
    )
    plantilla = PlantillaCertificado.objects.create(
        nombre='Lienzo stickers',
        modo_plantilla='imagen',
        activa=True,
    )
    client = Client()
    client.force_login(staff)
    url = reverse('admin:learning_plantillacertificado_preview')
    response = client.post(
        url,
        {
            'modo_plantilla': 'imagen',
            'plantilla_id': str(plantilla.pk),
            'layout_stickers': json.dumps(LAYOUT),
            'archivo_plantilla_imagen': SimpleUploadedFile(
                'fondo.png', _png_blanco(), content_type='image/png',
            ),
        },
        secure=True,
    )
    assert response.status_code == 200
    assert response['Content-Type'] == 'image/png'
    img = Image.open(BytesIO(response.content)).convert('RGB')
    # El fallback de preview pinta un banner (15, 23, 42) arriba. Stickers no.
    assert img.getpixel((10, 10)) != (15, 23, 42)
    crop = np.array(img.crop((460, 280, 540, 360)))
    assert crop.min() < 40


@pytest.mark.django_db
def test_admin_change_form_tiene_lienzo_click():
    user_model = get_user_model()
    staff = user_model.objects.create_user(
        username='staff-stickers-form',
        password='test12345',
        is_staff=True,
        is_superuser=True,
    )
    plantilla = PlantillaCertificado.objects.create(
        nombre='Lienzo form',
        modo_plantilla='imagen',
        activa=True,
    )
    client = Client()
    client.force_login(staff)
    response = client.get(
        reverse('admin:learning_plantillacertificado_change', args=[plantilla.pk]),
        secure=True,
    )
    assert response.status_code == 200
    body = response.content.decode('utf-8')
    assert 'data-sticker' in body
    assert 'id_layout_stickers' in body
    assert 'Borrar posiciones' in body
    assert 'Marcadores disponibles' in body

