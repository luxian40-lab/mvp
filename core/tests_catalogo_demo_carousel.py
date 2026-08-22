"""Carrusel demo v2: 2 botones (descripción + CTA)."""

from django.test import TestCase, override_settings
from unittest.mock import patch

from core.catalogo_demo_carousel import (
    DESC_RIENDAS,
    TEXTO_CTA_RIENDAS,
    TEXTO_INFO_VITRINA,
    es_keyword_carrusel,
    es_payload_carrusel,
    respuesta_por_payload,
    respuesta_por_texto,
)


class CatalogoDemoCarouselV2Tests(TestCase):
    def test_keywords(self):
        self.assertTrue(es_keyword_carrusel('programas'))
        self.assertTrue(es_keyword_carrusel('4'))
        self.assertFalse(es_keyword_carrusel('listo'))

    def test_payloads_dos_botones(self):
        self.assertTrue(es_payload_carrusel('desc_riendas'))
        self.assertTrue(es_payload_carrusel('in_riendas'))
        self.assertTrue(es_payload_carrusel('info_agrosavia'))
        self.assertIn('Tome las riendas', respuesta_por_payload('desc_riendas'))
        self.assertIn('quiero demo', respuesta_por_payload('desc_riendas').lower())
        self.assertEqual(respuesta_por_payload('in_riendas'), TEXTO_CTA_RIENDAS)
        self.assertEqual(respuesta_por_payload('info_fedepalma'), TEXTO_INFO_VITRINA)

    def test_seguimiento_tras_descripcion(self):
        self.assertEqual(respuesta_por_texto('quiero demo'), TEXTO_CTA_RIENDAS)
        self.assertIn('sin compromiso', respuesta_por_texto('no gracias').lower())
        self.assertEqual(respuesta_por_texto('descripcion riendas'), DESC_RIENDAS)

    @override_settings(EKI_DEMO_CAROUSEL_ENABLED=True, EKI_DEMO_CAROUSEL_CONTENT_SID='')
    def test_flujo_programas_fallback(self):
        from core.catalogo_demo_carousel import intentar_flujo_prospecto_carrusel

        with patch('core.utils.enviar_whatsapp_twilio') as mock_send:
            mock_send.return_value = {'success': True}
            ok = intentar_flujo_prospecto_carrusel(
                telefono='573009990002',
                msg_from='whatsapp:+573009990002',
                msg_body='programas',
            )
        self.assertTrue(ok)
        self.assertIn('Riendas', mock_send.call_args[0][1])

    @override_settings(EKI_DEMO_CAROUSEL_ENABLED=True)
    def test_flujo_desc_riendas(self):
        from core.catalogo_demo_carousel import intentar_flujo_prospecto_carrusel

        with patch('core.utils.enviar_whatsapp_twilio') as mock_send:
            mock_send.return_value = {'success': True}
            ok = intentar_flujo_prospecto_carrusel(
                telefono='573009990003',
                msg_from='whatsapp:+573009990003',
                msg_body='',
                button_payload='desc_riendas',
            )
        self.assertTrue(ok)
        self.assertIn('quiero demo', mock_send.call_args[0][1].lower())

    @override_settings(EKI_DEMO_CAROUSEL_ENABLED=True)
    def test_solo_botones_no_roba_programas(self):
        from core.catalogo_demo_carousel import intentar_flujo_prospecto_carrusel

        with patch('core.utils.enviar_whatsapp_twilio') as mock_send:
            mock_send.return_value = {'success': True}
            ok = intentar_flujo_prospecto_carrusel(
                telefono='573009990004',
                msg_from='whatsapp:+573009990004',
                msg_body='programas',
                solo_botones=True,
            )
        self.assertFalse(ok)
        mock_send.assert_not_called()

    @override_settings(EKI_DEMO_CAROUSEL_ENABLED=True)
    def test_solo_botones_si_payload(self):
        from core.catalogo_demo_carousel import intentar_flujo_prospecto_carrusel

        with patch('core.utils.enviar_whatsapp_twilio') as mock_send:
            mock_send.return_value = {'success': True}
            ok = intentar_flujo_prospecto_carrusel(
                telefono='573009990005',
                msg_from='whatsapp:+573009990005',
                msg_body='desc_agrosavia',
                solo_botones=True,
            )
        self.assertTrue(ok)
        self.assertIn('Agrosavia', mock_send.call_args[0][1])

    @override_settings(EKI_DEMO_CAROUSEL_ENABLED=True)
    def test_in_riendas_sin_curso_sigue_cta(self):
        from core.catalogo_demo_carousel import intentar_flujo_prospecto_carrusel

        with patch('core.utils.enviar_whatsapp_twilio') as mock_send:
            mock_send.return_value = {'success': True}
            ok = intentar_flujo_prospecto_carrusel(
                telefono='573009990010',
                msg_from='whatsapp:+573009990010',
                msg_body='',
                button_payload='in_riendas',
            )
        self.assertTrue(ok)
        self.assertEqual(mock_send.call_args[0][1], TEXTO_CTA_RIENDAS)

    @override_settings(EKI_DEMO_CAROUSEL_ENABLED=True)
    def test_in_riendas_crea_estudiante_y_habeas(self):
        from core.catalogo_demo_carousel import intentar_flujo_prospecto_carrusel
        from core.models import Cliente, Curso, Estudiante, ProgresoEstudiante

        cli = Cliente.objects.create(
            nombre='eki Demo',
            nit='900888777-1',
            activo=True,
            contacto_principal='eki',
            email='demo@eki.co',
            telefono='573000000000',
        )
        curso = Curso.objects.create(
            nombre='Demo · Tome las riendas',
            descripcion='Copia demo',
            cliente=cli,
            activo=True,
        )
        with override_settings(EKI_DEMO_RIENDAS_CURSO_ID=str(curso.id)):
            with patch('core.utils.enviar_whatsapp_twilio') as mock_txt, patch(
                'core.whatsapp_service.enviar_habeas_data'
            ) as mock_hab:
                mock_txt.return_value = {'success': True}
                mock_hab.return_value = {'success': True}
                ok = intentar_flujo_prospecto_carrusel(
                    telefono='573009990011',
                    msg_from='whatsapp:+573009990011',
                    msg_body='',
                    button_payload='in_riendas',
                )
        self.assertTrue(ok)
        est = Estudiante.objects.get(telefono='573009990011')
        self.assertEqual(est.cliente_id, cli.id)
        self.assertEqual(est.estado_chat, 'ESPERANDO_HABEAS_DATA')
        self.assertTrue(
            ProgresoEstudiante.objects.filter(estudiante=est, curso=curso).exists()
        )
        mock_hab.assert_called_once()

    @override_settings(EKI_DEMO_CAROUSEL_ENABLED=True)
    def test_in_riendas_no_roba_estudiante_otro_cliente(self):
        from core.catalogo_demo_carousel import intentar_flujo_prospecto_carrusel
        from core.models import Cliente, Curso, Estudiante

        otro = Cliente.objects.create(
            nombre='Org paga',
            nit='800111222-3',
            activo=True,
            contacto_principal='x',
            email='x@eki.co',
            telefono='57300',
        )
        demo = Cliente.objects.create(
            nombre='eki Demo',
            nit='900888777-2',
            activo=True,
            contacto_principal='eki',
            email='demo@eki.co',
            telefono='57300',
        )
        curso = Curso.objects.create(
            nombre='Demo · Tome las riendas',
            descripcion='Copia demo',
            cliente=demo,
            activo=True,
        )
        Estudiante.objects.create(
            nombre='Ya inscrito',
            cedula='1088001',
            telefono='573009990012',
            cliente=otro,
            activo=True,
        )
        with override_settings(EKI_DEMO_RIENDAS_CURSO_ID=str(curso.id)):
            with patch('core.utils.enviar_whatsapp_twilio') as mock_txt, patch(
                'core.whatsapp_service.enviar_habeas_data'
            ) as mock_hab:
                mock_txt.return_value = {'success': True}
                ok = intentar_flujo_prospecto_carrusel(
                    telefono='573009990012',
                    msg_from='whatsapp:+573009990012',
                    msg_body='',
                    button_payload='in_riendas',
                )
        self.assertTrue(ok)
        mock_hab.assert_not_called()
        self.assertIn('ya está en un curso', mock_txt.call_args[0][1].lower())
        self.assertEqual(
            Estudiante.objects.get(telefono='573009990012').cliente_id, otro.id
        )
