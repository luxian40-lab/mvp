from unittest.mock import patch

import pytest

pytest.importorskip("twilio")

from core.models import Cliente, ConfiguracionGlobal
from core.whatsapp_service import enviar_habeas_data


pytestmark = pytest.mark.django_db


def _cliente(**kwargs):
    base = {
        "nombre": "Cliente Test",
        "contacto_principal": "Ops",
        "email": "ops@test.co",
        "telefono": "573001111111",
    }
    base.update(kwargs)
    return Cliente.objects.create(**base)


@patch("core.whatsapp_service.enviar_template_twilio")
def test_habeas_template_prefiere_sid_cliente(mock_send):
    cliente = _cliente(content_sid_habeas_data_twilio="HXCLIENTE001")
    ConfiguracionGlobal.get_solo().save()

    mock_send.return_value = {"success": True, "mensaje_id": "SM1", "response": "ok"}
    enviar_habeas_data("573009999999", cliente=cliente)

    mock_send.assert_called_once_with("573009999999", "HXCLIENTE001")


@patch("core.whatsapp_service.enviar_template_twilio")
def test_habeas_template_usa_global_si_cliente_vacio(mock_send):
    cliente = _cliente(content_sid_habeas_data_twilio="")
    cfg = ConfiguracionGlobal.get_solo()
    cfg.content_sid_habeas_data_global = "HXGLOBAL001"
    cfg.save(update_fields=["content_sid_habeas_data_global", "fecha_actualizacion"])

    mock_send.return_value = {"success": True, "mensaje_id": "SM2", "response": "ok"}
    enviar_habeas_data("573008888888", cliente=cliente)

    mock_send.assert_called_once_with("573008888888", "HXGLOBAL001")
