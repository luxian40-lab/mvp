"""Campaña Meta: alta Graph, firma de webhook y envío Cloud API."""
import hashlib
import hmac
import json
from unittest.mock import patch

from django.contrib.admin.sites import site
from django.contrib.auth.models import User
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from core.meta_waba import (
    aplicar_eventos_plantilla,
    armar_componentes_alta,
    crear_plantilla_en_meta,
    ejecutar_campana_meta,
    firma_meta_ok,
)
from core.models_campana_meta import (
    CampanaMeta,
    EnvioCampanaMeta,
    PlantillaMeta,
    TarjetaPlantillaMeta,
)
from core.models import Estudiante
from core.plantilla_builder import guardar_borrador_carrusel


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

    def test_ficha_enviar_esta_en_la_campana(self):
        from core.admin.campana_meta import CampanaMetaAdmin

        borrador = self.plantilla
        aprobada = PlantillaMeta.objects.get(pk=borrador.pk)
        aprobada.pk = None
        aprobada.nombre_interno = 'Aviso aprobado'
        aprobada.meta_name = ''
        aprobada.meta_template_id = ''
        aprobada.estado = 'APPROVED'
        aprobada.save()
        from django.test import RequestFactory

        rf = RequestFactory()
        req = rf.get('/admin/core/campanameta/add/')
        req.user = User.objects.create_superuser('camp_meta', 'camp@x.co', 'pass12345')
        adm = CampanaMetaAdmin(CampanaMeta, site)
        field = adm.formfield_for_foreignkey(CampanaMeta._meta.get_field('plantilla'), req)
        ids = set(field.queryset.values_list('pk', flat=True))
        self.assertIn(aprobada.pk, ids)
        self.assertNotIn(borrador.pk, ids)

        est = Estudiante.objects.create(
            cedula='100200301', nombre='Ana', telefono='573001112244', activo=True,
        )
        campana = CampanaMeta.objects.create(nombre='Lanzamiento ficha', plantilla=aprobada)
        campana.destinatarios.add(est)
        self.client.force_login(req.user)
        pagina = self.client.get(reverse('admin:core_campanameta_change', args=[campana.pk]))
        self.assertContains(pagina, 'Enviar prueba')
        self.assertContains(pagina, 'Enviar a 1')
        with patch('core.meta_waba.encolar_campana_meta', return_value='sync') as encolar:
            resp = self.client.post(reverse('admin:core_campanameta_enviar', args=[campana.pk]))
        self.assertEqual(resp.status_code, 302)
        encolar.assert_called_once_with(campana.id)

        pendiente = CampanaMeta.objects.create(nombre='Sin aprobar', plantilla=borrador)
        bloqueada = self.client.get(reverse('admin:core_campanameta_change', args=[pendiente.pk]))
        self.assertContains(bloqueada, 'Meta todavía no aprobó esta plantilla.')
        self.assertNotContains(bloqueada, 'Enviar a ')

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

    def test_tipo_incluye_formatos_de_meta(self):
        from core.models_campana_meta import TIPOS_PLANTILLA

        codigos = {codigo for codigo, _label in TIPOS_PLANTILLA}
        self.assertTrue({
            'TEXTO', 'IMAGEN', 'VIDEO', 'DOCUMENTO', 'UBICACION', 'CARRUSEL',
            'OFERTA_LIMITADA', 'CUPON', 'CATALOGO', 'PRODUCTOS', 'FLUJO',
            'LLAMADA', 'AUTENTICACION', 'PEDIDO',
        } <= codigos)

    @patch('core.meta_waba._post')
    def test_tipo_imagen_no_se_envia_a_meta(self, post):
        self.plantilla.tipo = 'IMAGEN'
        self.plantilla.save()
        resultado = crear_plantilla_en_meta(self.plantilla)
        post.assert_not_called()
        self.assertFalse(resultado['success'])
        self.assertIn('registro', resultado['message'])
        self.plantilla.refresh_from_db()
        self.assertEqual(self.plantilla.estado, 'BORRADOR')
        self.assertEqual(self.plantilla.tipo, 'IMAGEN')

    def test_admin_abre_el_editor_y_guarda_el_mensaje(self):
        User.objects.create_superuser('meta_ok', 'ok@t.com', 'pass12345')
        client = Client()
        client.login(username='meta_ok', password='pass12345')
        url = reverse('admin:core_plantillameta_change', args=[self.plantilla.pk])
        pagina = client.get(url, follow=True)
        self.assertEqual(pagina.status_code, 200)
        self.assertContains(pagina, 'Guardar y enviar a aprobación')
        self.assertContains(pagina, 'Agregar variable')
        self.assertContains(pagina, 'pm-phone')
        self.assertContains(pagina, 'eki-mb-wa-preview')
        self.assertContains(pagina, '_v2')
        self.assertContains(pagina, 'Oferta por tiempo limitado')
        self.assertContains(pagina, 'Video')
        self.assertContains(pagina, 'Cupón')
        resp = client.post(reverse('admin:core_plantillameta_change', args=[self.plantilla.pk]), {
            'nombre_interno': 'Aviso café',
            'cuerpo': 'Hola Ana, tu curso abre mañana.',
            'ejemplos_cuerpo': '',
            'boton_texto': 'Listo',
            'accion': 'guardar',
        })
        self.assertEqual(resp.status_code, 302)
        self.plantilla.refresh_from_db()
        self.assertEqual(self.plantilla.cuerpo, 'Hola Ana, tu curso abre mañana.')
        self.assertEqual(self.plantilla.boton_1_texto, 'Listo')
        self.assertEqual(self.plantilla.footer, 'eki')
        self.assertContains(pagina, 'name="media_url"')
        self.assertContains(pagina, 'URL de la imagen')

    def test_admin_guarda_la_url_de_imagen_y_de_video(self):
        User.objects.create_superuser('meta_media', 'media@t.com', 'pass12345')
        client = Client()
        client.login(username='meta_media', password='pass12345')
        url = reverse('admin:core_plantillameta_change', args=[self.plantilla.pk])
        imagen = client.post(url, {
            'nombre_interno': 'Aviso café',
            'tipo': 'IMAGEN',
            'cuerpo': 'Hola Ana, tu curso abre mañana.',
            'media_url': 'https://eki.example/foto.jpg',
            'accion': 'guardar',
        })
        self.assertEqual(imagen.status_code, 302)
        self.plantilla.refresh_from_db()
        self.assertEqual(self.plantilla.tipo, 'IMAGEN')
        self.assertEqual(self.plantilla.media_url, 'https://eki.example/foto.jpg')
        ficha = client.get(url, follow=True)
        self.assertContains(ficha, 'https://eki.example/foto.jpg')
        video = client.post(url, {
            'nombre_interno': 'Aviso café',
            'tipo': 'VIDEO',
            'cuerpo': 'Hola Ana, tu curso abre mañana.',
            'media_url': 'https://eki.example/clip.mp4',
            'accion': 'guardar',
        })
        self.assertEqual(video.status_code, 302)
        self.plantilla.refresh_from_db()
        self.assertEqual(self.plantilla.tipo, 'VIDEO')
        self.assertEqual(self.plantilla.media_url, 'https://eki.example/clip.mp4')

    def test_lista_y_tarjetas_de_tipo(self):
        User.objects.create_superuser('meta_lista', 'l@t.com', 'pass12345')
        client = Client()
        client.login(username='meta_lista', password='pass12345')
        lista = client.get(reverse('admin:core_plantillameta_changelist'))
        self.assertContains(lista, 'Nueva plantilla')
        self.assertContains(lista, 'Aviso café')
        tipo = client.get(reverse('admin:core_plantillameta_tipo'))
        self.assertRedirects(tipo, reverse('admin:core_plantillameta_add'))
        editor = client.get(reverse('admin:core_plantillameta_add') + '?tipo=TEXTO')
        self.assertContains(editor, 'Texto')
        self.assertContains(editor, 'Imagen')
        self.assertContains(editor, 'Carrusel')
        self.assertContains(editor, 'Agregar variable')
        self.assertContains(editor, 'Oferta por tiempo limitado')
        self.assertContains(editor, 'Video')
        self.assertContains(editor, 'Autenticación (código)')

    def test_admin_changelist(self):
        User.objects.create_superuser('meta_admin', 'm@t.com', 'pass12345')
        client = Client()
        client.login(username='meta_admin', password='pass12345')
        for name in ('admin:core_plantillameta_changelist', 'admin:core_campanameta_changelist'):
            resp = client.get(reverse(name))
            self.assertEqual(resp.status_code, 200)

    def test_atajo_guarda_borrador_sin_llamar_a_meta(self):
        User.objects.create_superuser('meta_dia', 'd@t.com', 'pass12345')
        client = Client()
        client.login(username='meta_dia', password='pass12345')
        pagina = client.get(reverse('admin_campana_meta_dia'))
        self.assertEqual(pagina.status_code, 200)
        self.assertContains(pagina, 'Tome las riendas de su dinero')
        self.assertContains(pagina, 'Innovación e IA para nuevos emprendedores')
        self.assertContains(pagina, 'Gestión de tiempo y productividad personal en el campo')
        with patch('core.meta_waba._post') as post:
            resp = client.post(reverse('admin_campana_meta_dia'), {
                'nombre': 'Formación del día',
                'cursos': ['riendas', 'innovacion', 'tiempo'],
            })
        post.assert_not_called()
        self.assertEqual(resp.status_code, 302)
        ficha = client.get(resp['Location'])
        self.assertEqual(ficha.status_code, 200)
        self.assertContains(ficha, 'Ver curso')
        plantilla = PlantillaMeta.objects.get(nombre_interno='Formación del día')
        self.assertEqual(plantilla.tipo, 'CARRUSEL')
        self.assertEqual(plantilla.estado, 'BORRADOR')
        ids = list(
            TarjetaPlantillaMeta.objects.filter(plantilla=plantilla)
            .order_by('orden')
            .values_list('boton_ver_id', 'boton_info_id', 'boton_ver_texto', 'boton_info_texto')
        )
        self.assertEqual(ids, [
            ('ver_riendas', 'info_riendas', 'Ver curso', 'Más información'),
            ('ver_innovacion', 'info_innovacion', 'Ver curso', 'Más información'),
            ('ver_tiempo', 'info_tiempo', 'Ver curso', 'Más información'),
        ])

    @override_settings(WHATSAPP_APP_ID='999000')
    @patch('core.meta_waba.subir_ejemplo_imagen', side_effect=['h-riendas', 'h-tiempo'])
    @patch('core.meta_waba._post')
    def test_carrusel_se_crea_en_meta(self, post, _subir):
        post.return_value = (200, {'id': 'car-1', 'status': 'PENDING'})
        plantilla = guardar_borrador_carrusel('Borrador', ['riendas', 'tiempo'])
        resultado = crear_plantilla_en_meta(plantilla)
        self.assertTrue(resultado['success'])
        plantilla.refresh_from_db()
        self.assertEqual(plantilla.estado, 'PENDING')
        self.assertEqual(plantilla.meta_template_id, 'car-1')
        payload = post.call_args.args[1]
        tipos = [c['type'] for c in payload['components']]
        self.assertEqual(tipos, ['BODY', 'CAROUSEL'])
        cards = payload['components'][1]['cards']
        self.assertEqual(len(cards), 2)
        primera = cards[0]['components']
        self.assertEqual(primera[0]['format'], 'IMAGE')
        self.assertEqual(primera[0]['example']['header_handle'], ['h-riendas'])
        self.assertEqual(
            [b['type'] for b in primera[2]['buttons']],
            ['QUICK_REPLY', 'QUICK_REPLY'],
        )
        self.assertEqual(primera[2]['buttons'][0]['text'], 'Ver curso')
        self.assertEqual(primera[2]['buttons'][1]['text'], 'Más información')
        self.assertEqual(cards[1]['components'][0]['example']['header_handle'], ['h-tiempo'])

    @patch('core.meta_waba.subir_ejemplo_imagen', side_effect=RuntimeError('Faltan WHATSAPP_APP_ID'))
    @patch('core.meta_waba._post')
    def test_carrusel_sin_foto_no_crea_la_plantilla(self, post, _subir):
        plantilla = guardar_borrador_carrusel('Sin foto', ['riendas', 'tiempo'])
        resultado = crear_plantilla_en_meta(plantilla)
        post.assert_not_called()
        self.assertFalse(resultado['success'])
        plantilla.refresh_from_db()
        self.assertEqual(plantilla.estado, 'ERROR')
        self.assertIn('WHATSAPP_APP_ID', plantilla.ultimo_error_mensaje)


    def test_editor_guarda_pie_origen_y_ejemplo(self):
        User.objects.create_superuser('meta_origen', 'o@t.com', 'pass12345')
        client = Client()
        client.login(username='meta_origen', password='pass12345')
        resp = client.post(reverse('admin:core_plantillameta_change', args=[self.plantilla.pk]), {
            'tipo': 'TEXTO',
            'nombre_interno': 'Aviso café',
            'meta_name': 'aviso_cafe',
            'categoria': 'UTILITY',
            'idioma': 'es',
            'cuerpo': 'Hola {{1}}, tu curso abre mañana.',
            'footer': 'eki aula',
            'variable_nums': '1',
            'ejemplo_1': 'Ana',
            'origen_1': 'estudiante.nombre',
            'boton_1_texto': 'Listo',
            'boton_1_tipo': 'QUICK_REPLY',
            'accion': 'guardar',
        })
        self.assertEqual(resp.status_code, 302)
        self.plantilla.refresh_from_db()
        self.assertEqual(self.plantilla.footer, 'eki aula')
        self.assertEqual(self.plantilla.ejemplos_cuerpo, 'Ana')
        self.assertEqual(self.plantilla.origen_variables, {'1': 'estudiante.nombre'})
        self.assertEqual(self.plantilla.meta_name, 'aviso_cafe')

    def test_aprobada_se_abre_en_solo_lectura_y_se_duplica(self):
        User.objects.create_superuser('meta_dup', 'd2@t.com', 'pass12345')
        client = Client()
        client.login(username='meta_dup', password='pass12345')
        self.plantilla.estado = 'APPROVED'
        self.plantilla.meta_template_id = 'tpl-1'
        self.plantilla.save()
        pagina = client.get(reverse('admin:core_plantillameta_change', args=[self.plantilla.pk]))
        self.assertContains(pagina, 'Duplicar')
        self.assertContains(pagina, 'Enviar prueba')
        self.assertNotContains(pagina, 'Guardar y enviar a aprobación')
        resp = client.post(reverse('admin:core_plantillameta_change', args=[self.plantilla.pk]), {
            'nombre_interno': 'Cambiada',
            'cuerpo': 'No debe guardarse.',
            'accion': 'guardar',
        })
        self.assertEqual(resp.status_code, 302)
        self.plantilla.refresh_from_db()
        self.assertEqual(self.plantilla.nombre_interno, 'Aviso café')
        copia_resp = client.post(reverse('admin:core_plantillameta_change', args=[self.plantilla.pk]), {
            'accion': 'duplicar',
        })
        self.assertEqual(copia_resp.status_code, 302)
        copia = PlantillaMeta.objects.exclude(pk=self.plantilla.pk).get()
        self.assertEqual(copia.estado, 'BORRADOR')
        self.assertEqual(copia.meta_name, 'aviso_cafe_v2')
        self.assertIn('copia', copia.nombre_interno)
        self.assertEqual(copia.meta_template_id, '')

    @patch('core.meta_waba.enviar_prueba_meta')
    def test_enviar_prueba_usa_los_ejemplos(self, prueba):
        from core.meta_waba import enviar_prueba_de_plantilla

        prueba.return_value = {'success': True, 'message': 'Prueba enviada.'}
        self.plantilla.estado = 'APPROVED'
        self.plantilla.save()
        resultado = enviar_prueba_de_plantilla(self.plantilla, '573001112233')
        self.assertTrue(resultado['success'])
        campana = prueba.call_args.args[0]
        self.assertEqual(campana.mapeo_body, 'Café')
        self.assertEqual(prueba.call_args.args[1], '573001112233')


