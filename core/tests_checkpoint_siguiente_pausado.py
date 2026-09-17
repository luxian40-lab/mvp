"""Checkpoint IA al cerrar mÃ³dulo cuando el siguiente estÃ¡ pausado (borrador WA).

Caso real: curso Agrosavia con M1 activo y M2â€“M4 pausados. El reto del
facilitador debe dispararse igual; el bloqueo de contenido pendiente llega
despuÃ©s de responderlo.
"""
from django.test import TestCase
from django.test.utils import override_settings

from core.models import (
    Cliente,
    Curso,
    Estudiante,
    Modulo,
    ModuloCompletado,
    PasoModulo,
    PreguntaModulo,
    ProgresoEstudiante,
    SeccionModulo,
)
from core.response_templates import get_response_for_intent


class CheckpointConSiguientePausadoTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(nombre='QA Checkpoint', activo=True)
        self.curso = Curso.objects.create(
            nombre='QA Checkpoint Pausado',
            cliente=self.cliente,
            activo=True,
            usar_agentes_ia=True,
            dias_espera_entre_modulos=0,
            nombre_agente_asistente='CompaÃ±ero',
            nombre_agente_tutor='Asesor',
        )
        self.est = Estudiante.objects.create(
            cedula='QA-CP-001',
            nombre='Tester Checkpoint',
            telefono='573026480001',
            cliente=self.cliente,
            activo=True,
            acepto_terminos=True,
            estado_chat='ACTIVO',
            estado_onboarding='completado',
        )
        self.m1 = Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='M1 checkpoint',
            descripcion='d',
            contenido='Contenido M1',
            publicado_wa=True,
            modo_entrega=Modulo.MODO_ENTREGA_PASOS,
            facilitador_checkpoint=Modulo.FACILITADOR_CP_SI,
        )
        sec1 = SeccionModulo.objects.create(modulo=self.m1, orden=1, titulo='S1')
        PasoModulo.objects.create(
            modulo=self.m1,
            seccion=sec1,
            orden=1,
            titulo='P1',
            contenido='Micro M1',
            activo=True,
        )
        self.m2 = Modulo.objects.create(
            curso=self.curso,
            numero=2,
            titulo='M2 pausado',
            descripcion='d',
            contenido='Contenido M2',
            publicado_wa=False,
            modo_entrega=Modulo.MODO_ENTREGA_PASOS,
        )
        sec2 = SeccionModulo.objects.create(modulo=self.m2, orden=1, titulo='S2')
        PasoModulo.objects.create(
            modulo=self.m2,
            seccion=sec2,
            orden=1,
            titulo='P2',
            contenido='Micro M2',
            activo=True,
        )
        self.prog = ProgresoEstudiante.objects.create(
            estudiante=self.est,
            curso=self.curso,
            modulo_actual=self.m1,
            paso_actual_modulo=2,
        )

    def _listo(self):
        return get_response_for_intent(
            'continuar_leccion',
            self.est.nombre,
            estudiante_id=self.est.id,
            mensaje_original='listo',
        )

    def test_checkpoint_si_dispara_reto_aunque_siguiente_este_pausado(self):
        resp = self._listo()

        self.assertNotIn('le avisamos', resp.lower())
        self.assertIn('CompaÃ±ero', resp)
        self.est.refresh_from_db()
        self.assertEqual(self.est.estado_onboarding, 'esperando_respuesta_asistente')
        ctx = self.est.contexto_temporal or {}
        self.assertEqual(ctx.get('tipo'), 'asistente_dario')
        self.assertEqual(ctx.get('modulo_id'), self.m1.id)
        self.prog.refresh_from_db()
        self.assertEqual(self.prog.modulo_actual_id, self.m1.id)

    def test_modulo_sin_checkpoint_sigue_bloqueado(self):
        """BeyoncÃ©: sin checkpoint, el bloqueo por mÃ³dulo en borrador se mantiene."""
        self.m1.facilitador_checkpoint = Modulo.FACILITADOR_CP_NO
        self.m1.save(update_fields=['facilitador_checkpoint'])

        resp = self._listo()

        self.assertIn('le avisamos', resp.lower())
        self.est.refresh_from_db()
        self.assertNotEqual(self.est.estado_onboarding, 'esperando_respuesta_asistente')

    def test_checkpoint_no_se_repite_si_modulo_ya_completado(self):
        """Anti-loop: tras el reto el puntero sigue en M1; no volver a lanzarlo."""
        ModuloCompletado.objects.create(progreso=self.prog, modulo=self.m1)

        resp = self._listo()

        self.assertIn('le avisamos', resp.lower())
        self.est.refresh_from_db()
        self.assertNotEqual(self.est.estado_onboarding, 'esperando_respuesta_asistente')


