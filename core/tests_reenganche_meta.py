"""Reenganche drip solo por Graph, y los dry-run no envían."""
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from core.models import Curso, Estudiante, Modulo, ProgresoEstudiante, WhatsappLog
from core.tasks import reenganche_drip_content_diario


def _par(telefono, dias=2):
    curso = Curso.objects.create(
        nombre=f'Curso {telefono[-4:]}',
        descripcion='d',
        dias_espera_entre_modulos=dias,
    )
    actual = Modulo.objects.create(
        curso=curso, numero=1, titulo='M1', descripcion='d', contenido='c', duracion_dias=1,
    )
    Modulo.objects.create(
        curso=curso, numero=2, titulo='M2', descripcion='d', contenido='c', duracion_dias=1,
    )
    estudiante = Estudiante.objects.create(
        cedula=f'CC{telefono[-6:]}',
        nombre='Ana',
        telefono=telefono,
    )
    ProgresoEstudiante.objects.create(
        estudiante=estudiante,
        curso=curso,
        modulo_actual=actual,
        fecha_ultimo_avance=timezone.now() - timedelta(days=dias),
    )
    return estudiante


@override_settings(META_REENGANCHE_ENABLED=True, META_TEMPLATE_DRIP_REENGANCHE='', WA_VENTANA_HORAS=24)
class ReengancheMetaTests(TestCase):
    def test_ventana_abierta_manda_texto(self):
        estudiante = _par('573001110001')
        WhatsappLog.objects.create(
            telefono=estudiante.telefono,
            mensaje='listo',
            tipo='INCOMING',
            canal='meta',
            estudiante=estudiante,
            fecha=timezone.now(),
        )
        with patch('core.sandbox_canal.enviar_meta', return_value={'success': True}) as texto, \
                patch('core.sandbox_canal.enviar_meta_plantilla') as plantilla:
            resultado = reenganche_drip_content_diario()
        self.assertEqual(resultado['enviados'], 1)
        texto.assert_called_once()
        plantilla.assert_not_called()

    @override_settings(META_TEMPLATE_DRIP_REENGANCHE='drip_reenganche')
    def test_ventana_cerrada_manda_plantilla(self):
        _par('573001110002')
        with patch('core.sandbox_canal.enviar_meta') as texto, \
                patch('core.sandbox_canal.enviar_meta_plantilla', return_value={'success': True}) as plantilla:
            resultado = reenganche_drip_content_diario()
        self.assertEqual(resultado['enviados'], 1)
        self.assertEqual(resultado['omitidos_sin_ventana'], 0)
        texto.assert_not_called()
        plantilla.assert_called_once()
        self.assertEqual(plantilla.call_args.args[1], 'drip_reenganche')

    def test_entrante_twilio_no_abre_la_ventana_meta(self):
        estudiante = _par('573001110004')
        WhatsappLog.objects.create(
            telefono=estudiante.telefono,
            mensaje='listo',
            tipo='INCOMING',
            canal='twilio',
            estudiante=estudiante,
            fecha=timezone.now(),
        )
        with patch('core.sandbox_canal.enviar_meta') as texto, \
                patch('core.sandbox_canal.enviar_meta_plantilla') as plantilla:
            resultado = reenganche_drip_content_diario()
        self.assertEqual(resultado['omitidos_sin_ventana'], 1)
        texto.assert_not_called()
        plantilla.assert_not_called()

    def test_ventana_cerrada_sin_plantilla_no_envia(self):
        _par('573001110003')
        with patch('core.sandbox_canal.enviar_meta') as texto, \
                patch('core.sandbox_canal.enviar_meta_plantilla') as plantilla:
            resultado = reenganche_drip_content_diario()
        self.assertEqual(resultado['enviados'], 0)
        self.assertEqual(resultado['omitidos_sin_ventana'], 1)
        texto.assert_not_called()
        plantilla.assert_not_called()

    def test_dry_run_no_envia_y_enmascara(self):
        _par('573001110099')
        salida = StringIO()
        with patch('core.sandbox_canal.enviar_meta') as texto:
            call_command('reenganche_dry_run', '--dias', '1', stdout=salida)
        texto.assert_not_called()
        texto_salida = salida.getvalue()
        self.assertIn('***0099', texto_salida)
        self.assertNotIn('573001110099', texto_salida)
        self.assertIn('omitidos_sin_ventana=1', texto_salida)
