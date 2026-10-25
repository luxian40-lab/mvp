"""Estados del motor que el contrato de estados no alcanza por la línea 2.

`esperando_respuesta_recuperacion` solo corre con *listo* y el curso ya
completado: con un progreso abierto, *listo* fuerza `completado` antes de la
cadena de agentes, y cualquier otro texto se corta con "No entendí".
"""
from unittest.mock import MagicMock, patch

from django.test import TestCase

from core.models import Cliente, Curso, Estudiante, Modulo, ProgresoEstudiante, WhatsappLog


def _twilio_ok():
    instancia = MagicMock()
    instancia.messages.create.return_value = MagicMock(sid='SM_legado')
    return MagicMock(return_value=instancia)


class RecuperacionTests(TestCase):
    def setUp(self):
        cliente = Cliente.objects.create(nombre='Legado', activo=True)
        self.curso = Curso.objects.create(
            nombre='Curso legado', cliente=cliente, activo=True, dias_espera_entre_modulos=0,
        )
        modulo = Modulo.objects.create(
            curso=self.curso, numero=1, titulo='M1', descripcion='d', contenido='c', publicado_wa=True,
        )
        self.est = Estudiante.objects.create(
            cedula='LEGADO-1', nombre='Ana Legado', telefono='573223031100', cliente=cliente,
            activo=True, acepto_terminos=True, estado_chat='ACTIVO',
            estado_onboarding='esperando_respuesta_recuperacion',
            contexto_temporal={
                'pregunta_data': {'correcta': 'B', 'explicacion': 'EXPLICACION_FIJA'},
                'curso_id': self.curso.id,
            },
        )
        ProgresoEstudiante.objects.create(
            estudiante=self.est, curso=self.curso, modulo_actual=modulo, completado=True,
        )

    def _escribir(self, texto):
        from core.views import _procesar_twilio_webhook

        with patch('builtins.print'), patch('twilio.rest.Client', _twilio_ok()), patch(
            'core.response_templates._generar_completado_final', return_value='CIERRE_FINAL_FIJO',
        ) as cierre:
            _procesar_twilio_webhook({
                'Body': texto,
                'From': f'whatsapp:+{self.est.telefono}',
                'To': 'whatsapp:+14155238886',
                'MessageSid': f'SM_legado_{texto}',
                'NumMedia': '0',
            })
        self.est.refresh_from_db()
        enviados = ' '.join(
            WhatsappLog.objects.filter(telefono__endswith=self.est.telefono[-10:], tipo='SENT')
            .values_list('mensaje', flat=True)
        )
        return enviados, cierre

    def test_listo_con_curso_completado_evalua_y_cierra_el_curso(self):
        enviados, cierre = self._escribir('listo')
        cierre.assert_called_once_with(self.est, self.curso.id)
        self.assertIn('La respuesta correcta era *B*', enviados)
        self.assertIn('EXPLICACION_FIJA', enviados)
        self.assertIn('CIERRE_FINAL_FIJO', enviados)
        self.assertEqual(self.est.estado_onboarding, 'completado')
        self.assertIsNone(self.est.contexto_temporal)

    def test_letra_de_respuesta_no_llega_a_la_rama(self):
        enviados, cierre = self._escribir('B')
        cierre.assert_not_called()
        self.assertIn('No entendí', enviados)
        self.assertEqual(self.est.estado_onboarding, 'esperando_respuesta_recuperacion')
