"""Listado Unfold de Plantillas Meta, importación y reglas de alta.

No envía WhatsApp. Graph va con mock.
"""
import hashlib
import hmac
import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.meta_waba import aplicar_eventos_plantilla, sincronizar_catalogo_meta
from core.models_campana_meta import CampanaMeta, PlantillaMeta
from core.plantilla_meta_reglas import errores_de_alta

SECRET = 'meta-app-secret-test'
WABA = '111222333'
PHONE = '495439026995771'


def _firma(body: bytes) -> str:
    digest = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    return f'sha256={digest}'


def _plantilla(**kwargs):
    datos = {
        'nombre_interno': 'Aviso café',
        'meta_name': 'aviso_cafe',
        'idioma': 'es',
        'categoria': 'UTILITY',
        'cuerpo': 'Hola Ana, tu curso abre mañana.',
        'estado': 'BORRADOR',
    }
    datos.update(kwargs)
    return PlantillaMeta.objects.create(**datos)


@override_settings(SECURE_SSL_REDIRECT=False)
class ListaPlantillasTests(TestCase):
    def setUp(self):
        User.objects.create_superuser('pm_lista', 'pm@t.com', 'pass12345')
        self.client = Client()
        self.client.login(username='pm_lista', password='pass12345')

    def test_lista_vacia_muestra_conteos_en_cero(self):
        pagina = self.client.get(reverse('admin:core_plantillameta_changelist'))
        self.assertEqual(pagina.status_code, 200)
        self.assertContains(pagina, 'Todas · 0')
        self.assertContains(pagina, 'Aprobadas · 0')
        self.assertContains(pagina, 'Pendientes · 0')
        self.assertContains(pagina, 'Rechazadas · 0')
        self.assertContains(pagina, 'Borradores · 0')
        self.assertContains(pagina, 'Importadas · 0')
        self.assertContains(pagina, 'Nueva plantilla')
        self.assertContains(pagina, 'Traer de Meta')
        self.assertNotContains(pagina, 'pm-wrap')

    def test_pestanas_conteos_busqueda_y_usos(self):
        _plantilla(estado='APPROVED', meta_name='uno', nombre_interno='Uno')
        _plantilla(estado='APPROVED', meta_name='dos', nombre_interno='Dos')
        _plantilla(estado='PENDING', meta_name='tres', nombre_interno='Tres')
        _plantilla(estado='REJECTED', meta_name='cuatro', nombre_interno='Cuatro')
        _plantilla(estado='BORRADOR', meta_name='cinco', nombre_interno='Cinco')
        importada = _plantilla(
            estado='APPROVED',
            meta_name='seis',
            nombre_interno='Seis visible',
            origen='IMPORTADA',
        )
        CampanaMeta.objects.create(nombre='Uso', plantilla=importada)
        pagina = self.client.get(reverse('admin:core_plantillameta_changelist'))
        self.assertContains(pagina, 'Todas · 6')
        self.assertContains(pagina, 'Aprobadas · 3')
        self.assertContains(pagina, 'Pendientes · 1')
        self.assertContains(pagina, 'Rechazadas · 1')
        self.assertContains(pagina, 'Borradores · 1')
        self.assertContains(pagina, 'Importadas · 1')
        self.assertContains(pagina, 'Seis visible')
        self.assertContains(pagina, '1 campañas · 0 envíos')
        busqueda = self.client.get(reverse('admin:core_plantillameta_changelist'), {'q': 'seis'})
        self.assertContains(busqueda, 'Seis visible')
        self.assertNotContains(busqueda, 'Cinco')
        aprobadas = self.client.get(
            reverse('admin:core_plantillameta_changelist'),
            {'eki_pm': 'aprobadas'},
        )
        self.assertContains(aprobadas, 'Uno')
        self.assertNotContains(aprobadas, 'Cinco')

    def test_url_antigua_de_alta_redirige_al_asistente(self):
        alta = self.client.get(reverse('admin:core_plantillameta_tipo'))
        self.assertRedirects(alta, reverse('admin:core_plantillameta_add'))
        editor = self.client.get(reverse('admin:core_plantillameta_add') + '?tipo=TEXTO')
        self.assertContains(editor, 'Texto')
        self.assertContains(editor, 'Imagen')
        self.assertContains(editor, 'Carrusel')
        self.assertNotContains(editor, 'pm-wrap')


