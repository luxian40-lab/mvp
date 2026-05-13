"""Campañas: reglas de destinatarios y ejecución del servicio."""
from unittest.mock import patch

from django.test import TestCase

from core.models import Campana, Cliente, Estudiante, Plantilla
from core.services import ejecutar_campana_servicio


class CampanaSinDestinatariosTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            nombre='Org Test',
            contacto_principal='a',
            email='a@example.com',
            telefono='573000000001',
        )
        self.plantilla = Plantilla.objects.create(
            nombre_interno='p1',
            cuerpo_mensaje='Hola {nombre}',
        )
        self.est_in_cliente = Estudiante.objects.create(
            cedula='88776655',
            nombre='En cliente',
            telefono='573009991010',
            cliente=self.cliente,
            activo=True,
        )

    def test_individual_sin_destinatarios_no_llama_envio_ni_incluye_alumnos_del_cliente(self):
        campana = Campana.objects.create(
            nombre='Solo vacía',
            cliente=self.cliente,
            plantilla=self.plantilla,
            tipo_audiencia='individual',
        )
        with patch('core.services.enviar_whatsapp_twilio') as send:
            res = ejecutar_campana_servicio(campana)
            send.assert_not_called()
        self.assertEqual(res['total'], 0)
        self.assertEqual(res['exitosos'], 0)
