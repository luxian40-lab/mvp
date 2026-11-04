"""La frase de la línea 3 abre el Flow. En las otras líneas no pasa nada."""
import json
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from core.conversacion.puertas import correr_puertas
from core.lineas.envio import enviar_meta_flow
from core.lineas.meta import lineas_producto, phone_ids
from core.lineas.perfil import USO_REGISTRO
from core.lineas.registro_abrir import (
    NOMBRE_FLOW,
    abrir_registro,
    publicar_flow_registro,
)
from core.lineas.registro_flow import PANTALLA, flow_registro
from core.sandbox_canal import salida_por_phone_id

PHONE = '1477762615411333'
WABA = '1560693046090506'
FLOW = '1644555950738838'
PRINCIPAL = '111'
LINEA_2 = '222'

AJUSTES = dict(
    EKI_LINEA_REGISTRO_PHONE_ID=PHONE,
    EKI_LINEA_REGISTRO_E164='573019018929',
    EKI_LINEA_REGISTRO_WABA_ID=WABA,
    EKI_LINEA_REGISTRO_FLOW_ID=FLOW,
    SANDBOX_WHATSAPP_PHONE_ID=PRINCIPAL,
    WHATSAPP_PHONE_ID=PRINCIPAL,
    BOT_COMERCIAL_SANDBOX_NUMBER='573000000001',
    WHATSAPP_PHONE_NUMBER_ID_2=LINEA_2,
    WHATSAPP_NUMERO_2_E164='573009536193',
    META_LINEAS='',
    EKI_LINEAS_BD_ENABLED=False,
)


def _parametros(envio):
    payload = envio.call_args.args[0]
    return payload['interactive']['action']['parameters']


@override_settings(**AJUSTES)
class AbrirRegistroTests(SimpleTestCase):
    def test_la_frase_del_cliente_abre_el_flow_publicado(self):
        with salida_por_phone_id(PHONE), patch(
            'core.lineas.envio.enviar_meta_flow', return_value={'success': True},
        ) as envio:
            self.assertEqual(abrir_registro('573001112233', 'EKI C12'), 'handled')
        envio.assert_called_once_with(
            '573001112233',
            envio.call_args.args[1],
            FLOW,
            pantalla=PANTALLA,
            flow_token='registro-C12',
            cta='Registrarme',
            agente_evento='registro_flow',
            modo='published',
            con_datos=False,
        )
        self.assertIn('cédula', envio.call_args.args[1])
        self.assertNotIn('correo', envio.call_args.args[1].lower())

    def test_hola_eki_es_el_registro_general(self):
        with salida_por_phone_id(PHONE), patch(
            'core.lineas.envio.enviar_meta_flow', return_value={'success': True},
        ) as envio:
            self.assertEqual(abrir_registro('573001112233', 'hola eki'), 'handled')
        self.assertEqual(envio.call_args.kwargs['flow_token'], 'registro-general')

    def test_la_linea_principal_no_abre_el_flow(self):
        with salida_por_phone_id(PRINCIPAL), patch(
            'core.lineas.envio.enviar_meta_flow',
        ) as envio:
            self.assertIsNone(abrir_registro('573001112233', 'HOLA EKI'))
        envio.assert_not_called()

    def test_la_linea_2_no_abre_el_flow(self):
        with salida_por_phone_id(LINEA_2), patch(
            'core.lineas.envio.enviar_meta_flow',
        ) as envio:
            self.assertIsNone(abrir_registro('573001112233', 'EKI C4'))
        envio.assert_not_called()

    def test_otra_frase_en_la_linea_3_no_abre_el_menu(self):
        with salida_por_phone_id(PHONE), patch(
            'core.lineas.envio.enviar_meta_flow',
        ) as envio, patch('core.sandbox_menu.enviar_texto_sandbox') as texto:
            self.assertEqual(abrir_registro('573001112233', 'menu'), 'handled')
        envio.assert_not_called()
        self.assertIn('HOLA EKI', texto.call_args.args[2])
        self.assertIn('municipio', texto.call_args.args[2])

    @override_settings(EKI_LINEA_REGISTRO_FLOW_ID='', EKI_LINEA_REGISTRO_WABA_ID='')
    def test_sin_flow_avisa_y_no_sigue(self):
        with salida_por_phone_id(PHONE), patch(
            'core.lineas.envio.enviar_meta_flow',
        ) as envio, patch('core.sandbox_menu.enviar_texto_sandbox') as texto:
            self.assertEqual(abrir_registro('573001112233', 'HOLA EKI'), 'handled')
        envio.assert_not_called()
        self.assertIn('no está listo', texto.call_args.args[2])

    def test_si_meta_rechaza_el_envio_pide_reintentar(self):
        with salida_por_phone_id(PHONE), patch(
            'core.lineas.envio.enviar_meta_flow', return_value={'success': False},
        ), patch('core.sandbox_menu.enviar_texto_sandbox') as texto:
            self.assertEqual(correr_puertas('573001112233', 'HOLA EKI'), 'handled')
        self.assertIn('Envíe de nuevo', texto.call_args.args[2])

    def test_el_payload_publicado_no_manda_datos_vacios(self):
        with patch('core.lineas.envio._emit_enviado'), patch(
            'core.lineas.envio._post_graph', return_value={'success': True, 'mensaje_id': 'm'},
        ) as post:
            enviar_meta_flow(
                '573001112233', 'Hola', FLOW,
                pantalla=PANTALLA, flow_token='registro-general',
                modo='published', con_datos=False, cta='Registrarme',
            )
        params = _parametros(post)
        self.assertEqual(params['mode'], 'published')
        self.assertEqual(params['flow_id'], FLOW)
        self.assertEqual(params['flow_action_payload'], {'screen': PANTALLA})
        self.assertNotIn('data', params['flow_action_payload'])

    def test_el_flow_gei_sigue_mandando_datos_vacios(self):
        with patch('core.lineas.envio._emit_enviado'), patch(
            'core.lineas.envio._post_graph', return_value={'success': True, 'mensaje_id': 'm'},
        ) as post:
            enviar_meta_flow(
                '573001112233', 'Ficha', 'gei-1',
                pantalla='S1', flow_token='gei-4',
            )
        params = _parametros(post)
        self.assertNotIn('mode', params)
        self.assertEqual(params['flow_action_payload'], {'screen': 'S1', 'data': {}})


