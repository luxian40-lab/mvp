"""Cortes de la línea: envío, puerta, identidad, paso, reto y PQRS."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase


class CortesLineaTests(SimpleTestCase):
    def test_respuesta_de_curso_sale_por_meta_y_no_por_twilio(self):
        from core.lineas.envio import enviar_respuesta_linea

        with patch('core.lineas.envio.enviar_meta', return_value={'success': True}) as meta:
            enviar_respuesta_linea('573001110001', 'Su módulo sigue.', agente='curso')
        meta.assert_called_once()
        self.assertEqual(meta.call_args.args[1], 'Su módulo sigue.')
        self.assertEqual(meta.call_args.kwargs['agente_evento'], 'curso')

    def test_enviar_meta_vive_en_lineas(self):
        from core.lineas import enviar_meta as en_paquete
        from core.lineas.envio import enviar_meta as en_envio
        from core.sandbox_canal import enviar_meta as en_canal

        self.assertIs(en_envio, en_canal)
        self.assertIs(en_envio, en_paquete)

    def test_menu_de_producto_es_el_de_la_linea(self):
        from core.lineas.menu import dispatch_sandbox_menu
        from core.sandbox_menu import dispatch_sandbox_menu as en_menu

        self.assertIs(dispatch_sandbox_menu, en_menu)

    def test_habeas_se_corta_fuera_del_cuerpo(self):
        from core.lineas.identidad import cortar_habeas_meta
        from core.views.webhook_twilio import _cortar_habeas_meta

        self.assertIs(cortar_habeas_meta, _cortar_habeas_meta)

    def test_curso_meta_entra_por_la_puerta(self):
        from core.lineas.curso import procesar_curso_meta

        with patch('core.views.webhook_twilio._procesar_twilio_webhook', return_value=None) as puerta:
            procesar_curso_meta({'Body': 'listo'})
        puerta.assert_called_once()

    def test_aviso_de_entrega_no_entra_al_curso(self):
        from core.views.webhook_twilio import _procesar_twilio_webhook

        data = {
            'From': 'whatsapp:+573001110001',
            'To': 'whatsapp:+573202948806',
            'Body': '',
            'MessageSid': 'SMestado1',
            'MessageStatus': 'delivered',
            'SmsStatus': 'delivered',
        }
        with patch('core.views.webhook_twilio._procesar_twilio_webhook_cuerpo') as cuerpo, \
                patch('core.views.webhook_twilio._registrar_estado_twilio_callback') as registro:
            self.assertIsNone(_procesar_twilio_webhook(data))
        cuerpo.assert_not_called()
        registro.assert_called_once()

    def test_diploma_pendiente_no_entra_al_curso(self):
        from core.views.webhook_twilio import _procesar_twilio_webhook

        est = SimpleNamespace(
            telefono='573001110009',
            contexto_temporal={'cert_envio_pendiente': {'certificado_id': 1}},
        )
        data = {
            '_eki_proveedor': 'meta',
            'From': 'whatsapp:+573001110009',
            'To': 'whatsapp:+14155238886',
            'Body': 'ok',
            'MessageSid': 'wamid.diploma1',
        }
        with patch('core.utils_telefono.estudiante_por_telefono', return_value=est), \
                patch(
                    'core.views.certificados_wa._intentar_responder_envio_certificado',
                    return_value=True,
                ) as diploma, \
                patch('core.views.webhook_twilio._procesar_twilio_webhook_cuerpo') as cuerpo:
            self.assertIsNone(_procesar_twilio_webhook(data))
        diploma.assert_called_once()
        cuerpo.assert_not_called()

    def test_el_cuerpo_no_vuelve_a_crecer(self):
        from pathlib import Path

        texto = Path('core/views/webhook_twilio.py').read_text(encoding='utf-8').splitlines()
        inicio = next(
            n for n, linea in enumerate(texto)
            if linea.startswith('def _procesar_twilio_webhook_cuerpo')
        )
        self.assertLessEqual(len(texto) - inicio, 3226)


class EntregaMarcadaTests(TestCase):
    def test_confirmacion_plana_usa_un_create(self):
        from core.lineas.entrega import enviar_marcado

        cliente = MagicMock()
        with patch('twilio.rest.Client', return_value=cliente):
            enviar_marcado('whatsapp:+573001110001', '573001110001', 'Módulo 1', registro='segmentos')
        cliente.messages.create.assert_called_once()
        self.assertEqual(cliente.messages.create.call_args.kwargs['body'], 'Módulo 1')

    def test_seleccion_con_marcas_no_arma_el_cliente_en_el_cuerpo(self):
        from core.lineas.entrega import enviar_marcado

        enviado = MagicMock(return_value=[(SimpleNamespace(sid='SM1'), 'Intro')])
        with patch('twilio.rest.Client', return_value=MagicMock()), \
                patch('core.views.twilio_transporte._enviar_mensaje_twilio_segmentado', enviado):
            enviar_marcado(
                'whatsapp:+573001110001',
                '573001110001',
                '[MULTI_MSG]Intro[SEP][MEDIA:https://cdn.example.com/a.jpg]',
                registro='cierre',
            )
        medias = [call.kwargs['media_url'] for call in enviado.call_args_list]
        self.assertIn('https://cdn.example.com/a.jpg', medias)
