"""La campaña de la línea 2 no usa plantillas de la WABA principal."""
from unittest.mock import patch

from django.test import TestCase, override_settings

from core.lineas.campana import plantilla_sirve_en_linea, plantillas_aprobadas_de_linea
from core.models_campana_meta import CampanaMeta, PlantillaMeta

PHONE = '495439026995771'
LINEA_2 = '894379507087782'
WABA = '111222333'
WABA_2 = '999888777'


def _plantilla(**kwargs):
    datos = dict(
        nombre_interno='Aviso',
        meta_name='aviso_linea',
        idioma='es',
        categoria='UTILITY',
        tipo='TEXTO',
        cuerpo='Hola',
        estado='APPROVED',
        activa=True,
        waba_id=WABA,
    )
    datos.update(kwargs)
    return PlantillaMeta.objects.create(**datos)


@override_settings(
    EKI_CAMPANA_META_ENABLED=True,
    WHATSAPP_TOKEN='tok',
    WHATSAPP_API_VERSION='v21.0',
    WHATSAPP_PHONE_ID=PHONE,
    SANDBOX_WHATSAPP_PHONE_ID=PHONE,
    WHATSAPP_PHONE_NUMBER_ID_2=LINEA_2,
    WHATSAPP_NUMERO_2_E164='573009536193',
    WHATSAPP_BUSINESS_ACCOUNT_ID=WABA,
    WHATSAPP_BUSINESS_ACCOUNT_ID_2=WABA_2,
    META_LINEAS='',
)
class CampanaLineaWabaTests(TestCase):
    def test_la_linea_2_no_lista_la_plantilla_de_la_principal(self):
        de_la_principal = _plantilla(nombre_interno='Principal')
        de_la_2 = _plantilla(nombre_interno='Linea 2', meta_name='aviso_l2', waba_id=WABA_2)
        ids_2 = set(plantillas_aprobadas_de_linea(LINEA_2).values_list('id', flat=True))
        ids_1 = set(plantillas_aprobadas_de_linea(PHONE).values_list('id', flat=True))
        self.assertIn(de_la_2.id, ids_2)
        self.assertNotIn(de_la_principal.id, ids_2)
        self.assertIn(de_la_principal.id, ids_1)
        self.assertNotIn(de_la_2.id, ids_1)

    def test_el_envio_corta_si_la_plantilla_es_de_otra_cuenta(self):
        from core.meta_waba import ejecutar_campana_meta

        plantilla = _plantilla()
        campana = CampanaMeta.objects.create(
            nombre='L2 mal',
            plantilla=plantilla,
            phone_number_id=LINEA_2,
        )
        with self.assertRaises(ValueError) as ctx:
            ejecutar_campana_meta(campana)
        self.assertIn('no cruzan', str(ctx.exception).lower())

    def test_el_formulario_rechaza_la_plantilla_ajena(self):
        from core.admin.campana_meta import CampanaMetaForm

        plantilla = _plantilla()
        form = CampanaMetaForm(data={
            'nombre': 'Prueba',
            'plantilla': str(plantilla.pk),
            'phone_number_id': LINEA_2,
            'dias_repeticion': '14',
            'personas_ids': '',
            'grupos_ids': '',
            'reglas_json': '{}',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('plantilla', form.errors)

    def test_la_etiqueta_de_linea_dice_modo_twilio(self):
        from core.plantilla_meta_editor import lineas_disponibles

        etiquetas = ' '.join(nombre for _, nombre in lineas_disponibles())
        self.assertIn('modo Twilio', etiquetas)
        self.assertIn('versión Meta', etiquetas)

    def test_sin_waba_2_tampoco_sale_la_principal(self):
        with self.settings(WHATSAPP_BUSINESS_ACCOUNT_ID_2=''):
            de_la_principal = _plantilla()
            self.assertEqual(plantilla_sirve_en_linea(de_la_principal, LINEA_2)[:20], 'Esa plantilla es de ')
            ids_2 = set(plantillas_aprobadas_de_linea(LINEA_2).values_list('id', flat=True))
            self.assertNotIn(de_la_principal.id, ids_2)

    def test_fichas_dicen_quien_inicia_y_como_sigue(self):
        from core.lineas.campana import fichas_admin

        fichas = fichas_admin()
        self.assertEqual(len(fichas), 2)
        self.assertIn('planes mensuales', fichas[0]['entra'])
        self.assertIn('acabar el curso', fichas[1]['entra'])
        self.assertFalse(fichas[0]['lineal'])
        self.assertTrue(fichas[1]['lineal'])
        self.assertEqual(fichas[0]['waba'], WABA)
        self.assertEqual(fichas[1]['waba'], WABA_2)

    def test_el_formulario_grava_la_waba_de_la_linea_2(self):
        from core.admin.plantilla_meta_admin import PlantillaMetaAdminForm

        form = PlantillaMetaAdminForm(data={
            'nombre_interno': 'Aviso L2',
            'meta_name': 'aviso_l2_form',
            'idioma': 'es',
            'categoria': 'UTILITY',
            'tipo': 'TEXTO',
            'cuerpo': 'Hola',
            'estado': 'BORRADOR',
            'origen': 'LOCAL',
            'activa': 'on',
            'linea': LINEA_2,
            'components_raw': '{}',
            'origen_variables': '{}',
        })
        self.assertTrue(form.is_valid(), form.errors)
        plantilla = form.save()
        self.assertEqual(plantilla.waba_id, WABA_2)

    def test_sin_waba_2_el_formulario_no_deja_crear(self):
        from core.admin.plantilla_meta_admin import PlantillaMetaAdminForm

        with self.settings(WHATSAPP_BUSINESS_ACCOUNT_ID_2=''):
            form = PlantillaMetaAdminForm(data={
                'nombre_interno': 'Aviso L2',
                'meta_name': 'aviso_l2_sin_waba',
                'idioma': 'es',
                'categoria': 'UTILITY',
                'tipo': 'TEXTO',
                'cuerpo': 'Hola',
                'estado': 'BORRADOR',
                'origen': 'LOCAL',
                'activa': 'on',
                'linea': LINEA_2,
                'components_raw': '{}',
                'origen_variables': '{}',
            })
            self.assertFalse(form.is_valid())
            self.assertIn('linea', form.errors)

    @patch('core.meta_waba.requests.post')
    def test_crear_plantilla_pega_en_la_waba_de_la_linea_2(self, post):
        from core.meta_waba import crear_plantilla_en_meta

        post.return_value.status_code = 200
        post.return_value.json.return_value = {'id': '888', 'status': 'PENDING'}
        plantilla = _plantilla(
            estado='BORRADOR',
            waba_id=WABA_2,
            meta_name='aviso_l2_alta',
            nombre_interno='Alta L2',
        )
        resultado = crear_plantilla_en_meta(plantilla)
        self.assertTrue(resultado['success'], resultado)
        self.assertIn(f'/{WABA_2}/message_templates', post.call_args.args[0])

    @patch('core.meta_waba._get')
    def test_sincronizar_recorre_las_dos_waba_sin_mezclar(self, get):
        from core.meta_waba import sincronizar_catalogo_meta

        de_1 = _plantilla(meta_template_id='55')
        de_2 = _plantilla(
            nombre_interno='L2',
            meta_name='aviso_l2_sync',
            waba_id=WABA_2,
            meta_template_id='77',
        )

        def falso_get(url, params=None):
            if f'/{WABA_2}/' in url:
                return 200, {
                    'data': [{
                        'id': '77',
                        'name': 'aviso_l2_sync',
                        'language': 'es',
                        'status': 'APPROVED',
                    }],
                }
            return 200, {
                'data': [{
                    'id': '55',
                    'name': 'aviso_linea',
                    'language': 'es',
                    'status': 'APPROVED',
                }],
            }

        get.side_effect = falso_get
        resultado = sincronizar_catalogo_meta()
        self.assertTrue(resultado['ok'], resultado)
        de_1.refresh_from_db()
        de_2.refresh_from_db()
        self.assertEqual(de_1.estado, 'APPROVED')
        self.assertEqual(de_2.estado, 'APPROVED')
        self.assertNotEqual(de_1.estado, 'NO_EXISTE')
        self.assertEqual(de_2.waba_id, WABA_2)
        urls = [str(c.args[0]) for c in get.call_args_list]
        self.assertTrue(any(f'/{WABA}/' in u for u in urls))
        self.assertTrue(any(f'/{WABA_2}/' in u for u in urls))
