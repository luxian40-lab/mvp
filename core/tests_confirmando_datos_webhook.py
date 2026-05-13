"""Regresión: confirmación de datos debe enviar el curso (no el mensaje genérico de excepción)."""
import sys
from contextlib import nullcontext
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest
from django.test import Client, override_settings

from core.models import Cliente, Curso, Estudiante, Modulo, ProgresoEstudiante

pytestmark = pytest.mark.django_db


def _install_twilio_rest_stub(client_class):
    """Permite cargar core.views sin el paquete twilio instalado (CI / entornos mínimos)."""
    root = sys.modules.get("twilio") or ModuleType("twilio")
    rest = sys.modules.get("twilio.rest") or ModuleType("twilio.rest")
    rest.Client = client_class
    sys.modules.setdefault("twilio", root)
    sys.modules["twilio.rest"] = rest


@override_settings(SECURE_SSL_REDIRECT=False)
def test_webhook_confirmando_datos_con_progreso_incluye_modulo_no_fallback_generico():
    cliente = Cliente.objects.create(
        nombre="eki",
        contacto_principal="Ops",
        email="ops@eki.test",
        telefono="573001111111",
        usar_gamificacion=True,
    )
    curso = Curso.objects.create(
        nombre="Curso campaña",
        descripcion="Prueba",
        activo=True,
        cliente=None,
    )
    modulo = Modulo.objects.create(
        curso=curso,
        numero=1,
        titulo="Intro",
        descripcion="Desc",
        contenido="Contenido del módulo uno para el test.",
        duracion_dias=1,
    )
    tel = "573009988776"
    est = Estudiante.objects.create(
        cedula="3026480629",
        nombre="Julián Test",
        telefono=tel,
        cliente=cliente,
        estado_chat="CONFIRMANDO_DATOS",
        acepto_terminos=True,
    )
    ProgresoEstudiante.objects.create(
        estudiante=est,
        curso=curso,
        completado=False,
    )

    create_mock = MagicMock()

    class FakeTwilioClient:
        def __init__(self, *args, **kwargs):
            self.messages = MagicMock()
            self.messages.create = create_mock

    twilio_ctx = nullcontext()
    try:
        import twilio.rest  # noqa: F401

        twilio_ctx = patch("twilio.rest.Client", FakeTwilioClient)
    except ImportError:
        _install_twilio_rest_stub(FakeTwilioClient)

    with twilio_ctx:
        c = Client()
        resp = c.post(
            "/webhook/whatsapp/",
            {
                "From": f"whatsapp:+{tel}",
                "To": "whatsapp:+573202948806",
                "Body": "confirmar",
                "MessageSid": "SM_confirm_test_001",
                "NumMedia": "0",
            },
        )

    assert resp.status_code == 200
    bodies = []
    for call in create_mock.call_args_list:
        kw = call.kwargs or {}
        args = call.args or ()
        body = kw.get("body") if "body" in kw else (args[0] if args else None)
        if body:
            bodies.append(body)
    joined = "\n".join(b for b in bodies if b)
    assert "Tu organización te notificará cuando estén listos los cursos" not in joined
    assert "Módulo 1" in joined or "primer módulo" in joined.lower()
    assert modulo.titulo in joined or "Intro" in joined
