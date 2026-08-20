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


def _cliente_admin_post_base(cli: Cliente) -> dict:
    return {
        'nombre': cli.nombre,
        'contacto_principal': cli.contacto_principal,
        'email': cli.email,
        'telefono': cli.telefono,
        'activo': 'on',
        'tipo_proyecto': cli.tipo_proyecto or 'cursos',
        'modo_gamificacion': cli.modo_gamificacion or 'puntos',
        'cupos_portal': str(cli.cupos_portal or 5),
        'modo_avance_modulo': cli.modo_avance_modulo or 'texto',
        'nota_minima_certificado': str(cli.nota_minima_certificado or 3),
        'empleabilidad_radio_metros': str(cli.empleabilidad_radio_metros or 800),
        'empleabilidad_cooldown_horas': str(cli.empleabilidad_cooldown_horas or 24),
        'empleabilidad_max_misiones_dia': str(cli.empleabilidad_max_misiones_dia or 3),
        'empleabilidad_puntos_validacion': str(cli.empleabilidad_puntos_validacion or 30),
    }


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


def test_cliente_admin_save_model_sube_logo(tmp_path, settings):
    from django.contrib.admin.sites import AdminSite
    from django.test import RequestFactory

    from core.admin.clientes import ClienteAdmin

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
        nombre='Org SaveModel',
        contacto_principal='C',
        email='sm@example.com',
        telefono='573009990006',
    )
    form = ClientePortalAdminForm(
        data={**_cliente_admin_post_base(cli)},
        files={
            'logo_archivo': SimpleUploadedFile(
                'sm-logo.png', _png_bytes(), content_type='image/png',
            ),
        },
        instance=cli,
    )
    assert form.is_valid(), form.errors
    obj = form.save(commit=False)
    admin = ClienteAdmin(Cliente, AdminSite())
    admin.save_model(RequestFactory().post('/'), obj, form, change=True)
    cli.refresh_from_db()
    assert cli.logo_url
    assert 'logos' in cli.logo_url


def test_form_save_commit_false_sube_logo(tmp_path, settings):
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
        nombre='Org CommitFalse',
        contacto_principal='C',
        email='cf@example.com',
        telefono='573009990005',
    )
    form = ClientePortalAdminForm(
        data={
            **_cliente_admin_post_base(cli),
        },
        files={
            'logo_archivo': SimpleUploadedFile(
                'cf-logo.png', _png_bytes(), content_type='image/png',
            ),
        },
        instance=cli,
    )
    assert form.is_valid(), form.errors
    obj = form.save(commit=False)
    assert not obj.logo_url
    form.sync_media_fields(obj)
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
