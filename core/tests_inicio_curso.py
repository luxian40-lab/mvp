"""El primer continuar de un curso nuevo manda el saludo y el módulo 1."""
import time

from django.test import TestCase

from core.models import Curso, Estudiante, Modulo, ModuloCompletado, ProgresoEstudiante
from core.response_templates import get_response_for_intent


class PrimeraEntregaTests(TestCase):
    def setUp(self):
        self.curso = Curso.objects.create(
            nombre='Tome las riendas',
            descripcion='d',
            dias_espera_entre_modulos=0,
        )
        self.mod1 = Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='El punto de partida',
            descripcion='d',
            contenido='TEXTO_MODULO_1',
        )
        self.mod2 = Modulo.objects.create(
            curso=self.curso,
            numero=2,
            titulo='El siguiente',
            descripcion='d',
            contenido='TEXTO_MODULO_2',
        )
        self.est = Estudiante.objects.create(
            cedula='9001001',
            nombre='Ana',
            telefono='573009001001',
            acepto_terminos=True,
            estado_chat='ACTIVO',
            estado_onboarding='completado',
            contexto_temporal={'inicio_pendiente_curso_id': self.curso.id},
        )
        self.prog = ProgresoEstudiante.objects.create(
            estudiante=self.est,
            curso=self.curso,
            modulo_actual=self.mod1,
        )

    def _continuar(self):
        return get_response_for_intent(
            'continuar_leccion',
            self.est.nombre,
            estudiante_id=self.est.id,
            mensaje_original='continuar',
        )

    def test_el_primer_continuar_manda_saludo_y_modulo_1(self):
        respuesta = self._continuar()
        self.assertIn('Formador', respuesta)
        self.assertIn('Compañero', respuesta)
        self.assertIn('TEXTO_MODULO_1', respuesta)
        self.assertNotIn('TEXTO_MODULO_2', respuesta)
        self.prog.refresh_from_db()
        self.assertEqual(self.prog.modulo_actual_id, self.mod1.id)
        self.assertFalse(ModuloCompletado.objects.filter(progreso=self.prog).exists())

    def test_el_segundo_continuar_sigue_sin_repetir_el_saludo(self):
        self._continuar()
        self.est.refresh_from_db()
        ctx = dict(self.est.contexto_temporal or {})
        ctx['_ts_leccion'] = time.time() - 60
        ctx.pop('_leccion_enviando', None)
        self.est.contexto_temporal = ctx
        self.est.save(update_fields=['contexto_temporal'])
        respuesta = self._continuar()
        self.assertNotIn('Soy el Formador', respuesta)
        self.assertIn('TEXTO_MODULO_2', respuesta)
        self.prog.refresh_from_db()
        self.assertEqual(self.prog.modulo_actual_id, self.mod2.id)

    def test_quien_ya_iba_en_el_modulo_1_avanza_sin_saludo(self):
        self.est.contexto_temporal = {}
        self.est.save(update_fields=['contexto_temporal'])
        respuesta = self._continuar()
        self.assertNotIn('Soy el Formador', respuesta)
        self.assertIn('TEXTO_MODULO_2', respuesta)
        self.prog.refresh_from_db()
        self.assertEqual(self.prog.modulo_actual_id, self.mod2.id)