@override_settings(
    SECURE_SSL_REDIRECT=False,
    EKI_CAMPANA_META_ENABLED=True,
    WHATSAPP_TOKEN='tok',
    WHATSAPP_BUSINESS_ACCOUNT_ID=WABA,
    WHATSAPP_PHONE_ID=PHONE,
    WHATSAPP_PHONE_NUMBER_ID_2='222',
    WHATSAPP_APP_SECRET=SECRET,
    WHATSAPP_API_VERSION='v21.0',
)
class ImportarPlantillasTests(TestCase):
    def _catalogo(self):
        return {
            'data': [
                {
                    'id': '10',
                    'name': 'eki_texto',
                    'language': 'es',
                    'status': 'APPROVED',
                    'category': 'UTILITY',
                    'quality_score': {'score': 'GREEN'},
                    'components': [
                        {'type': 'BODY', 'text': 'Hola desde Meta.'},
                        {'type': 'BUTTONS', 'buttons': [{'type': 'QUICK_REPLY', 'text': 'Listo'}]},
                    ],
                },
                {
                    'id': '11',
                    'name': 'eki_imagen',
                    'language': 'es',
                    'status': 'APPROVED',
                    'category': 'MARKETING',
                    'components': [
                        {'type': 'HEADER', 'format': 'IMAGE'},
                        {'type': 'BODY', 'text': 'Mira la foto.'},
                    ],
                },
                {
                    'id': '12',
                    'name': 'eki_carrusel',
                    'language': 'es',
                    'status': 'PENDING',
                    'category': 'MARKETING',
                    'components': [
                        {'type': 'BODY', 'text': 'Deslice.'},
                        {'type': 'CAROUSEL', 'cards': []},
                    ],
                },
                {
                    'id': '13',
                    'name': 'eki_otp',
                    'language': 'es',
                    'status': 'APPROVED',
                    'category': 'AUTHENTICATION',
                    'components': [{'type': 'BODY', 'text': 'Su código es 123.'}],
                },
                {
                    'id': '14',
                    'name': 'eki_cupon',
                    'language': 'es',
                    'status': 'APPROVED',
                    'category': 'MARKETING',
                    'components': [
                        {'type': 'BODY', 'text': 'Cupón.'},
                        {'type': 'LIMITED_TIME_OFFER', 'limited_time_offer': {}},
                    ],
                },
            ],
        }

    def test_importacion_idempotente_y_no_pisa_el_nombre_visible(self):
        local = _plantilla(
            nombre_interno='Nombre local',
            meta_name='eki_texto',
            notas='Nota del equipo',
            estado='BORRADOR',
        )
        ausente = _plantilla(
            nombre_interno='Ya no está',
            meta_name='eki_ausente',
            meta_template_id='99',
            estado='APPROVED',
        )
        with patch('core.meta_waba._get', return_value=(200, self._catalogo())):
            primera = sincronizar_catalogo_meta()
            segunda = sincronizar_catalogo_meta()
        self.assertTrue(primera['ok'])
        self.assertEqual(primera['resumen']['nuevas'], 4)
        self.assertEqual(primera['resumen']['actualizadas'], 1)
        self.assertEqual(primera['resumen']['con_error'], 0)
        self.assertEqual(PlantillaMeta.objects.count(), 6)
        local.refresh_from_db()
        self.assertEqual(local.nombre_interno, 'Nombre local')
        self.assertEqual(local.notas, 'Nota del equipo')
        self.assertEqual(local.estado, 'APPROVED')
        self.assertEqual(local.tipo, 'TEXTO')
        self.assertEqual(local.calidad, 'GREEN')
        self.assertEqual(local.origen, 'LOCAL')
        por_nombre = {p.meta_name: p for p in PlantillaMeta.objects.all()}
        self.assertEqual(por_nombre['eki_imagen'].tipo, 'IMAGEN')
        self.assertEqual(por_nombre['eki_carrusel'].tipo, 'CARRUSEL')
        self.assertEqual(por_nombre['eki_otp'].tipo, 'AUTENTICACION')
        self.assertEqual(por_nombre['eki_otp'].categoria, 'AUTHENTICATION')
        self.assertEqual(por_nombre['eki_cupon'].tipo, 'OTRO')
        self.assertIn('LIMITED_TIME_OFFER', json.dumps(por_nombre['eki_cupon'].components_raw))
        ausente.refresh_from_db()
        self.assertEqual(ausente.estado, 'NO_EXISTE')
        self.assertTrue(PlantillaMeta.objects.filter(pk=ausente.pk).exists())
        self.assertEqual(segunda['resumen']['nuevas'], 0)
        self.assertEqual(segunda['resumen']['actualizadas'], 0)
        self.assertEqual(segunda['resumen']['sin_cambios'], 5)
        self.assertEqual(PlantillaMeta.objects.count(), 6)

    def test_reintenta_si_meta_limita_la_tasa(self):
        llamadas = {'n': 0}

        def falso_get(url, params=None):
            llamadas['n'] += 1
            if llamadas['n'] == 1:
                return 429, {'error': {'code': 4, 'message': 'rate'}}
            return 200, {'data': []}

        with patch('core.meta_waba._get', side_effect=falso_get), patch('core.meta_waba.time.sleep'):
            resultado = sincronizar_catalogo_meta()
        self.assertTrue(resultado['ok'])
        self.assertEqual(llamadas['n'], 2)

    def test_webhook_actualiza_calidad_y_categoria(self):
        plantilla = _plantilla(meta_template_id='77', estado='APPROVED', calidad='', categoria='UTILITY')
        payload = {
            'entry': [{
                'changes': [
                    {
                        'field': 'message_template_quality_update',
                        'value': {
                            'message_template_id': '77',
                            'new_quality_score': 'YELLOW',
                        },
                    },
                    {
                        'field': 'template_category_update',
                        'value': {
                            'message_template_id': '77',
                            'new_category': 'MARKETING',
                        },
                    },
                ],
            }],
        }
        raw = json.dumps(payload).encode()
        n = aplicar_eventos_plantilla(payload, raw, _firma(raw))
        self.assertEqual(n, 2)
        plantilla.refresh_from_db()
        self.assertEqual(plantilla.calidad, 'YELLOW')
        self.assertEqual(plantilla.categoria, 'MARKETING')
        self.assertEqual(aplicar_eventos_plantilla(payload, raw, 'sha256=00'), 0)
        plantilla.refresh_from_db()
        self.assertEqual(plantilla.calidad, 'YELLOW')


