"""El Flow de registro pide nombre y cédula. No muestra municipio."""
from django.test import SimpleTestCase

from core.lineas.registro_flow import NOMBRE_FLOW, PANTALLA, flow_registro


class FlowRegistroTests(SimpleTestCase):
    def test_pide_consentimiento_nombre_y_cedula(self):
        pantalla = flow_registro()['screens'][0]
        self.assertEqual(pantalla['id'], PANTALLA)
        hijos = pantalla['layout']['children'][0]['children']
        por_nombre = {hijo.get('name'): hijo for hijo in hijos if hijo.get('name')}
        self.assertTrue(por_nombre['habeas']['required'])
        self.assertTrue(por_nombre['nombre']['required'])
        self.assertTrue(por_nombre['cedula']['required'])
        self.assertNotIn('municipio', por_nombre)
        texto = ' '.join(hijo.get('text', '') for hijo in hijos).lower()
        self.assertNotIn('opcional', texto)
        self.assertNotIn('municipio', texto)
        payload = hijos[-1]['on-click-action']['payload']
        self.assertEqual(set(payload), {'habeas', 'nombre', 'cedula'})
        self.assertEqual(NOMBRE_FLOW, 'eki_registro')
