"""Foto como evidencia del reto: se guarda, se califica con visión y va al data lake."""
from unittest.mock import MagicMock, patch

from django.test import TestCase

from core.models import (
    Curso,
    Estudiante,
    EstudianteEventoAprendizaje,
    Modulo,
    ProgresoEstudiante,
)
from core.tests_listo_continuar_trigger import _twilio_client_patch

FOTO_BYTES = b'\xff\xd8\xff\xe0fake-jpeg-bytes'


class RetoEvidenciaFotoTests(TestCase):
    def setUp(self):
        self.est = Estudiante.objects.create(
            cedula='10553311',
            nombre='Apicultor Prueba',
            telefono='573005553311',
            acepto_terminos=True,
            estado_chat='ACTIVO',
            estado_onboarding='esperando_respuesta_reto',
        )
        self.curso = Curso.objects.create(
            nombre='Manejo sanitario de abejas',
            dias_espera_entre_modulos=0,
            usar_agentes_ia=True,
            perfil_facilitador='tecnicoagro',
        )
        self.mod = Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='Reconozca el problema antes de actuar',
            descripcion='D',
            contenido='C',
        )
        self.prog = ProgresoEstudiante.objects.create(
            estudiante=self.est,
            curso=self.curso,
            modulo_actual=self.mod,
        )
        self.est.contexto_temporal = {
            'tipo': 'reto_facilitador',
            'reto_texto': 'Revise 10 colmenas y cuente cuántas muestran cría salteada.',
            'modulos_reto_ids': [self.mod.id],
            'progreso_id': self.prog.id,
            'es_final': False,
        }
        self.est.save(update_fields=['contexto_temporal'])

    def _post_foto(self, body=''):
        mock_instance = MagicMock()
        mock_instance.messages.create.return_value = MagicMock(sid='SM_foto')
        FakeTwilioClient = MagicMock(return_value=mock_instance)
        from core.views import _procesar_twilio_webhook

        with _twilio_client_patch(FakeTwilioClient):
            _procesar_twilio_webhook(
                {
                    'Body': body,
                    'From': 'whatsapp:+573005553311',
                    'To': 'whatsapp:+14155238886',
                    'MessageSid': 'SM_foto',
                    'NumMedia': '1',
                    'MediaContentType0': 'image/jpeg',
                    'MediaUrl0': 'https://api.twilio.com/media/abc',
                }
            )
        bodies = [c.kwargs.get('body', '') for c in mock_instance.messages.create.call_args_list]
        return ' '.join(bodies)

    @patch(
        'core.reto_evidencia.evaluar_evidencia_foto',
        return_value=(8, 'Se observa cría salteada en el marco; tome muestra de 30 abejas.'),
    )
    @patch(
        'core.reto_evidencia.descargar_media_twilio',
        return_value=(FOTO_BYTES, 'image/jpeg'),
    )
    def test_foto_se_califica_y_no_pide_texto(self, _mock_dl, _mock_vision):
        texto = self._post_foto()

        self.assertIn('cría salteada', texto)
        self.assertNotIn('necesito su respuesta en texto o audio', texto)
        self.est.refresh_from_db()
        self.assertEqual(self.est.estado_onboarding, 'completado')

    @patch(
        'core.reto_evidencia.evaluar_evidencia_foto',
        return_value=(8, 'Evidencia válida.'),
    )
    @patch(
        'core.reto_evidencia.descargar_media_twilio',
        return_value=(FOTO_BYTES, 'image/jpeg'),
    )
    def test_foto_emite_evento_reto_respondido(self, _mock_dl, _mock_vision):
        self._post_foto()

        ev = EstudianteEventoAprendizaje.objects.filter(
            estudiante=self.est,
            tipo=EstudianteEventoAprendizaje.TIPO_RETO_RESPONDIDO,
        ).first()
        self.assertIsNotNone(ev)
        self.assertEqual(ev.metadata.get('tipo_respuesta'), 'foto')
        self.assertEqual(ev.metadata.get('puntaje'), 8)
        self.assertEqual(ev.metadata.get('perfil_facilitador'), 'tecnicoagro')
        self.assertEqual(ev.curso_id, self.curso.id)

    @patch('core.reto_evidencia.evaluar_evidencia_foto', return_value=None)
    @patch(
        'core.reto_evidencia.descargar_media_twilio',
        return_value=(FOTO_BYTES, 'image/jpeg'),
    )
    def test_foto_sin_vision_no_castiga_al_estudiante(self, _mock_dl, _mock_vision):
        texto = self._post_foto()

        self.assertIn('Recibí su foto', texto)
        self.est.refresh_from_db()
        self.assertEqual(self.est.estado_onboarding, 'esperando_respuesta_reto')

    @patch(
        'core.reto_evidencia.evaluar_evidencia_foto',
        return_value=(9, 'Buena evidencia.'),
    )
    @patch(
        'core.reto_evidencia.descargar_media_twilio',
        return_value=(FOTO_BYTES, 'image/jpeg'),
    )
    def test_foto_se_guarda_y_queda_en_el_evento(self, _mock_dl, _mock_vision):
        with patch('core.reto_evidencia.guardar_evidencia', return_value='https://s3/ev.jpg'):
            self._post_foto()

        ev = EstudianteEventoAprendizaje.objects.filter(
            estudiante=self.est,
            tipo=EstudianteEventoAprendizaje.TIPO_RETO_RESPONDIDO,
        ).first()
        self.assertEqual(ev.metadata.get('evidencia_url'), 'https://s3/ev.jpg')

    @patch('core.tutor_ia_modulo.evaluar_reto_facilitador', return_value=(7, 'Buen registro.'))
    def test_respuesta_de_texto_tambien_emite_evento(self, _mock_eval):
        mock_instance = MagicMock()
        mock_instance.messages.create.return_value = MagicMock(sid='SM_txt')
        FakeTwilioClient = MagicMock(return_value=mock_instance)
        from core.views import _procesar_twilio_webhook

        with _twilio_client_patch(FakeTwilioClient):
            _procesar_twilio_webhook(
                {
                    'Body': 'Revisé 10 colmenas, 3 con cría salteada; tomaré muestra.',
                    'From': 'whatsapp:+573005553311',
                    'To': 'whatsapp:+14155238886',
                    'MessageSid': 'SM_txt',
                    'NumMedia': '0',
                }
            )

        ev = EstudianteEventoAprendizaje.objects.filter(
            estudiante=self.est,
            tipo=EstudianteEventoAprendizaje.TIPO_RETO_RESPONDIDO,
        ).first()
        self.assertIsNotNone(ev)
        self.assertEqual(ev.metadata.get('tipo_respuesta'), 'texto')
        self.assertIn('cría salteada', ev.metadata.get('respuesta_texto', ''))
