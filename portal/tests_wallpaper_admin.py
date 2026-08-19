"""Admin Cliente: subida clara de wallpaper Aprende."""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.test.utils import override_settings

from core.models import Cliente
from portal.forms import ClientePortalAdminForm
from portal.utils import guardar_logo_organizacion, guardar_wallpaper_aula

pytestmark = pytest.mark.django_db


def _png_bytes() -> bytes:
    return (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
        b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00'
        b'\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
    )


@override_settings(SECURE_SSL_REDIRECT=False)
def test_admin_cliente_muestra_fieldset_wallpaper():
    User = get_user_model()
    User.objects.create_superuser('walladmin', 'w@e.co', 'pass')
    cli = Cliente.objects.create(
        nombre='Org Wallpaper',
        contacto_principal='C',
        email='w@example.com',
        telefono='573009990001',
    )

    http = Client()
    assert http.login(username='walladmin', password='pass')
    r = http.get(f'/admin/core/cliente/{cli.pk}/change/', HTTP_HOST='127.0.0.1')
    assert r.status_code == 200
    assert b'Aula Aprende' in r.content
    assert b'wallpaper_archivo' in r.content
    assert b'Subir imagen de fondo' in r.content
    assert 'wallpaper_archivo' in ClientePortalAdminForm.base_fields
    assert b'logo_archivo' in r.content
    assert b'Subir logo' in r.content
    assert 'logo_archivo' in ClientePortalAdminForm.base_fields


def test_guardar_logo_organizacion_escribe_url(tmp_path, settings):
    settings.STORAGES = {
        'default': {
            'BACKEND': 'django.core.files.storage.FileSystemStorage',
            'OPTIONS': {'location': str(tmp_path)},
        },
        'staticfiles': {
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    }
    settings.MEDIA_URL = '/media/'
    cli = Cliente.objects.create(
        nombre='Org Logo FS',
        contacto_principal='C',
        email='lg@example.com',
        telefono='573009990003',
    )
    url = guardar_logo_organizacion(
        SimpleUploadedFile('logo-org.png', _png_bytes(), content_type='image/png'),
        cli.pk,
    )
    assert url
    assert 'logos' in url
    assert 'logo-org' in url


@override_settings(
    SECURE_SSL_REDIRECT=False,
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
    MEDIA_ROOT='/tmp/eki_test_media_logo',
)
def test_admin_cliente_subir_logo_actualiza_logo_url(tmp_path, settings):
    settings.MEDIA_ROOT = str(tmp_path)
    User = get_user_model()
    User.objects.create_superuser('logoadmin', 'l@e.co', 'pass')
    cli = Cliente.objects.create(
        nombre='Org Logo Upload',
        contacto_principal='C',
        email='lu@example.com',
        telefono='573009990004',
    )
    http = Client()
    assert http.login(username='logoadmin', password='pass')
    r = http.post(
        f'/admin/core/cliente/{cli.pk}/change/',
        {
            'nombre': cli.nombre,
            'contacto_principal': cli.contacto_principal,
            'email': cli.email,
            'telefono': cli.telefono,
            'activo': 'on',
            'tipo_proyecto': 'cursos',
            'modo_gamificacion': 'puntos',
            'cupos_portal': '5',
            'logo_archivo': SimpleUploadedFile(
                'marca.png', _png_bytes(), content_type='image/png',
            ),
        },
        HTTP_HOST='127.0.0.1',
    )
    assert r.status_code == 302, r.content[:500]
    cli.refresh_from_db()
    assert cli.logo_url
    assert 'logos' in cli.logo_url


def test_guardar_wallpaper_aula_escribe_url(tmp_path, settings):
    settings.STORAGES = {
        'default': {
            'BACKEND': 'django.core.files.storage.FileSystemStorage',
            'OPTIONS': {'location': str(tmp_path)},
        },
        'staticfiles': {
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    }
    settings.MEDIA_URL = '/media/'
    cli = Cliente.objects.create(
        nombre='Org Wallpaper FS',
        contacto_principal='C',
        email='wf@example.com',
        telefono='573009990002',
    )
    url = guardar_wallpaper_aula(
        SimpleUploadedFile('fondo-aprende.png', _png_bytes(), content_type='image/png'),
        cli.pk,
    )
    assert url
    assert 'wallpapers' in url
    assert 'fondo-aprende' in url
