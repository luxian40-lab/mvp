"""Cortes de la línea: envío, puerta, identidad, paso, reto y PQRS."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase, override_settings


class CortesLineaTests(SimpleTestCase):
    def test_respuesta_de_curso_sale_por_meta_y_no_por_twilio(self):
        from core.lineas.envio import enviar_respuesta_linea

        with patch('core.lineas.envio.enviar_meta', return_value={'success': True}) as meta:
            enviar_respuesta_linea('573001110001', 'Su módulo sigue.', agente='curso')
        meta.assert_called_once()
        self.assertEqual(meta.call_args.args[1], 'Su módulo sigue.')
        self.assertEqual(meta.call_args.kwargs['agente_evento'], 'curso')

    def test_puerta_en_meta_no_abre_cliente_twilio(self):
        from core.lineas.salida_turno import enviar_respuesta_turno
        from core.canal.wa_canal import CANAL_META, canal_webhook

        with canal_webhook(CANAL_META), \
                patch('twilio.rest.Client') as cliente, \
                patch(
                    'core.lineas.envio.enviar_respuesta_linea',
                    return_value={'success': True, 'mensaje_id': 'wamid.tip'},
                ) as linea:
            enviar_respuesta_turno('573001110001', 'Pulse Continuar.', agente='puerta_leccion')
        cliente.assert_not_called()
        linea.assert_called_once()
        self.assertEqual(linea.call_args.kwargs['agente'], 'puerta_leccion')

    def test_menu_multimsg_en_meta_usa_entrega_marcada(self):
        from core.lineas.salida_turno import entregar_en_turno
        from core.canal.wa_canal import CANAL_META, canal_webhook

        with canal_webhook(CANAL_META), \
                patch('core.lineas.entrega.enviar_marcado') as marcado:
            entregar_en_turno(
                'whatsapp:+573001110001',
                '573001110001',
                '[MULTI_MSG]Hola[SEP]Sigue',
                agente='menu_curso',
            )
        marcado.assert_called_once()

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

    def test_turno_meta_el_video_sale_por_graph(self):
        from core.lineas.entrega import enviar_marcado
        from core.canal.wa_canal import CANAL_META, canal_webhook

        cliente = MagicMock()
        with canal_webhook(CANAL_META), \
                patch('twilio.rest.Client', return_value=cliente), \
                patch(
                    'core.sandbox_canal.enviar_meta',
                    return_value={'success': True, 'mensaje_id': 'wamid.video'},
                ) as meta:
            enviar_marcado(
                'whatsapp:+573001110001',
                '573001110001',
                '[MULTI_MSG]Mira[SEP][MEDIA:https://cdn.example.com/modulo.mp4]',
                registro='segmentos',
            )
        cliente.messages.create.assert_not_called()
        urls = [call.kwargs.get('media_url') for call in meta.call_args_list]
        self.assertIn('https://cdn.example.com/modulo.mp4', urls)

    def test_fallo_de_graph_no_cae_a_twilio(self):
        from core.lineas.entrega import enviar_marcado
        from core.canal.wa_canal import CANAL_META, canal_webhook

        cliente = MagicMock()
        with canal_webhook(CANAL_META), \
                patch('twilio.rest.Client', return_value=cliente), \
                patch('core.sandbox_canal.enviar_meta', side_effect=RuntimeError('graph')):
            enviar_marcado(
                'whatsapp:+573001110001',
                '573001110001',
                '[MEDIA:https://cdn.example.com/modulo.mp4]',
                registro='segmentos',
            )
        cliente.messages.create.assert_not_called()

    @override_settings(EKI_ENTREGA_DELAYS_CELERY=True)
    def test_pausa_en_meta_reencola_en_la_misma_linea(self):
        from core.lineas.entrega import enviar_marcado
        from core.canal.wa_canal import CANAL_META, canal_webhook

        with canal_webhook(CANAL_META), \
                patch(
                    'core.sandbox_canal.enviar_meta',
                    return_value={'success': True, 'mensaje_id': 'wamid.1'},
                ), \
                patch('celery.current_app.send_task') as tarea:
            enviar_marcado(
                'whatsapp:+573001110001',
                '573001110001',
                '[MULTI_MSG]Hola[SEP][DELAY:5][SEP][MEDIA:https://cdn.example.com/a.mp4]',
                registro='segmentos',
            )
        self.assertTrue(tarea.called)
        kwargs = tarea.call_args.kwargs['kwargs']
        self.assertTrue(kwargs.get('meta'))
        self.assertIn('phone_id', kwargs)
        self.assertEqual(kwargs.get('canal'), 'twilio_marcado')

    def test_turno_meta_no_dispara_plantilla_twilio(self):
        from core.lineas.entrega import enviar_marcado
        from core.canal.wa_canal import CANAL_META, canal_webhook

        with canal_webhook(CANAL_META), \
                patch(
                    'core.sandbox_canal.enviar_meta',
                    return_value={'success': True, 'mensaje_id': 'wamid.1'},
                ), \
                patch('core.whatsapp_service.enviar_template_twilio') as plantilla:
            enviar_marcado(
                'whatsapp:+573001110001',
                '573001110001',
                '[MULTI_MSG][SEND_TEMPLATE:HXabc123][SEP]Sigue el módulo',
                registro='segmentos',
            )
        plantilla.assert_not_called()

    def test_sin_canal_meta_la_plantilla_sigue_por_twilio(self):
        from core.lineas.entrega import enviar_marcado

        with patch('twilio.rest.Client', return_value=MagicMock()), \
                patch('core.whatsapp_service.enviar_template_twilio') as plantilla:
            enviar_marcado(
                'whatsapp:+573001110001',
                '573001110001',
                '[MULTI_MSG][SEND_TEMPLATE:HXabc123]',
                registro='segmentos',
            )
        plantilla.assert_called_once()


LINEAS = 'PN_UNO|+573000000001|Principal;PN_DOS|+573000000002|Segunda|cursos'


@override_settings(
    META_LINEAS=LINEAS,
    WHATSAPP_BUSINESS_ACCOUNT_ID='WABA_UNO',
    WHATSAPP_BUSINESS_ACCOUNT_ID_2='WABA_DOS',
)
class CursoPorSenderTests(TestCase):
    @patch('core.sandbox_canal.phone_id_de_salida', return_value='PN_DOS')
    @patch('core.lineas.envio.enviar_meta', return_value={'success': True, 'mensaje_id': 'wamid.curso'})
    def test_con_phone_id_sale_por_el_sender(self, meta, _pn):
        from core.lineas.envio import enviar_respuesta_linea

        r = enviar_respuesta_linea('573001110001', 'Su módulo sigue.', agente='curso', correlacion='leccion:1')
        self.assertTrue(r['success'])
        meta.assert_called_once()
        self.assertEqual(meta.call_args.kwargs['agente_evento'], 'curso')

    @patch('core.sandbox_canal.phone_id_de_salida', return_value='PN_DOS')
    @patch('core.lineas.envio.enviar_meta', return_value={'success': True, 'mensaje_id': 'wamid.curso'})
    def test_flag_apagado_no_escribe_outbox(self, _meta, _pn):
        from core.lineas.envio import enviar_respuesta_linea
        from core.models.outbox_envio import OutboxEnvio

        enviar_respuesta_linea('573001110001', 'Su módulo sigue.', correlacion='leccion:1')
        self.assertEqual(OutboxEnvio.objects.count(), 0)

    @override_settings(EKI_OUTBOX_ENVIO=True)
    @patch('core.sandbox_canal.phone_id_de_salida', return_value='PN_DOS')
    @patch('core.lineas.envio.enviar_meta', return_value={'success': True, 'mensaje_id': 'wamid.curso'})
    def test_turno_meta_pasa_por_sender_y_outbox(self, _meta, _pn):
        from core.lineas.salida_turno import enviar_respuesta_turno
        from core.models.outbox_envio import OutboxEnvio
        from core.canal.wa_canal import CANAL_META, canal_webhook

        with canal_webhook(CANAL_META):
            enviar_respuesta_turno(
                '573001110001',
                'Su módulo sigue.',
                agente='curso',
            )
        self.assertEqual(OutboxEnvio.objects.count(), 1)
        self.assertEqual(OutboxEnvio.objects.get().estado, 'ENVIADO')
