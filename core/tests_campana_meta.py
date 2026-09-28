"""Campaña Meta: alta Graph, firma de webhook y envío Cloud API."""
import hashlib
import hmac
import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.meta_waba import (
    aplicar_eventos_plantilla,
    armar_componentes_alta,
    crear_plantilla_en_meta,
    ejecutar_campana_meta,
    firma_meta_ok,
)
from core.models_campana_meta import CampanaMeta, EnvioCampanaMeta, PlantillaMeta
from core.models import Estudiante


SECRET = 'meta-app-secret-test'
WABA = '111222333'
PHONE = '495439026995771'


def _firma(body: bytes) -> str:
    digest = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    return f'sha256={digest}'


@override_settings(
    SECURE_SSL_REDIRECT=False,
    EKI_CAMPANA_META_ENABLED=True,
    WHATSAPP_TOKEN='tok',
    WHATSAPP_BUSINESS_ACCOUNT_ID=WABA,
    WHATSAPP_PHONE_ID=PHONE,
    WHATSAPP_APP_SECRET=SECRET,
    WHATSAPP_API_VERSION='v21.0',
    WHATSAPP_VERIFY_TOKEN='eki_webhook_verify_token',
)
class CampanaMetaTests(TestCase):
    def setUp(self):
        self.plantilla = PlantillaMeta(
            nombre_interno='Aviso café',
            categoria='UTILITY',
            idioma='es',
            header_texto='Hola {{1}}.',
            header_ejemplo='Ana',
            cuerpo='Tu curso {{1}} abre mañana.',
            ejemplos_cuerpo='Café',
            footer='eki',
            boton_1_tipo='QUICK_REPLY',
            boton_1_texto='Listo',
        )
        self.plantilla.save()

    def test_arma_componentes_header_body_boton(self):
        comps = armar_componentes_alta(self.plantilla)
        tipos = [c['type'] for c in comps]
        self.assertEqual(tipos, ['HEADER', 'BODY', 'FOOTER', 'BUTTONS'])
        self.assertEqual(comps[0]['example']['header_text'], ['Ana'])
        self.assertEqual(comps[1]['example']['body_text'], [['Café']])
        self.assertEqual(comps[3]['buttons'][0]['type'], 'QUICK_REPLY')

    @patch('core.meta_waba.requests.post')
    def test_crear_guarda_id_y_pending(self, post):
        post.return_value.status_code = 200
        post.return_value.json.return_value = {'id': '999', 'status': 'PENDING'}
        resultado = crear_plantilla_en_meta(self.plantilla)
        self.assertTrue(resultado['success'])
        self.plantilla.refresh_from_db()
        self.assertEqual(self.plantilla.meta_template_id, '999')
        self.assertEqual(self.plantilla.estado, 'PENDING')
        self.assertEqual(self.plantilla.waba_id, WABA)
        payload = post.call_args.kwargs['json']
        self.assertEqual(payload['name'], 'aviso_cafe')
        self.assertEqual(payload['category'], 'UTILITY')
        self.assertIn('/111222333/message_templates', post.call_args.args[0])

    @patch('core.meta_waba.requests.post')
    def test_crear_error_meta_queda_en_error(self, post):
        post.return_value.status_code = 400
        post.return_value.json.return_value = {
            'error': {
                'message': 'Template name already exists',
                'code': 100,
                'error_subcode': 2388026,
            }
        }
        resultado = crear_plantilla_en_meta(self.plantilla)
        self.assertFalse(resultado['success'])
        self.plantilla.refresh_from_db()
        self.assertEqual(self.plantilla.estado, 'ERROR')
        self.assertEqual(self.plantilla.ultimo_error_code, '2388026')
        self.assertIn('already exists', self.plantilla.ultimo_error_mensaje)

    def test_webhook_firma_valida_aprueba(self):
        self.plantilla.meta_template_id = '999'
        self.plantilla.estado = 'PENDING'
        self.plantilla.save()
        payload = {
            'object': 'whatsapp_business_account',
            'entry': [{
                'changes': [{
                    'field': 'message_template_status_update',
                    'value': {
                        'event': 'APPROVED',
                        'message_template_id': '999',
                        'message_template_name': 'aviso_cafe',
                        'message_template_language': 'es',
                        'reason': 'NONE',
                    },
                }],
            }],
        }
        raw = json.dumps(payload).encode()
        n = aplicar_eventos_plantilla(payload, raw, _firma(raw))
        self.assertEqual(n, 1)
        self.plantilla.refresh_from_db()
        self.assertEqual(self.plantilla.estado, 'APPROVED')

    def test_webhook_firma_invalida_no_cambia(self):
        self.plantilla.meta_template_id = '999'
        self.plantilla.estado = 'PENDING'
        self.plantilla.save()
        payload = {
            'entry': [{
                'changes': [{
                    'field': 'message_template_status_update',
                    'value': {'event': 'REJECTED', 'message_template_id': '999', 'reason': 'SCAM'},
                }],
            }],
        }
        raw = json.dumps(payload).encode()
        n = aplicar_eventos_plantilla(payload, raw, 'sha256=deadbeef')
        self.assertEqual(n, 0)
        self.plantilla.refresh_from_db()
        self.assertEqual(self.plantilla.estado, 'PENDING')

    def test_enviar_rechaza_si_no_esta_aprobada(self):
        campana = CampanaMeta.objects.create(nombre='Lanzamiento', plantilla=self.plantilla)
        with self.assertRaises(ValueError):
            ejecutar_campana_meta(campana)

    @patch('core.meta_waba.time.sleep')
    @patch('core.meta_waba.requests.post')
    @patch('core.meta_waba.requests.get')
    def test_enviar_arma_template_cloud_api(self, get, post, _sleep):
        self.plantilla.estado = 'APPROVED'
        self.plantilla.meta_template_id = '999'
        self.plantilla.waba_id = WABA
        self.plantilla.save()
        est = Estudiante.objects.create(
            cedula='100200300',
            nombre='Ana',
            telefono='573001112233',
            activo=True,
        )
        campana = CampanaMeta.objects.create(
            nombre='Lanzamiento',
            plantilla=self.plantilla,
            mapeo_header='nombre',
            mapeo_body='Café',
        )
        campana.destinatarios.add(est)
        get.return_value.status_code = 200
        get.return_value.json.return_value = {'data': [{'id': PHONE}]}
        post.return_value.status_code = 200
        post.return_value.json.return_value = {'messages': [{'id': 'wamid.1'}]}

        resultado = ejecutar_campana_meta(campana)
        self.assertEqual(resultado['enviados'], 1)
        self.assertFalse(resultado['rate_limit'])
        body = post.call_args.kwargs['json']
        self.assertEqual(body['type'], 'template')
        self.assertEqual(body['template']['name'], 'aviso_cafe')
        self.assertEqual(body['template']['language']['code'], 'es')
        self.assertEqual(body['to'], '573001112233')
        tipos = [c['type'] for c in body['template']['components']]
        self.assertEqual(tipos, ['header', 'body'])
        self.assertEqual(body['template']['components'][0]['parameters'][0]['text'], 'Ana')
        self.assertEqual(body['template']['components'][1]['parameters'][0]['text'], 'Café')
        self.assertTrue(
            EnvioCampanaMeta.objects.filter(campana=campana, estado='ENVIADO', wamid='wamid.1').exists()
        )
        campana.refresh_from_db()
        self.assertTrue(campana.ejecutada)

    def test_firma_compare_digest(self):
        raw = b'{"a":1}'
        self.assertTrue(firma_meta_ok(raw, _firma(raw), SECRET))
        self.assertFalse(firma_meta_ok(raw, 'sha256=00', SECRET))
        self.assertFalse(firma_meta_ok(raw, _firma(raw), ''))

    def test_admin_changelist(self):
        User.objects.create_superuser('meta_admin', 'm@t.com', 'pass12345')
        client = Client()
        client.login(username='meta_admin', password='pass12345')
        for name in ('admin:core_plantillameta_changelist', 'admin:core_campanameta_changelist'):
            resp = client.get(reverse(name))
            self.assertEqual(resp.status_code, 200)
