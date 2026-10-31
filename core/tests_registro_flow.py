"""El Flow de registro pide lo justo y deja el municipio vacío si quieren."""
from django.test import SimpleTestCase

from core.lineas.registro_flow import NOMBRE_FLOW, PANTALLA, flow_registro


class FlowRegistroTests(SimpleTestCase):
    def test_pide_consentimiento_nombre_cedula_y_municipio_opcional(self):
        pantalla = flow_registro()['screens'][0]
        self.assertEqual(pantalla['id'], PANTALLA)
        hijos = pantalla['layout']['children'][0]['children']
        por_nombre = {hijo.get('name'): hijo for hijo in hijos if hijo.get('name')}
        self.assertTrue(por_nombre['habeas']['required'])
        self.assertTrue(por_nombre['nombre']['required'])
        self.assertTrue(por_nombre['cedula']['required'])
        self.assertFalse(por_nombre['municipio']['required'])
        payload = hijos[-1]['on-click-action']['payload']
        self.assertEqual(set(payload), {'habeas', 'nombre', 'cedula', 'municipio'})
        self.assertEqual(NOMBRE_FLOW, 'eki_registro')