class PantallaCampanaMetaTests(SimpleTestCase):
    def test_plantilla_abre_en_el_mensaje(self):
        from core.admin.campana_meta import PlantillaMetaAdmin

        adm = PlantillaMetaAdmin(PlantillaMeta, site)
        por_titulo = {nombre: opts for nombre, opts in adm.fieldsets}
        self.assertEqual(list(por_titulo)[0], 'Mensaje')
        self.assertEqual(
            por_titulo['Mensaje']['fields'],
            ('nombre_interno', 'linea', 'tipo', 'cuerpo', 'estado'),
        )
        self.assertIn('collapse', por_titulo['Más opciones']['classes'])
        self.assertEqual(adm.get_inlines(None, None), [])
        carrusel = PlantillaMeta(tipo='CARRUSEL', nombre_interno='x', cuerpo='Hola')
        self.assertEqual(len(adm.get_inlines(None, carrusel)), 1)

    def test_campana_abre_en_nombre_y_plantilla(self):
        from core.admin.campana_meta import CampanaMetaAdmin

        adm = CampanaMetaAdmin(CampanaMeta, site)
        por_titulo = {nombre: opts for nombre, opts in adm.fieldsets}
        self.assertEqual(por_titulo['Campaña']['fields'], ('nombre', 'es_inicio_flujo'))
        self.assertEqual(por_titulo['Plantilla de Meta']['fields'], ('cliente', 'plantilla'))
        self.assertEqual(
            por_titulo['Envío']['fields'],
            ('phone_number_id', 'fecha_programada', 'dias_repeticion'),
        )
        for opts in por_titulo.values():
            self.assertNotIn('collapse', opts.get('classes') or ())