@override_settings(TWILIO_ACCOUNT_SID='', TWILIO_AUTH_TOKEN='')
class CheckpointMiniExamenConSiguientePausadoTests(TestCase):
    """Mismo gate, pero cerrando el mÃ³dulo con mini examen (PreguntaModulo)."""

    def setUp(self):
        self.cliente = Cliente.objects.create(nombre='QA Checkpoint Examen', activo=True)
        self.curso = Curso.objects.create(
            nombre='QA Checkpoint Examen',
            cliente=self.cliente,
            activo=True,
            usar_agentes_ia=True,
            dias_espera_entre_modulos=0,
            nombre_agente_asistente='CompaÃ±ero',
            nombre_agente_tutor='Asesor',
        )
        self.est = Estudiante.objects.create(
            cedula='QA-CP-002',
            nombre='Tester Examen',
            telefono='573026480002',
            cliente=self.cliente,
            activo=True,
            acepto_terminos=True,
            estado_chat='ACTIVO',
        )
        self.m1 = Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='M1 con examen',
            descripcion='d',
            contenido='Contenido M1',
            publicado_wa=True,
            facilitador_checkpoint=Modulo.FACILITADOR_CP_SI,
        )
        self.m2 = Modulo.objects.create(
            curso=self.curso,
            numero=2,
            titulo='M2 pausado',
            descripcion='d',
            contenido='Contenido M2',
            publicado_wa=False,
        )
        self.pregunta = PreguntaModulo.objects.create(
            modulo=self.m1,
            pregunta='Â¿QuÃ© revisa primero?',
            opcion_a='La piquera',
            opcion_b='Nada',
            respuesta_correcta='A',
        )
        self.prog = ProgresoEstudiante.objects.create(
            estudiante=self.est,
            curso=self.curso,
            modulo_actual=self.m1,
        )
        self.est.contexto_temporal = {
            'modulo_id': self.m1.id,
            'pregunta_id': self.pregunta.id,
            'progreso_id': self.prog.id,
            'tipo': 'pregunta_modulo',
        }
        self.est.estado_onboarding = 'esperando_respuesta_modulo'
        self.est.save(update_fields=['contexto_temporal', 'estado_onboarding'])

    def _responder(self, body='A'):
        from core.views import _procesar_twilio_webhook

        _procesar_twilio_webhook(
            {
                'Body': body,
                'From': f'whatsapp:+{self.est.telefono}',
                'To': 'whatsapp:+14155238886',
                'MessageSid': 'SM_test_checkpoint_examen',
                'NumMedia': '0',
            }
        )

    def test_checkpoint_si_dispara_reto_aunque_siguiente_este_pausado(self):
        self._responder()

        self.est.refresh_from_db()
        self.assertEqual(self.est.estado_onboarding, 'esperando_respuesta_asistente')
        ctx = self.est.contexto_temporal or {}
        self.assertEqual(ctx.get('tipo'), 'asistente_dario')
        self.assertEqual(ctx.get('modulo_id'), self.m1.id)
        self.prog.refresh_from_db()
        self.assertEqual(self.prog.modulo_actual_id, self.m1.id)

    def test_modulo_sin_checkpoint_sigue_bloqueado(self):
        self.m1.facilitador_checkpoint = Modulo.FACILITADOR_CP_NO
        self.m1.save(update_fields=['facilitador_checkpoint'])

        self._responder()

        self.est.refresh_from_db()
        self.assertNotEqual(self.est.estado_onboarding, 'esperando_respuesta_asistente')
