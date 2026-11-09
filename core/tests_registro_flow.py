"""El Flow de registro v2 pide nombre, cédula, municipio y habeas con URL."""
from django.test import SimpleTestCase

from core.lineas.registro_flow import NOMBRE_FLOW, PANTALLA, URL_HABEAS, flow_registro


class FlowRegistroTests(SimpleTestCase):
    def test_pide_consentimiento_nombre_cedula_y_municipio(self):
        pantalla = flow_registro()['screens'][0]
        self.assertEqual(pantalla['id'], PANTALLA)
        hijos = pantalla['layout']['children'][0]['children']
        por_nombre = {hijo.get('name'): hijo for hijo in hijos if hijo.get('name')}
        self.assertTrue(por_nombre['habeas']['required'])
        self.assertEqual(por_nombre['habeas']['on-click-action']['url'], URL_HABEAS)
        self.assertTrue(por_nombre['nombre']['required'])
        self.assertTrue(por_nombre['cedula']['required'])
        self.assertTrue(por_nombre['municipio']['required'])
        texto = ' '.join(hijo.get('text', '') for hijo in hijos).lower()
        self.assertNotIn('opcional', texto)
        self.assertIn('municipio', texto)
        payload = hijos[-1]['on-click-action']['payload']
        self.assertEqual(set(payload), {'habeas', 'nombre', 'cedula', 'municipio'})
        self.assertEqual(NOMBRE_FLOW, 'eki_registro_v2')
