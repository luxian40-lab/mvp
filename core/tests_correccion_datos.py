import pytest

from core.correccion_datos import (
    iniciar_flujo_correccion,
    normalizar_texto,
    procesar_flujo_correccion,
)
from core.models import Cliente, Estudiante, SolicitudSoporte


@pytest.mark.django_db
def test_normalizar_texto_menu_con_tilde():
    assert normalizar_texto("Menú") == "menu"


@pytest.mark.django_db
def test_flujo_correccion_nombre_actualiza_y_audita():
    cliente = Cliente.objects.create(
        nombre="Cliente Test",
        nit="900123123-1",
        contacto_principal="Admin Test",
        email="admin@test.com",
        telefono="573001112233",
        activo=True,
    )
    est = Estudiante.objects.create(
        cedula="123456789",
        nombre="Nombre Viejo",
        telefono="573001110000",
        cliente=cliente,
        estado_chat="ACTIVO",
        estado_onboarding="completado",
        acepto_terminos=True,
        activo=True,
    )

    msg_inicio = iniciar_flujo_correccion(est)
    assert "Correccion de datos" in msg_inicio

    msg_opcion = procesar_flujo_correccion(est, "1")
    assert "nombre completo" in msg_opcion.lower()

    msg_final = procesar_flujo_correccion(est, "Pedro Perez")
    est.refresh_from_db()
    assert est.nombre == "Pedro Perez"
    assert "escribe *listo*" in msg_final.lower()
    assert est.contexto_temporal is None
    assert SolicitudSoporte.objects.filter(estudiante=est, keyword_usada="autocorreccion").exists()


@pytest.mark.django_db
def test_flujo_correccion_valida_opcion():
    cliente = Cliente.objects.create(
        nombre="Cliente Test 2",
        nit="900123123-2",
        contacto_principal="Admin Test",
        email="admin2@test.com",
        telefono="573001112234",
        activo=True,
    )
    est = Estudiante.objects.create(
        cedula="123456788",
        nombre="Nombre Test",
        telefono="573001110001",
        cliente=cliente,
        estado_chat="ACTIVO",
        estado_onboarding="completado",
        acepto_terminos=True,
        activo=True,
    )
    iniciar_flujo_correccion(est)
    msg = procesar_flujo_correccion(est, "9")
    assert "1, 2 o 3" in msg