@override_settings(**AJUSTES, WHATSAPP_TOKEN='token')
class PublicarRegistroTests(SimpleTestCase):
    @override_settings(EKI_LINEA_REGISTRO_FLOW_ID='')
    def test_si_ya_esta_publicado_no_crea_otro(self):
        lista = {'data': [
            {'id': '999', 'name': 'otro', 'status': 'PUBLISHED'},
            {'id': FLOW, 'name': NOMBRE_FLOW, 'status': 'PUBLISHED'},
        ]}
        with patch('requests.get') as get, patch('requests.post') as post:
            get.return_value.content = b'{}'
            get.return_value.json.return_value = lista
            get.return_value.status_code = 200
            self.assertEqual(publicar_flow_registro(), FLOW)
        post.assert_not_called()
        self.assertIn(f'/{WABA}/flows', get.call_args.args[0])

    @override_settings(EKI_LINEA_REGISTRO_FLOW_ID='', WHATSAPP_TOKEN='token')
    def test_si_no_existe_publica_el_json_minimo(self):
        with patch('requests.get') as get, patch('requests.post') as post:
            get.return_value.content = b'{}'
            get.return_value.json.return_value = {'data': []}
            get.return_value.status_code = 200
            post.return_value.content = b'{}'
            post.return_value.status_code = 200
            post.return_value.json.return_value = {'id': FLOW}
            self.assertEqual(publicar_flow_registro(), FLOW)
        cuerpo = post.call_args.kwargs['json']
        self.assertEqual(cuerpo['name'], NOMBRE_FLOW)
        self.assertTrue(cuerpo['publish'])
        documento = json.loads(cuerpo['flow_json'])
        self.assertEqual(documento, flow_registro())
        hijos = documento['screens'][0]['layout']['children'][0]['children']
        nombres = {hijo.get('name') for hijo in hijos if hijo.get('name')}
        self.assertEqual(nombres, {'habeas', 'nombre', 'cedula', 'municipio'})


class LineaRegistroEnElRegistroTests(SimpleTestCase):
    @override_settings(**AJUSTES)
    def test_entra_como_tercera_linea_de_registro(self):
        self.assertEqual(phone_ids(), (PRINCIPAL, LINEA_2, PHONE))
        linea = lineas_producto()[-1]
        self.assertEqual(linea.nombre, 'Línea 3')
        self.assertEqual(linea.uso, USO_REGISTRO)
        self.assertEqual(linea.waba_id, WABA)
        self.assertFalse(linea.perfil.menu)
        self.assertFalse(linea.perfil.curso_directo)

    @override_settings(
        **{**AJUSTES, 'EKI_LINEA_REGISTRO_PHONE_ID': '', 'EKI_LINEA_REGISTRO_E164': '573019018929'},
    )
    def test_sin_phone_id_siguen_las_dos_de_siempre(self):
        self.assertEqual(phone_ids(), (PRINCIPAL, LINEA_2))

    @override_settings(META_LINEAS='333|573019018929|Registro|registro', EKI_LINEAS_BD_ENABLED=False)
    def test_la_marca_registro_no_es_la_principal(self):
        linea = lineas_producto()[0]
        self.assertEqual(linea.uso, USO_REGISTRO)
        self.assertFalse(linea.perfil.menu)