@override_settings(SECURE_SSL_REDIRECT=False, WHATSAPP_APP_ID='999')
class ValidacionAsistenteTests(TestCase):
    def setUp(self):
        User.objects.create_superuser('pm_val', 'v@t.com', 'pass12345')
        self.client = Client()
        self.client.login(username='pm_val', password='pass12345')
        self.url = reverse('admin:core_plantillameta_add')

    def _post(self, **extra):
        datos = {
            'tipo': 'TEXTO',
            'nombre_interno': 'Aviso',
            'meta_name': 'aviso',
            'categoria': 'UTILITY',
            'idioma': 'es',
            'cuerpo': 'Hola Ana, tu curso abre mañana.',
            'footer': 'eki',
            'accion': 'guardar',
        }
        datos.update(extra)
        return self.client.post(self.url, datos)

    def test_rechaza_nombre_con_mayusculas(self):
        resp = self._post(meta_name='AvisoMayus')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'minúsculas')
        self.assertFalse(PlantillaMeta.objects.filter(meta_name='avisomayus').exists())

    def test_rechaza_variable_al_inicio_y_al_final(self):
        inicio = self._post(meta_name='aviso_inicio', cuerpo='{{1}} hola', ejemplo_1='Ana', variable_nums='1')
        self.assertContains(inicio, 'empezar ni terminar')
        final = self._post(meta_name='aviso_final', cuerpo='hola {{1}}', ejemplo_1='Ana', variable_nums='1')
        self.assertContains(final, 'empezar ni terminar')
        self.assertEqual(PlantillaMeta.objects.count(), 0)

    def test_rechaza_pie_largo_y_carrusel_de_una_tarjeta(self):
        pie = self._post(meta_name='aviso_pie', footer='x' * 61)
        self.assertContains(pie, '60')
        carrusel = self._post(
            tipo='CARRUSEL',
            meta_name='aviso_cards',
            card_count='1',
            card_titulo_0='Uno',
            card_cuerpo_0='Texto',
            card_imagen_0='https://example.com/a.jpg',
        )
        self.assertContains(carrusel, '2 y 10')
        self.assertEqual(PlantillaMeta.objects.count(), 0)

    def test_reglas_sueltas_coinciden_con_el_formulario(self):
        self.assertTrue(any('minúsculas' in e for e in errores_de_alta({
            'nombre_interno': 'Aviso',
            'meta_name': 'Aviso',
            'cuerpo': 'Hola.',
            'tipo': 'TEXTO',
        })))
        self.assertTrue(any('2 y 10' in e for e in errores_de_alta({
            'nombre_interno': 'Aviso',
            'meta_name': 'aviso',
            'cuerpo': 'Hola.',
            'tipo': 'CARRUSEL',
            'tarjetas': [{'titulo': 'a', 'cuerpo': 'b'}],
        })))


