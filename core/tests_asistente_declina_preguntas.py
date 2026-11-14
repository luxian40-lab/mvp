"""Pausa Compañero: «No tengo preguntas» avanza al Formador sin LLM ni cupo."""
from unittest.mock import patch

from django.test import TestCase, override_settings

from core.models import Cliente, Curso, Estudiante, Modulo, ProgresoEstudiante


@override_settings(EKI_CONTEXTO_CONSERVA_CLAVES=True)
class AsistenteDeclinaPreguntasTests(TestCase):
    def setUp(self):
        self.cli = Cliente.objects.create(nombre='Org Declina', activo=True)
        self.curso = Curso.objects.create(
            nombre='Declina', cliente=self.cli, activo=True, dias_espera_entre_modulos=0,
        )
        self.mod = Modulo.objects.create(
            curso=self.curso, numero=1, titulo='M1', descripcion='d', contenido='c',
            publicado_wa=True,
        )
        self.est = Estudiante.objects.create(
            cedula='CC-DECLINA', nombre='Oscar', telefono='573108603813',
            cliente=self.cli, activo=True, acepto_terminos=True, estado_chat='ACTIVO',
        )
        self.progreso = ProgresoEstudiante.objects.create(
            estudiante=self.est, curso=self.curso, modulo_actual=self.mod,
        )

    def _en_pausa(self, preguntas_hechas=0):
        self.est.estado_onboarding = 'esperando_respuesta_asistente'
        self.est.contexto_temporal = {
            'tipo': 'asistente_dario',
            'preguntas_hechas': preguntas_hechas,
            'modulos_reto_ids': [self.mod.id],
            'progreso_id': self.progreso.id,
            'curso_activo_id': self.curso.id,
        }
        self.est.save()

    def test_no_tengo_preguntas_abre_reto_sin_llm(self):
        from core.conversacion.contexto import Contexto
        from core.conversacion.estados import asistente

        self._en_pausa(preguntas_hechas=0)
        with patch(
            'core.tutor_ia_modulo.generar_reto_facilitador', return_value='Reto finca raíz.',
        ), patch(
            'core.tutor_ia_modulo.generar_respuesta_asistente',
        ) as mock_asistente:
            out = asistente.manejar(
                Contexto(self.est, 'No tengo preguntas.', self.est.telefono, self.est.telefono),
            )
        mock_asistente.assert_not_called()
        self.est.refresh_from_db()
        self.assertEqual(self.est.estado_onboarding, 'esperando_respuesta_reto')
        self.assertEqual((self.est.contexto_temporal or {}).get('preguntas_hechas'), None)
        self.assertEqual((self.est.contexto_temporal or {}).get('tipo'), 'reto_facilitador')
        self.assertIn('Reto finca raíz', out.texto)

    def test_pregunta_real_sigue_al_companero(self):
        from core.conversacion.contexto import Contexto
        from core.conversacion.estados import asistente

        self._en_pausa(preguntas_hechas=0)
        with patch(
            'core.tutor_ia_modulo.generar_respuesta_asistente',
            return_value='El interés compuesto multiplica el capital.',
        ) as mock_asistente:
            out = asistente.manejar(
                Contexto(
                    self.est,
                    '¿qué es el interés compuesto?',
                    self.est.telefono,
                    self.est.telefono,
                ),
            )
        mock_asistente.assert_called_once()
        self.est.refresh_from_db()
        self.assertEqual(self.est.estado_onboarding, 'esperando_respuesta_asistente')
        self.assertEqual((self.est.contexto_temporal or {}).get('preguntas_hechas'), 1)
        self.assertIn('interés compuesto', out.texto.lower())

    def test_continuemos_sigue_abriendo_reto(self):
        from core.conversacion.contexto import Contexto
        from core.conversacion.estados import asistente

        self._en_pausa(preguntas_hechas=0)
        with patch(
            'core.tutor_ia_modulo.generar_reto_facilitador', return_value='Reto continuar.',
        ), patch(
            'core.tutor_ia_modulo.generar_respuesta_asistente',
        ) as mock_asistente:
            asistente.manejar(
                Contexto(self.est, 'continuemos', self.est.telefono, self.est.telefono),
            )
        mock_asistente.assert_not_called()
        self.est.refresh_from_db()
        self.assertEqual(self.est.estado_onboarding, 'esperando_respuesta_reto')
