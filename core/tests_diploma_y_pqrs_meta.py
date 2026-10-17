"""Diploma y PQRS salen por Meta. El video de clase sigue en Twilio."""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase, override_settings

from core.views.diploma_meta import es_entrega_diploma


class EsDiplomaTests(SimpleTestCase):
    def test_frases_de_diploma(self):
        url = 'https://eki-produccion.s3.amazonaws.com/cert.png'
        self.assertTrue(es_entrega_diploma('🎓 *¡Tu certificado!*', url))
        self.assertTrue(es_entrega_diploma('🎓 *¡Su certificado!*', url))
        self.assertTrue(es_entrega_diploma('Tu certificado digital está listo:\n' + url, url))
        self.assertTrue(es_entrega_diploma('Ana — certificado *Café*', url))

    def test_video_de_clase_no_es_diploma(self):
        self.assertFalse(es_entrega_diploma('Módulo 2. Riego', 'https://x/clase.mp4'))
        self.assertFalse(es_entrega_diploma('🎓 *¡Tu certificado!*', None))
        self.assertFalse(es_entrega_diploma('hablemos del certificado en clase', 'https://x/clase.mp4'))


class DiplomaSalePorMetaTests(SimpleTestCase):
    @patch('core.sandbox_canal.enviar_meta', return_value={'success': True, 'mensaje_id': 'wamid.DIP'})
    @patch('twilio.rest.Client')
    def test_diploma_no_llama_a_twilio(self, client_cls, meta):
        from core.utils import enviar_whatsapp_twilio

        r = enviar_whatsapp_twilio(
            '573001112233',
            '🎓 *¡Tu certificado!*',
            media_url='https://eki-produccion.s3.amazonaws.com/cert.png',
        )
        self.assertTrue(r['success'])
        meta.assert_called_once()
        self.assertEqual(meta.call_args.kwargs['canal_evento'], 'certificado')
        self.assertEqual(meta.call_args.kwargs['media_url'], 'https://eki-produccion.s3.amazonaws.com/cert.png')
        client_cls.assert_not_called()

    @override_settings(
        TWILIO_ACCOUNT_SID='ACtest',
        TWILIO_AUTH_TOKEN='token',
        TWILIO_WHATSAPP_NUMBER='whatsapp:+14155238886',
    )
    @patch('core.sandbox_canal.enviar_meta')
    @patch('core.utils.WhatsappLog')
    @patch('twilio.rest.Client')
    def test_video_de_aula_sigue_en_twilio(self, client_cls, _log, meta):
        from core.utils import enviar_whatsapp_twilio

        msg = MagicMock()
        msg.sid = 'SMaula'
        client_cls.return_value.messages.create.return_value = msg
        r = enviar_whatsapp_twilio(
            '573001112233',
            'Módulo 1. El surco',
            media_url='https://eki-produccion.s3.amazonaws.com/clase.mp4',
        )
        self.assertTrue(r['success'])
        meta.assert_not_called()
        client_cls.return_value.messages.create.assert_called()


class PqrsMetaTests(TestCase):
    def test_si_meta_falla_no_marca_resuelta(self):
        from core.models import Estudiante, SolicitudSoporte
        from core.pqrs_respuesta import aplicar_respuesta_pqrs

        from core.models import Cliente

        cliente = Cliente.objects.create(
            nombre='Coop Diploma',
            nit='900111222-1',
            contacto_principal='Ana',
            email='diploma-meta@example.com',
            telefono='573009990087',
            activo=True,
        )
        est = Estudiante.objects.create(
            nombre='Ana Ruiz',
            telefono='573009990088',
            cedula='9001112223',
            cliente=cliente,
            estado_chat='ACTIVO',
            acepto_terminos=True,
            activo=True,
        )
        solicitud = SolicitudSoporte.objects.create(
            estudiante=est,
            mensaje_original='No abre el video',
            estado='pendiente',
        )
        with patch('core.sandbox_canal.enviar_meta', return_value={'success': False, 'response': '131047'}):
            ok, err = aplicar_respuesta_pqrs(solicitud, 'Ya quedó el video.', user=None)
        self.assertFalse(ok)
        self.assertIn('131047', err)
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, 'pendiente')
        self.assertFalse(solicitud.respuesta)


class PlantillaDiplomaMetaTests(SimpleTestCase):
    @override_settings(META_TEMPLATE_DIPLOMA='diploma_eki', META_TEMPLATE_DIPLOMA_IDIOMA='es')
    @patch('core.lineas.envio._post_graph', return_value={'success': True, 'mensaje_id': 'wamid.TPL'})
    def test_encabezado_imagen_y_cuerpo(self, post):
        from core.views.diploma_meta import enviar_diploma_plantilla_meta

        r = enviar_diploma_plantilla_meta(
            '573026480629',
            'https://eki-produccion.s3.amazonaws.com/cert.png',
            nombre_estudiante='Julian',
            curso='Innovación',
            codigo='eki-E26A',
        )
        self.assertTrue(r['success'])
        body = post.call_args.args[0]
        self.assertEqual(body['type'], 'template')
        self.assertEqual(body['template']['name'], 'diploma_eki')
        comps = body['template']['components']
        self.assertEqual(comps[0]['parameters'][0]['image']['link'], 'https://eki-produccion.s3.amazonaws.com/cert.png')
        textos = [p['text'] for p in comps[1]['parameters']]
        self.assertEqual(textos, ['Julian', 'Innovación', 'eki-E26A'])

    @override_settings(META_TEMPLATE_DIPLOMA='')
    def test_sin_nombre_no_llama_a_graph(self):
        from core.views.diploma_meta import enviar_diploma_plantilla_meta

        with patch('core.views.diploma_meta.nombre_plantilla_diploma', return_value=''):
            self.assertIsNone(
                enviar_diploma_plantilla_meta('573026480629', 'https://eki-produccion.s3.amazonaws.com/cert.png')
            )


class NombrePlantillaDiplomaTests(TestCase):
    @override_settings(META_TEMPLATE_DIPLOMA='')
    def test_lee_el_nombre_de_configuracion_global(self):
        from core.models import ConfiguracionGlobal
        from core.views.diploma_meta import nombre_plantilla_diploma

        cfg = ConfiguracionGlobal.get_solo()
        cfg.meta_plantilla_diploma = 'diploma_eki'
        cfg.save(update_fields=['meta_plantilla_diploma'])
        self.assertEqual(nombre_plantilla_diploma(), 'diploma_eki')

    @override_settings(META_TEMPLATE_DIPLOMA='desde_entorno')
    def test_el_entorno_gana_sobre_el_admin(self):
        from core.models import ConfiguracionGlobal
        from core.views.diploma_meta import nombre_plantilla_diploma

        cfg = ConfiguracionGlobal.get_solo()
        cfg.meta_plantilla_diploma = 'desde_admin'
        cfg.save(update_fields=['meta_plantilla_diploma'])
        self.assertEqual(nombre_plantilla_diploma(), 'desde_entorno')