@override_settings(
    SECURE_SSL_REDIRECT=False,
    EKI_CAMPANA_META_ENABLED=True,
    WHATSAPP_TOKEN='tok',
    WHATSAPP_BUSINESS_ACCOUNT_ID=WABA,
    WHATSAPP_PHONE_ID=PHONE,
    WHATSAPP_API_VERSION='v21.0',
)
class EjecutarPlantillaTests(TestCase):
    def setUp(self):
        User.objects.create_superuser('pm_env', 'e@t.com', 'pass12345')
        self.client = Client()
        self.client.login(username='pm_env', password='pass12345')
        self.borrador = _plantilla(estado='BORRADOR', rejected_reason='SCAM')

    def test_borrador_no_se_envia_ni_abre_campana(self):
        prueba = self.client.post(
            reverse('admin:core_plantillameta_enviar_prueba', args=[self.borrador.pk]),
            {'linea': PHONE, 'telefono': '573026480629', '_form_submitted': 'on'},
        )
        self.assertContains(prueba, 'Borrador')
        self.assertContains(prueba, 'Aprobada')
        self.assertContains(prueba, 'SCAM')
        campana = self.client.post(
            reverse('admin:core_plantillameta_usar_en_campana', args=[self.borrador.pk]),
            follow=True,
        )
        self.assertContains(campana, 'Borrador')
        self.assertContains(campana, 'Aprobada')
        self.assertEqual(CampanaMeta.objects.count(), 0)

    @patch('core.meta_waba._post')
    @patch('core.meta_waba.phone_pertenece_a_waba', return_value=(True, ''))
    def test_aprobada_arma_la_prueba_sin_llamar_si_el_post_esta_mockeado(self, _phone, post):
        post.return_value = (200, {'messages': [{'id': 'wamid.PRUEBA'}]})
        self.borrador.estado = 'APPROVED'
        self.borrador.rejected_reason = ''
        self.borrador.cuerpo = 'Hola {{1}}.'
        self.borrador.header_texto = ''
        self.borrador.ejemplos_cuerpo = 'Ana'
        self.borrador.save()
        resp = self.client.post(
            reverse('admin:core_plantillameta_enviar_prueba', args=[self.borrador.pk]),
            {'linea': PHONE, 'telefono': '573026480629', 'var_1': 'Ana', '_form_submitted': 'on'},
            follow=True,
        )
        self.assertContains(resp, 'wamid.PRUEBA')
        self.assertEqual(post.call_args.args[1]['to'], '573026480629')
        uso = self.client.post(
            reverse('admin:core_plantillameta_usar_en_campana', args=[self.borrador.pk]),
        )
        self.assertEqual(uso.status_code, 302)
        creada = CampanaMeta.objects.get()
        self.assertEqual(creada.plantilla_id, self.borrador.pk)
        self.assertEqual(creada.ejecutada, False)
