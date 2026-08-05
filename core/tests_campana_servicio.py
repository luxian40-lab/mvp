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


class CampanaAvisoClasesInscribeSinHabeasTests(TestCase):
    """10x / informativo: curso_destino + es_campana_curso=False → inscrito, sin reset Habeas."""

    def setUp(self):
        from core.models import Curso, ProgresoEstudiante

        self.ProgresoEstudiante = ProgresoEstudiante
        self.cliente = Cliente.objects.create(
            nombre='Org 10x',
            contacto_principal='a',
            email='10x@example.com',
            telefono='573000000099',
        )
        self.curso = Curso.objects.create(
            nombre='10x test campana',
            descripcion='d',
            cliente=self.cliente,
            modo_aula=Curso.MODO_AULA_CLASES,
            usar_gamificacion=False,
        )
        self.est = Estudiante.objects.create(
            cedula='10X0001',
            nombre='Piloto Diez',
            telefono='573026480629',
            cliente=self.cliente,
            activo=True,
            acepto_terminos=True,
            estado_onboarding='completado',
            estado_chat='ACTIVO',
        )
        self.campana = Campana.objects.create(
            nombre='Aviso 10x',
            cliente=self.cliente,
            template_twilio_id='HXtestaviso10x',
            es_campana_curso=False,
            curso_destino=self.curso,
            tipo_audiencia='individual',
        )
        self.campana.destinatarios.add(self.est)

    @patch('core.whatsapp_service.enviar_template_twilio')
    def test_inscribe_sin_reiniciar_habeas(self, mock_send):
        mock_send.return_value = {'success': True, 'mensaje_id': 'SM1'}
        res = ejecutar_campana_servicio(self.campana)
        self.assertEqual(res['exitosos'], 1)
        self.est.refresh_from_db()
        self.assertEqual(self.est.estado_chat, 'ACTIVO')
        self.assertTrue(self.est.acepto_terminos)
        self.assertEqual(self.est.estado_onboarding, 'completado')
        self.assertTrue(
            self.ProgresoEstudiante.objects.filter(
                estudiante=self.est, curso=self.curso
            ).exists()
        )
        mock_send.assert_called_once()
        args, kwargs = mock_send.call_args
        self.assertEqual(kwargs.get('content_sid') or args[1], 'HXtestaviso10x')
