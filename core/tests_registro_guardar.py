"""El Flow de registro escribe la ficha y no toca un Flow GEI."""
import json
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from core.lineas.registro_guardar import datos_registro, guardar_registro, responder_registro
from core.models import Cliente, Estudiante
from formulario.flow_gei import MARCA_FLOW


def _flow(token, **extra):
    datos = {
        'flow_token': token,
        'habeas': True,
        'nombre': 'Ana Ruiz',
        'cedula': '1099000111',
        'municipio': 'Andes',
    }
    datos.update(extra)
    return MARCA_FLOW + json.dumps(datos)


class GuardarRegistroTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            nombre='Agricapital',
            contacto_principal='Ana',
            email='agri-reg@test.com',
            telefono='573001110001',
            activo=True,
            fecha_fin_suscripcion=timezone.localdate() + timedelta(days=30),
        )
        self.otro = Cliente.objects.create(
            nombre='Otro Cliente',
            contacto_principal='Bo',
            email='otro-reg@test.com',
            telefono='573001110002',
            activo=True,
            fecha_fin_suscripcion=timezone.localdate() + timedelta(days=30),
        )

    def test_un_flow_gei_no_es_registro(self):
        self.assertIsNone(datos_registro(MARCA_FLOW + '{"flow_token":"gei-4","nombre":"Ana"}'))
        self.assertIsNone(datos_registro('hola'))

    def test_crea_la_ficha_en_el_cliente(self):
        texto = guardar_registro('573009991001', json.loads(_flow(f'registro-C{self.cliente.pk}')[len(MARCA_FLOW):]))
        est = Estudiante.objects.get(telefono='573009991001')
        self.assertEqual(est.cliente_id, self.cliente.pk)
        self.assertEqual(est.nombre, 'Ana Ruiz')
        self.assertEqual(est.cedula, '1099000111')
        self.assertEqual(est.municipio, 'Andes')
        self.assertTrue(est.acepto_terminos)
        self.assertEqual(est.estado_chat, 'ACTIVO')
        self.assertIn('Agricapital', texto)

    def test_sin_cliente_queda_en_eki(self):
        guardar_registro('573009991002', json.loads(_flow('registro-general', cedula='1099000222')[len(MARCA_FLOW):]))
        est = Estudiante.objects.get(telefono='573009991002')
        self.assertIsNone(est.cliente_id)

    def test_no_cambia_el_cliente_que_ya_tenia(self):
        Estudiante.objects.create(
            nombre='Ana Ruiz', cedula='1099000333', telefono='573009991003',
            cliente=self.otro, acepto_terminos=True, estado_chat='ACTIVO',
        )
        texto = guardar_registro(
            '573009991003',
            json.loads(_flow(f'registro-C{self.cliente.pk}', cedula='1099000333')[len(MARCA_FLOW):]),
        )
        est = Estudiante.objects.get(telefono='573009991003')
        self.assertEqual(est.cliente_id, self.otro.pk)
        self.assertIn('Otro Cliente', texto)

    def test_cedula_de_otra_persona_no_se_mezcla(self):
        Estudiante.objects.create(
            nombre='Pedro', cedula='1099000444', telefono='573009991004',
            acepto_terminos=True, estado_chat='ACTIVO',
        )
        texto = guardar_registro(
            '573009991005',
            json.loads(_flow(f'registro-C{self.cliente.pk}', cedula='1099000444')[len(MARCA_FLOW):]),
        )
        self.assertFalse(Estudiante.objects.filter(telefono='573009991005').exists())
        self.assertIn('otro registro', texto)

    @patch('core.sandbox_menu.enviar_texto_sandbox')
    @patch('core.sandbox_menu._get_or_create_sesion')
    def test_la_puerta_responde_y_un_hola_sigue(self, sesion, envio):
        sesion.return_value.habeas_aceptado = False
        self.assertEqual(
            responder_registro('573009991006', _flow(f'registro-C{self.cliente.pk}', cedula='1099000666')),
            'handled',
        )
        self.assertEqual(Estudiante.objects.get(telefono='573009991006').cliente_id, self.cliente.pk)
        envio.assert_called_once()
        self.assertIsNone(responder_registro('573009991006', 'hola'))

    @patch('core.lineas.registro_guardar._ofrecer_menu_tras_registro')
    @patch('core.sandbox_menu.enviar_texto_sandbox')
    @patch('core.sandbox_menu._get_or_create_sesion')
    def test_agri_listo_dice_AgriCapital_y_abre_menu(self, sesion, envio, menu):
        sesion.return_value.habeas_aceptado = False
        with override_settings(EKI_AGRICAPITAL_CLIENTE_ID=str(self.cliente.pk)):
            self.assertEqual(
                responder_registro(
                    '573009991007',
                    _flow(f'registro-C{self.cliente.pk}', cedula='1099000777'),
                ),
                'handled',
            )
        texto = envio.call_args.args[2]
        self.assertIn('AgriCapital', texto)
        self.assertNotIn('Agricapital', texto)
        menu.assert_called_once_with('573009991007')
