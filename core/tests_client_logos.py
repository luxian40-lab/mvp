from django.test import SimpleTestCase

from core.client_logos import logo_estatico_para_nombre


class ClientLogosTests(SimpleTestCase):
    def test_match(self):
        self.assertIn('agrosavia', logo_estatico_para_nombre('AGROSAVIA Tunja'))
        self.assertIn('fedepalma', logo_estatico_para_nombre('Fedepalma'))
        self.assertIn('profamilia', logo_estatico_para_nombre('Profamilia'))
        self.assertIn('eki.png', logo_estatico_para_nombre('eki Demo'))
        self.assertIsNone(logo_estatico_para_nombre('Cliente desconocido XYZ'))
