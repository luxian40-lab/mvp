"""Pausa Compañero: LLM solo si parece pregunta; ambiguo repregunta sin cupo."""
from unittest.mock import patch

from django.test import TestCase, override_settings

from core.models import Cliente, Curso, Estudiante, Modulo, ProgresoEstudiante


@override_settings(EKI_CONTEXTO_CONSERVA_CLAVES=True)
class AsistenteEsPreguntaTests(TestCase):
    def setUp(self):
        self.cli = Cliente.objects.create(nombre='Org EsPreg', activo=True)
        self.curso = Curso.objects.create(
            nombre='EsPreg', cliente=self.cli, activo=True, dias_espera_entre_modulos=0,
        )
        self.mod = Modulo.objects.create(
            curso=self.curso, numero=1, titulo='M1', descripcion='d', contenido='c',
            publicado_wa=True,
        )
        self.est = Estudiante.objects.create(
            cedula='CC-ESPREG', nombre='Ana', telefono='573109991122',
            cliente=self.cli, activo=True, acepto_terminos=True, estado_chat='ACTIVO',
        )
        self.progreso = ProgresoEstudiante.objects.create(
            estudiante=self.est, curso=self.curso, modulo_actual=self.mod,
        )

    def _en_pausa(self, **extra):
        self.est.estado_onboarding = 'esperando_respuesta_asistente'
        self.est.contexto_temporal = {
            'tipo': 'asistente_dario',
            'preguntas_hechas': 0,
            'modulos_reto_ids': [self.mod.id],
            'progreso_id': self.progreso.id,
            'curso_activo_id': self.curso.id,
            **extra,
        }
        self.est.save()

    def test_todo_bien_abre_reto_sin_llm(self):
        from core.conversacion.contexto import Contexto
        from core.conversacion.estados import asistente

        self._en_pausa()
        with patch(
            'core.agentes.tutor_ia_modulo.generar_reto_facilitador', return_value='Reto cierre.',
        ), patch(
            'core.agentes.tutor_ia_modulo.generar_respuesta_asistente',
        ) as mock_asistente:
            asistente.manejar(Contexto(self.est, 'todo bien', self.est.telefono, self.est.telefono))
        mock_asistente.assert_not_called()
        self.est.refresh_from_db()
        self.assertEqual(self.est.estado_onboarding, 'esperando_respuesta_reto')

    def test_pregunta_clara_usa_cupo(self):
        from core.conversacion.contexto import Contexto
        from core.conversacion.estados import asistente

        self._en_pausa()
        with patch(
            'core.agentes.tutor_ia_modulo.generar_respuesta_asistente',
            return_value='Respuesta clara.',
        ) as mock_asistente:
            out = asistente.manejar(
                Contexto(
                    self.est, '¿qué es el interés compuesto?', self.est.telefono, self.est.telefono,
                ),
            )
        mock_asistente.assert_called_once()
        self.est.refresh_from_db()
        self.assertEqual(self.est.estado_onboarding, 'esperando_respuesta_asistente')
        self.assertEqual((self.est.contexto_temporal or {}).get('preguntas_hechas'), 1)
        self.assertIn('Respuesta clara', out.texto)

    def test_ambiguo_repregunta_sin_cupo_ni_llm(self):
        from core.conversacion.contexto import Contexto
        from core.conversacion.estados import asistente

        self._en_pausa()
        with patch('core.agentes.tutor_ia_modulo.generar_respuesta_asistente') as mock_asistente:
            out = asistente.manejar(
                Contexto(self.est, 'bla bla', self.est.telefono, self.est.telefono),
            )
        mock_asistente.assert_not_called()
        self.est.refresh_from_db()
        self.assertEqual(self.est.estado_onboarding, 'esperando_respuesta_asistente')
        self.assertEqual((self.est.contexto_temporal or {}).get('preguntas_hechas'), 0)
        self.assertTrue((self.est.contexto_temporal or {}).get('repregunta_companero'))
        self.assertIn('pregunta sobre el curso', out.texto.lower())
        self.assertIn('[SEND_BUTTON:continuemos]', out.texto)

    def test_segunda_ambiguedad_abre_reto(self):
        from core.conversacion.contexto import Contexto
        from core.conversacion.estados import asistente

        self._en_pausa(repregunta_companero=True)
        with patch(
            'core.agentes.tutor_ia_modulo.generar_reto_facilitador', return_value='Reto tras ambiguo.',
        ), patch(
            'core.agentes.tutor_ia_modulo.generar_respuesta_asistente',
        ) as mock_asistente:
            out = asistente.manejar(
                Contexto(self.est, 'mmm no se', self.est.telefono, self.est.telefono),
            )
        mock_asistente.assert_not_called()
        self.est.refresh_from_db()
        self.assertEqual(self.est.estado_onboarding, 'esperando_respuesta_reto')
        self.assertIn('Reto tras ambiguo', out.texto)

    def test_ok_handoff_sigue_abriendo_reto(self):
        from core.conversacion.contexto import Contexto
        from core.conversacion.estados import asistente

        self._en_pausa()
        with patch(
            'core.agentes.tutor_ia_modulo.generar_reto_facilitador', return_value='Reto ok.',
        ), patch(
            'core.agentes.tutor_ia_modulo.generar_respuesta_asistente',
        ) as mock_asistente:
            asistente.manejar(Contexto(self.est, 'Ok', self.est.telefono, self.est.telefono))
        mock_asistente.assert_not_called()
        self.est.refresh_from_db()
        self.assertEqual(self.est.estado_onboarding, 'esperando_respuesta_reto')
