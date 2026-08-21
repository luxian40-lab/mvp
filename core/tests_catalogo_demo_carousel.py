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
