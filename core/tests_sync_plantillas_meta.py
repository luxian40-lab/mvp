"""Catálogo Meta: el estado de aprobación baja de Graph y la prueba no cierra la campaña."""
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from core.meta_waba import enviar_prueba_meta, sincronizar_catalogo_meta
from core.models import Cliente
from core.models_campana_meta import CampanaMeta, PlantillaMeta

WABA = '111222333'
PHONE = '495439026995771'


@override_settings(
    EKI_CAMPANA_META_ENABLED=True,
    WHATSAPP_TOKEN='tok',
    WHATSAPP_BUSINESS_ACCOUNT_ID=WABA,
    WHATSAPP_PHONE_ID=PHONE,
    WHATSAPP_API_VERSION='v21.0',
)
class SyncCatalogoMetaTests(TestCase):
    def test_pagina_y_marca_aprobada_o_rechazada(self):
        local = PlantillaMeta.objects.create(
            nombre_interno='Habeas',
            meta_name='eki_habeas',
            idioma='es',
            cuerpo='Hola. Responda este mensaje.',
            categoria='UTILITY',
            estado='BORRADOR',
        )

        def falso_get(url, params=None):
            if params:
                return 200, {
                    'data': [{
                        'id': '55',
                        'name': 'eki_habeas',
                        'language': 'es',
                        'status': 'APPROVED',
                    }],
                    'paging': {'next': 'https://graph.example/next'},
                }
            return 200, {
                'data': [{
                    'id': '56',
                    'name': 'eki_rechazada',
                    'language': 'es',
                    'status': 'REJECTED',
                    'rejected_reason': 'INVALID_FORMAT',
                    'components': [{'type': 'BODY', 'text': 'Hola desde Meta.'}],
                }],
            }

        with patch('core.meta_waba._get', side_effect=falso_get):
            resultado = sincronizar_catalogo_meta()
        self.assertTrue(resultado['ok'])
        local.refresh_from_db()
        self.assertEqual(local.estado, 'APPROVED')
        self.assertEqual(local.meta_template_id, '55')
        nueva = PlantillaMeta.objects.get(meta_name='eki_rechazada')
        self.assertEqual(nueva.estado, 'REJECTED')
        self.assertEqual(nueva.rejected_reason, 'INVALID_FORMAT')

    def test_comando_falla_sin_waba(self):
        with patch('core.meta_waba._waba', return_value=''):
            with self.assertRaises(CommandError):
                call_command('sync_plantillas_meta')


@override_settings(
    EKI_CAMPANA_META_ENABLED=True,
    WHATSAPP_TOKEN='tok',
    WHATSAPP_BUSINESS_ACCOUNT_ID=WABA,
    WHATSAPP_PHONE_ID=PHONE,
    WHATSAPP_API_VERSION='v21.0',
)
class EnviarPruebaMetaTests(TestCase):
    def setUp(self):
        self.org = Cliente.objects.create(
            nombre='Org prueba',
            contacto_principal='a',
            email='prueba-meta@example.com',
            telefono='573000000222',
        )
        self.plantilla = PlantillaMeta.objects.create(
            nombre_interno='Aviso',
            meta_name='eki_aviso',
            idioma='es',
            cuerpo='Hola {{1}}.',
            ejemplos_cuerpo='Ana',
            categoria='UTILITY',
            estado='PENDING',
            waba_id=WABA,
        )
        self.campana = CampanaMeta.objects.create(
            nombre='Prueba',
            cliente=self.org,
            plantilla=self.plantilla,
            mapeo_body='nombre',
        )

    def test_pendiente_no_envia(self):
        resultado = enviar_prueba_meta(self.campana, '573001112233')
        self.assertFalse(resultado['success'])
        self.assertIn('PENDING', resultado['message'])
        self.campana.refresh_from_db()
        self.assertFalse(self.campana.ejecutada)

    @patch('core.meta_waba.phone_pertenece_a_waba', return_value=(True, ''))
    @patch('core.meta_waba._post')
    def test_aprobada_envia_una_vez_sin_cerrar_campana(self, post, _phone):
        self.plantilla.estado = 'APPROVED'
        self.plantilla.save(update_fields=['estado'])
        post.return_value = (200, {'messages': [{'id': 'wamid.prueba'}]})
        resultado = enviar_prueba_meta(self.campana, '+57 300-111-2233')
        self.assertTrue(resultado['success'])
        self.assertEqual(resultado['wamid'], 'wamid.prueba')
        enviado = post.call_args[0][1]
        self.assertEqual(enviado['to'], '573001112233')
        self.assertEqual(enviado['template']['name'], 'eki_aviso')
        self.campana.refresh_from_db()
        self.assertFalse(self.campana.ejecutada)
