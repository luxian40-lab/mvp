"""Corte 5: el HD vive en verify / Aprende, no en el globo de WhatsApp."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from django.test import Client, override_settings
from django.utils import timezone

from core.certificado_service import enviar_certificado_whatsapp, texto_descarga_alta_calidad
from core.models import Cliente, Curso, Estudiante
from core.models_certificados import Certificado


def _org_curso_est():
    cliente = Cliente.objects.create(
        nombre='Org HD',
        nit='900111222-3',
        contacto_principal='A',
        email='hd@test.com',
        telefono='573001110001',
        activo=True,
    )
    curso = Curso.objects.create(nombre='Curso HD', cliente=cliente, activo=True)
    est = Estudiante.objects.create(
        cedula='1099887766',
        nombre='Ana HD',
        telefono='573001110002',
        cliente=cliente,
        activo=True,
        acepto_terminos=True,
    )
    return cliente, curso, est


@pytest.mark.django_db
def test_texto_descarga_alta_calidad_apunta_a_verify():
    _, curso, est = _org_curso_est()
    cert = Certificado.objects.create(
        estudiante=est,
        curso=curso,
        calificacion_final=91,
        fecha_inicio='2026-01-01',
        fecha_completado='2026-02-01',
        emitido=True,
        fecha_emision=timezone.now(),
        codigo_verificacion='eki-TEST-HDCOPY-01',
    )
    texto = texto_descarga_alta_calidad(cert)
    assert 'alta calidad' in texto.lower()
    assert cert.obtener_url_verificacion() in texto


@pytest.mark.django_db
@override_settings(
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
    SECURE_SSL_REDIRECT=False,
)
def test_ficha_publica_ofrece_alta_calidad():
    _, curso, est = _org_curso_est()
    Certificado.objects.create(
        estudiante=est,
        curso=curso,
        calificacion_final=91,
        fecha_inicio='2026-01-01',
        fecha_completado='2026-02-01',
        emitido=True,
        fecha_emision=timezone.now(),
        codigo_verificacion='eki-TEST-HDCOPY-02',
        hash_sha256='a' * 64,
    )
    with patch('core.certificado_service.asegurar_pdf_certificado', return_value=False):
        r = Client().get('/verificar-certificado/eki-TEST-HDCOPY-02/')
    assert r.status_code == 200
    body = r.content.decode('utf-8')
    assert 'alta calidad' in body.lower()
    assert '/descargar-certificado/eki-TEST-HDCOPY-02/' in body


@pytest.mark.django_db
@patch('core.certificado_service._media_url_certificado', return_value='https://eki-produccion.s3.amazonaws.com/cert.png')
@patch('core.views.diploma_meta.enviar_diploma_plantilla_meta', return_value=None)
@patch('core.certificado_service._intentar_enviar_imagen_diploma', return_value=({'success': True}, 'imagen'))
def test_caption_whatsapp_pide_alta_calidad(imagen, _plantilla, _url):
    _, curso, est = _org_curso_est()
    cert = Certificado.objects.create(
        estudiante=est,
        curso=curso,
        calificacion_final=91,
        fecha_inicio='2026-01-01',
        fecha_completado='2026-02-01',
        emitido=True,
        fecha_emision=timezone.now(),
        codigo_verificacion='eki-TEST-HDCOPY-03',
        archivo_imagen='certificados/generados/hd.png',
    )
    assert enviar_certificado_whatsapp(cert) is True
    caption = imagen.call_args.kwargs.get('caption') or ''
    assert 'certificado digital está listo' in caption.lower()
    assert 'alta calidad' in caption.lower()
    assert cert.obtener_url_verificacion() in caption
    assert 'eki-produccion.s3.amazonaws.com/cert.png' not in caption
