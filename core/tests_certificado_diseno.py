from io import BytesIO

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client
from django.urls import reverse
from PIL import Image

from core.certificado_diseno_eki import render_certificado_diseno_eki
from core.certificado_preview import generar_preview_certificado, plantilla_desde_request
from core.models import Cliente, Curso, Estudiante
from core.models_certificados import Certificado, PlantillaCertificado


@pytest.mark.django_db
def test_modo_efectivo_diseno_sin_imagen():
    p = PlantillaCertificado(
        nombre='Diseño test',
        modo_plantilla='diseno_eki',
        color_primario='#112233',
        color_secundario='#445566',
    )
    assert p.modo_efectivo() == 'diseno_eki'


@pytest.mark.django_db
def test_modo_imagen_requiere_url_o_archivo():
    p = PlantillaCertificado(nombre='Sin img', modo_plantilla='imagen')
    with pytest.raises(ValidationError):
        p.clean()


@pytest.mark.django_db
def test_render_diseno_eki_genera_png():
    p = PlantillaCertificado(
        nombre='Preview',
        modo_plantilla='diseno_eki',
        texto_superior='Org Demo',
        texto_certificado='CERTIFICADO TEST',
        color_primario='#1d4ed8',
        color_secundario='#059669',
    )
    buf = render_certificado_diseno_eki(plantilla=p)
    assert isinstance(buf, BytesIO)
    data = buf.getvalue()
    assert data[:8] == b'\x89PNG\r\n\x1a\n'
    assert len(data) > 5000


@pytest.mark.django_db
def test_generar_y_guardar_usa_diseno_eki(monkeypatch):
    cliente = Cliente.objects.create(
        nombre='Org Cert',
        contacto_principal='Director Demo',
        email='cert@test.com',
        telefono='573001100020',
        activo=True,
    )
    curso = Curso.objects.create(nombre='Curso Cert', descripcion='d', cliente=cliente, activo=True)
    est = Estudiante.objects.create(
        cedula='222222222',
        nombre='Estudiante Cert',
        telefono='573001100021',
        cliente=cliente,
        estado_chat='ACTIVO',
        activo=True,
    )
    plantilla = PlantillaCertificado.objects.create(
        nombre='Plantilla diseño',
        curso=curso,
        cliente=cliente,
        modo_plantilla='diseno_eki',
        activa=True,
    )
    cert = Certificado.objects.create(
        estudiante=est,
        curso=curso,
        calificacion_final=88,
        fecha_inicio='2026-01-01',
        fecha_completado='2026-02-01',
    )

    guardados = []

    def fake_guardar(certificado, img_buffer, label=''):
        guardados.append(label)
        certificado.archivo_imagen.name = f'certificados/test_{certificado.codigo_verificacion}.png'
        certificado.emitido = True
        return True

    monkeypatch.setattr('core.certificado_service._guardar_cert_s3', fake_guardar)

    from core.certificado_service import generar_y_guardar_certificado

    ok = generar_y_guardar_certificado(cert, plantilla=plantilla, force=True)
    assert ok is True
    assert guardados and 'Diseño eki' in guardados[0]


def _png_bytes(color=(200, 200, 200)) -> bytes:
    buf = BytesIO()
    Image.new('RGB', (400, 280), color).save(buf, format='PNG')
    return buf.getvalue()


@pytest.mark.django_db
def test_preview_diseno_eki_sin_guardar():
    plantilla = plantilla_desde_request({
        'modo_plantilla': 'diseno_eki',
        'color_primario': '#112233',
        'color_secundario': '#445566',
        'texto_superior': 'Org Preview',
        'texto_certificado': 'CERT PREVIEW',
    })
    buf = generar_preview_certificado(plantilla, post_data={'modo_plantilla': 'diseno_eki'})
    data = buf.getvalue()
    assert data[:8] == b'\x89PNG\r\n\x1a\n'
    assert len(data) > 3000


@pytest.mark.django_db
def test_preview_imagen_desde_bytes_sin_marcadores():
    plantilla = PlantillaCertificado(
        nombre='Img preview',
        modo_plantilla='imagen',
    )
    post = {'modo_plantilla': 'imagen'}
    files = {'archivo_plantilla_imagen': BytesIO(_png_bytes())}
    files['archivo_plantilla_imagen'].name = 'plantilla.png'
    buf = generar_preview_certificado(plantilla, post_data=post, files=files)
    data = buf.getvalue()
    assert data[:8] == b'\x89PNG\r\n\x1a\n'
    assert len(data) > 500


@pytest.mark.django_db
def test_admin_preview_endpoint_diseno_eki():
    user_model = get_user_model()
    staff = user_model.objects.create_user(
        username='staff-cert-preview',
        password='test12345',
        is_staff=True,
        is_superuser=True,
    )
    plantilla = PlantillaCertificado.objects.create(
        nombre='Plantilla admin preview',
        modo_plantilla='diseno_eki',
        color_primario='#1d4ed8',
        color_secundario='#059669',
    )
    client = Client()
    client.force_login(staff)
    url = reverse('admin:learning_plantillacertificado_preview')
    response = client.post(
        url,
        {
            'modo_plantilla': 'diseno_eki',
            'color_primario': '#1d4ed8',
            'color_secundario': '#059669',
            'texto_superior': 'eki demo',
            'texto_certificado': 'CERTIFICADO',
            'plantilla_id': str(plantilla.pk),
        },
        secure=True,
    )
    assert response.status_code == 200
    assert response['Content-Type'] == 'image/png'
    assert response.content[:8] == b'\x89PNG\r\n\x1a\n'


