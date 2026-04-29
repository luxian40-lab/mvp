import pytest

from core.models import Cliente, Curso, Estudiante
from core.models_certificados import Certificado


@pytest.mark.django_db
def test_obtener_url_verificacion_usa_portal_netlify():
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
    )
    url = cert.obtener_url_verificacion()
    assert url.startswith("https://certificadosseki.netlify.app/")
    assert "?code=" in url
    assert cert.codigo_verificacion in url
