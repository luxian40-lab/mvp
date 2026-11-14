"""C2: smoke --verificar-plantilla refleja config."""
from io import StringIO

from django.core.management import call_command
from django.test import SimpleTestCase, override_settings


class SmokeVerificarPlantillaTests(SimpleTestCase):
    @override_settings(META_TEMPLATE_DIPLOMA='diploma_eki')
    def test_con_nombre_exit_0(self):
        out = StringIO()
        err = StringIO()
        call_command(
            'smoke_certificado_envio',
            '--telefono',
            '573000000001',
            '--verificar-plantilla',
            stdout=out,
            stderr=err,
        )
        self.assertIn('plantilla_meta=diploma_eki', out.getvalue())
        self.assertIn('Plantilla lista', out.getvalue())

    @override_settings(META_TEMPLATE_DIPLOMA='')
    def test_sin_nombre_exit_1(self):
        from unittest.mock import patch

        out = StringIO()
        err = StringIO()
        with patch(
            'core.lineas.diploma_entrega.nombre_plantilla_diploma',
            return_value='',
        ):
            with self.assertRaises(SystemExit) as raised:
                call_command(
                    'smoke_certificado_envio',
                    '--telefono',
                    '573000000001',
                    '--verificar-plantilla',
                    stdout=out,
                    stderr=err,
                )
        self.assertEqual(raised.exception.code, 1)