@pytest.mark.django_db
def test_admin_preview_con_estudiante_real():
    from core.models import Cliente, Estudiante

    user_model = get_user_model()
    staff = user_model.objects.create_user(
        username='staff-cert-est',
        password='test12345',
        is_staff=True,
        is_superuser=True,
    )
    cliente = Cliente.objects.create(
        nombre='Org Preview',
        contacto_principal='A',
        email='pv@test.com',
        telefono='573009999991',
        activo=True,
    )
    est = Estudiante.objects.create(
        cedula='pv1', nombre='Pedro Vista', telefono='573009999992', cliente=cliente, activo=True,
    )
    plantilla = PlantillaCertificado.objects.create(
        nombre='Plantilla con estudiante',
        modo_plantilla='diseno_eki',
        cliente=cliente,
        activa=True,
    )
    client = Client()
    client.force_login(staff)
    url = reverse('admin:learning_plantillacertificado_preview')
    response = client.post(
        url,
        {
            'modo_plantilla': 'diseno_eki',
            'plantilla_id': str(plantilla.pk),
            'estudiante_preview': str(est.pk),
        },
        secure=True,
    )
    assert response.status_code == 200
    assert response['Content-Type'] == 'image/png'


@pytest.mark.django_db
def test_admin_estudiantes_preview_json():
    from core.models import Cliente, Estudiante

    user_model = get_user_model()
    staff = user_model.objects.create_user(
        username='staff-cert-json',
        password='test12345',
        is_staff=True,
        is_superuser=True,
    )
    cliente = Cliente.objects.create(
        nombre='Org JSON',
        contacto_principal='A',
        email='js@test.com',
        telefono='573009999993',
        activo=True,
    )
    Estudiante.objects.create(
        cedula='js1', nombre='Ana JSON', telefono='573009999994', cliente=cliente, activo=True,
    )
    client = Client()
    client.force_login(staff)
    url = reverse('admin:learning_plantillacertificado_estudiantes_preview')
    response = client.get(url + f'?cliente={cliente.pk}', secure=True)
    assert response.status_code == 200
    data = response.json()
    assert len(data['estudiantes']) == 1
    assert data['estudiantes'][0]['nombre'] == 'Ana Json'


@pytest.mark.django_db
def test_obtener_url_plantilla_prioriza_archivo_sobre_url_vieja():
    """Al subir archivo nuevo, no debe ganar la URL antigua pegada en el campo."""
    from django.core.files.uploadedfile import SimpleUploadedFile

    png = _png_bytes()
    plantilla = PlantillaCertificado(
        nombre='Sync URL',
        modo_plantilla='imagen',
        url_plantilla_imagen='https://eki-produccion.s3.us-east-2.amazonaws.com/vieja/plantilla_antigua.png',
    )
    plantilla.archivo_plantilla_imagen = SimpleUploadedFile(
        'plantilla_nueva.png', png, content_type='image/png',
    )
    plantilla.save()
    plantilla.refresh_from_db()

    efectiva = plantilla.obtener_url_plantilla_imagen()
    assert efectiva
    assert 'vieja/plantilla_antigua' not in efectiva
    assert plantilla.url_plantilla_imagen == efectiva
    assert 'plantilla_nueva' in (plantilla.archivo_plantilla_imagen.name or '')


@pytest.mark.django_db
def test_reemplazo_archivo_actualiza_url_segunda_vez():
    """QA: segunda subida debe dejar de apuntar a la key de la primera."""
    from django.core.files.uploadedfile import SimpleUploadedFile

    from core.certificado_preview import _resolver_fuente_imagen

    p = PlantillaCertificado(
        nombre='Replace twice',
        modo_plantilla='imagen',
        url_plantilla_imagen='https://eki-produccion.s3.us-east-2.amazonaws.com/vieja/old.png',
    )
    p.archivo_plantilla_imagen = SimpleUploadedFile(
        'v1.png', _png_bytes(), content_type='image/png',
    )
    p.save()
    p.refresh_from_db()
    url1 = p.url_plantilla_imagen
    name1 = p.archivo_plantilla_imagen.name

    p.archivo_plantilla_imagen = SimpleUploadedFile(
        'v2.png', _png_bytes(), content_type='image/png',
    )
    # Simula formulario admin que reenvía URL vieja
    p.url_plantilla_imagen = url1
    p.save()
    p.refresh_from_db()

    assert p.archivo_plantilla_imagen.name != name1
    assert 'v2' in (plantilla_name := (p.archivo_plantilla_imagen.name or ''))
    assert p.obtener_url_plantilla_imagen() == p.url_plantilla_imagen
    assert url1 != p.url_plantilla_imagen
    assert 'vieja/old' not in (p.url_plantilla_imagen or '')

    kind, src = _resolver_fuente_imagen(p)
    assert kind in ('url', 'bytes')
    if kind == 'url':
        assert 'vieja/old' not in str(src)
        assert src == p.archivo_plantilla_imagen.url
    else:
        assert isinstance(src, (bytes, bytearray)) and len(src) > 50
