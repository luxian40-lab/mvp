"""C1 modularidad: diploma del chat (reto/MULTI_MSG) usa la misma entrega Meta + flag."""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone


class SegmentadoDiplomaInterceptTests(SimpleTestCase):
    """El camino envio_comun → segmentado no puede saltarse el diploma."""

    @patch('core.canal.sandbox_canal.sandbox_meta_activo', return_value=True)
    @patch(
        'core.views.diploma_meta.entregar_si_es_diploma',
        return_value={'success': True, 'mensaje_id': 'wamid.DIP'},
    )
    @patch('core.canal.sandbox_canal.enviar_meta')
    def test_diploma_en_segmentado_no_llama_enviar_meta_crudo(self, meta, entregar, _activo):
        from core.views.twilio_transporte import _enviar_mensaje_twilio_segmentado

        out = _enviar_mensaje_twilio_segmentado(
            client=MagicMock(),
            from_number='whatsapp:+100',
            to_number='whatsapp:+573001112233',
            body='🎓 *¡Tu certificado!*',
            media_url='https://eki-produccion.s3.amazonaws.com/certificados/generados/certificado_eki-ABCD.png',
        )
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0][0].sid, 'wamid.DIP')
        entregar.assert_called_once()
        meta.assert_not_called()

    @patch('core.canal.sandbox_canal.sandbox_meta_activo', return_value=True)
    @patch('core.views.diploma_meta.entregar_si_es_diploma', return_value=None)
    @patch(
        'core.canal.sandbox_canal.enviar_meta',
        return_value={'success': True, 'mensaje_id': 'wamid.CLASE'},
    )
    def test_video_de_clase_sigue_por_enviar_meta(self, meta, entregar, _activo):
        from core.views.twilio_transporte import _enviar_mensaje_twilio_segmentado

        out = _enviar_mensaje_twilio_segmentado(
            client=MagicMock(),
            from_number='whatsapp:+100',
            to_number='whatsapp:+573001112233',
            body='Módulo 2. Riego',
            media_url='https://eki-produccion.s3.amazonaws.com/clase.mp4',
        )
        self.assertEqual(out[0][0].sid, 'wamid.CLASE')
        entregar.assert_called_once()
        meta.assert_called_once()


class DiplomaEntregaPlantillaYFlagTests(TestCase):
    def setUp(self):
        from core.models import Cliente, Curso, Estudiante
        from core.models_certificados import Certificado

        self.cli = Cliente.objects.create(
            nombre='Coop C1 Dip',
            nit='900222333-1',
            contacto_principal='Ana',
            email='c1-dip@example.com',
            telefono='573009990101',
            activo=True,
        )
        self.est = Estudiante.objects.create(
            nombre='Lu C1',
            telefono='573009990102',
            cedula='9002223334',
            cliente=self.cli,
            estado_chat='ACTIVO',
            acepto_terminos=True,
            activo=True,
        )
        self.curso = Curso.objects.create(nombre='Curso C1', cliente=self.cli, activo=True)
        from core.models import NotaCierreCurso

        NotaCierreCurso.objects.create(estudiante=self.est, curso=self.curso, nota=9)
        hoy = timezone.now().date()
        self.cert = Certificado.objects.create(
            estudiante=self.est,
            curso=self.curso,
            calificacion_final=100,
            fecha_inicio=hoy,
            fecha_completado=hoy,
            emitido=True,
            codigo_verificacion='eki-C1AA-BBBB',
            archivo_imagen='certificados/generados/certificado_eki-C1AA-BBBB.png',
        )
        self.media = (
            'https://eki-produccion.s3.us-east-2.amazonaws.com/'
            'certificados/generados/certificado_eki-C1AA-BBBB.png'
        )

    @override_settings(META_TEMPLATE_DIPLOMA='diploma_eki', META_TEMPLATE_DIPLOMA_IDIOMA='es')
    @patch(
        'core.lineas.diploma_entrega.enviar_diploma_plantilla_meta',
        return_value={'success': True, 'mensaje_id': 'wamid.TPL'},
    )
    @patch('core.canal.sandbox_canal.enviar_meta')
    def test_con_plantilla_no_usa_imagen_de_sesion(self, meta, tpl):
        from core.lineas.diploma_entrega import entregar_si_corresponde

        r = entregar_si_corresponde(
            self.est.telefono,
            '🎓 *¡Tu certificado!*',
            self.media,
        )
        self.assertTrue(r['success'])
        self.assertEqual(r.get('modo'), 'plantilla_meta')
        tpl.assert_called_once()
        meta.assert_not_called()
        self.cert.refresh_from_db()
        self.assertTrue(self.cert.enviado_whatsapp)

    @override_settings(META_TEMPLATE_DIPLOMA='')
    @patch('core.lineas.sender.sender_de_linea')
    def test_sin_plantilla_sesion_y_marca_flag(self, sender_fn):
        from core.lineas.diploma_entrega import entregar_si_corresponde

        sender = MagicMock()
        sender.canal = 'meta'
        sender.texto.return_value = {'success': True, 'mensaje_id': 'wamid.SES'}
        sender_fn.return_value = sender
        r = entregar_si_corresponde(
            self.est.telefono,
            '🎓 *¡Su certificado!*',
            self.media,
        )
        self.assertTrue(r['success'])
        self.assertEqual(r.get('modo'), 'sesion_meta')
        sender.texto.assert_called_once()
        self.cert.refresh_from_db()
        self.assertTrue(self.cert.enviado_whatsapp)

    @override_settings(META_TEMPLATE_DIPLOMA='')
    @patch('core.lineas.sender.sender_de_linea')
    def test_si_meta_falla_no_marca(self, sender_fn):
        from core.lineas.diploma_entrega import entregar_si_corresponde

        sender = MagicMock()
        sender.canal = 'meta'
        sender.texto.return_value = {'success': False, 'response': '131047'}
        sender_fn.return_value = sender
        r = entregar_si_corresponde(
            self.est.telefono,
            '🎓 *¡Tu certificado!*',
            self.media,
        )
        self.assertFalse(r['success'])
        self.cert.refresh_from_db()
        self.assertFalse(self.cert.enviado_whatsapp)

    def test_no_diploma_devuelve_none(self):
        from core.lineas.diploma_entrega import entregar_si_corresponde

        self.assertIsNone(
            entregar_si_corresponde(
                self.est.telefono,
                'Módulo 1',
                'https://eki-produccion.s3.amazonaws.com/clase.mp4',
            )
        )

    def test_sin_nota_de_cierre_no_envia_el_diploma(self):
        from core.lineas.diploma_entrega import entregar_si_corresponde
        from core.models import NotaCierreCurso

        NotaCierreCurso.objects.filter(estudiante=self.est, curso=self.curso).delete()
        with patch('core.lineas.diploma_entrega.enviar_diploma_plantilla_meta') as tpl:
            r = entregar_si_corresponde(
                self.est.telefono,
                '🎓 *¡Tu certificado!*',
                self.media,
            )
        self.assertEqual(r.get('modo'), 'sin_nota')
        tpl.assert_not_called()
        self.cert.refresh_from_db()
        self.assertFalse(self.cert.enviado_whatsapp)
