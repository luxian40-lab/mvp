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
        from core.certificados.models_certificados import Certificado

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


class DiplomaLineaEmpresaTests(TestCase):
    """El diploma encolado no tiene turno. Sale por la línea de la empresa."""

    def setUp(self):
        from core.models import Cliente, Curso, Estudiante
        from core.certificados.models_certificados import Certificado

        self.cli = Cliente.objects.create(
            nombre='Agri Test',
            contacto_principal='A',
            email='agri-diploma@test.com',
            telefono='573000000026',
            activo=True,
        )
        self.est = Estudiante.objects.create(
            cedula='dipL3',
            nombre='Ana Linea',
            telefono='573000000027',
            cliente=self.cli,
            estado_chat='ACTIVO',
            activo=True,
        )
        self.curso = Curso.objects.create(nombre='Riego', cliente=self.cli, activo=True)
        hoy = timezone.now().date()
        self.cert = Certificado.objects.create(
            estudiante=self.est,
            curso=self.curso,
            calificacion_final=100,
            fecha_inicio=hoy,
            fecha_completado=hoy,
            emitido=True,
            codigo_verificacion='eki-L3AA-BBBB',
            archivo_imagen='certificados/generados/certificado_eki-L3AA-BBBB.png',
        )
        self.media = (
            'https://eki-produccion.s3.us-east-2.amazonaws.com/'
            'certificados/generados/certificado_eki-L3AA-BBBB.png'
        )

    def _spy(self, capturado):
        def spy(phone_id=None):
            capturado['phone_id'] = phone_id
            sender = MagicMock()
            sender.canal = 'meta'
            sender.plantilla_imagen.return_value = {'success': True, 'mensaje_id': 'wamid.L3'}
            return sender
        return spy

    def _plantilla(self, waba_id):
        from core.campanas.models_campana_meta import PlantillaMeta

        PlantillaMeta.objects.create(
            nombre_interno='Entrega documento',
            meta_name='entrega_documento_eki',
            cuerpo='Nombre: {{1}}. Curso: {{2}}. Referencia: {{3}}.',
            tipo='IMAGEN',
            categoria='UTILITY',
            estado='APPROVED',
            activa=True,
            waba_id=waba_id,
        )

    def test_sin_plantilla_en_la_cuenta_no_cambia_la_linea(self):
        from core.lineas.diploma_entrega import enviar_diploma_plantilla_meta

        capturado = {}
        with override_settings(
            EKI_AGRICAPITAL_CLIENTE_ID=str(self.cli.pk),
            EKI_LINEA_REGISTRO_PHONE_ID='1477762615411333',
            EKI_LINEA_REGISTRO_WABA_ID='1560693046090506',
            META_TEMPLATE_DIPLOMA='entrega_documento_eki',
        ), patch('core.lineas.sender.sender_de_linea', self._spy(capturado)):
            enviar_diploma_plantilla_meta(self.est.telefono, self.media)
        self.assertIsNone(capturado['phone_id'])

    def test_agricapital_sin_turno_sale_por_linea_3(self):
        from core.lineas.diploma_entrega import enviar_diploma_plantilla_meta

        self._plantilla('1560693046090506')
        capturado = {}
        with override_settings(
            EKI_AGRICAPITAL_CLIENTE_ID=str(self.cli.pk),
            EKI_LINEA_REGISTRO_PHONE_ID='1477762615411333',
            EKI_LINEA_REGISTRO_WABA_ID='1560693046090506',
            EKI_LINEA_REGISTRO_E164='573001112233',
            META_TEMPLATE_DIPLOMA='entrega_documento_eki',
        ), patch('core.lineas.sender.sender_de_linea', self._spy(capturado)):
            r = enviar_diploma_plantilla_meta(
                self.est.telefono,
                self.media,
                nombre_estudiante='Ana',
                curso='Riego',
                codigo='eki-L3AA-BBBB',
            )
        self.assertTrue(r['success'])
        self.assertEqual(capturado['phone_id'], '1477762615411333')

    def test_el_turno_abierto_no_se_cambia(self):
        from core.canal.sandbox_canal import salida_por_phone_id
        from core.lineas.diploma_entrega import enviar_diploma_plantilla_meta

        capturado = {}
        with override_settings(
            EKI_AGRICAPITAL_CLIENTE_ID=str(self.cli.pk),
            EKI_LINEA_REGISTRO_PHONE_ID='1477762615411333',
            META_TEMPLATE_DIPLOMA='entrega_documento_eki',
        ), salida_por_phone_id('495439026995771'), patch(
            'core.lineas.sender.sender_de_linea', self._spy(capturado),
        ):
            enviar_diploma_plantilla_meta(self.est.telefono, self.media)
        self.assertEqual(capturado['phone_id'], '495439026995771')

    def test_empresa_con_linea_propia_usa_esa_linea(self):
        from core.lineas.diploma_entrega import enviar_diploma_plantilla_meta

        self.cli.phone_id_meta = '222000000000222'
        self.cli.save(update_fields=['phone_id_meta'])
        self._plantilla('1000000000008942')
        capturado = {}
        with override_settings(
            META_TEMPLATE_DIPLOMA='entrega_documento_eki',
            WHATSAPP_BUSINESS_ACCOUNT_ID='1000000000008942',
        ), patch('core.lineas.sender.sender_de_linea', self._spy(capturado)):
            enviar_diploma_plantilla_meta(self.est.telefono, self.media)
        self.assertEqual(capturado['phone_id'], '222000000000222')

    def test_sin_linea_de_empresa_sigue_el_turno(self):
        from core.lineas.diploma_entrega import enviar_diploma_plantilla_meta

        capturado = {}
        with override_settings(META_TEMPLATE_DIPLOMA='entrega_documento_eki'), patch(
            'core.lineas.sender.sender_de_linea', self._spy(capturado),
        ):
            enviar_diploma_plantilla_meta(self.est.telefono, self.media)
        self.assertIsNone(capturado['phone_id'])
