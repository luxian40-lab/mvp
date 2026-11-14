"""Regresión anclada a AgriCapital prod (2026-11-13/14).

Casos reales:
- Maryuri: último módulo → Compañero anuncia reto final → *continuemos*/«Ok»
  no debe decir «Ya completaste»; debe lanzar Formador. Antes fallaba porque
  progreso.completado=True se marcaba al abrir el checkpoint.
- Elsa: checkpoint mid-curso (asistente_dario) + «Ok» → Formador.
- Legado atrapado: alumnos ya en prod con completado=True + checkpoint
  siguen pudiendo pasar al Formador (bypass).
"""
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from core.intent_detector import (
    mensaje_indica_listo,
    mensaje_indica_listo_o_confirma_handoff,
)
from core.models import Cliente, Curso, Estudiante, Modulo, ProgresoEstudiante
from core.response_templates import get_response_for_intent


def _cliente_curso_mods(*, cedula, telefono, nombre, gamificacion=True):
    cli = Cliente.objects.create(nombre='AgriCapital QA', usar_gamificacion=gamificacion)
    curso = Curso.objects.create(
        nombre='Innovación e IA para nuevos emprendedores',
        usar_gamificacion=gamificacion,
        usar_agentes_ia=True,
        cliente=cli,
    )
    mods = [
        Modulo.objects.create(
            curso=curso, numero=n, titulo=f'M{n}', descripcion='d', contenido=f'c{n}',
        )
        for n in (4, 5)
    ]
    est = Estudiante.objects.create(
        cedula=cedula,
        nombre=nombre,
        telefono=telefono,
        cliente=cli,
        activo=True,
        acepto_terminos=True,
        estado_chat='ACTIVO',
        estado_onboarding='esperando_respuesta_asistente',
    )
    return cli, curso, mods, est


class MaryuriCierreSinCompletadoPrematuroTests(TestCase):
    """Prod: Maryuri Giraldo — Innovación e IA, es_reto_final, dijo Ok."""

    def setUp(self):
        _cli, self.curso, self.mods, self.est = _cliente_curso_mods(
            cedula='QA-MARYURI',
            telefono='573145707550',
            nombre='Maryuri Giraldo Orozco',
        )
        self.prog = ProgresoEstudiante.objects.create(
            estudiante=self.est,
            curso=self.curso,
            modulo_actual=self.mods[-1],
            completado=False,
        )
        self.est.contexto_temporal = {
            'tipo': 'asistente_dario',
            'curso_activo_id': self.curso.id,
            'modulo_id': self.mods[-1].id,
            'progreso_id': self.prog.id,
            'modulos_reto_ids': [m.id for m in self.mods],
            'preguntas_hechas': 0,
            'es_reto_final': True,
        }
        self.est.save(update_fields=['contexto_temporal'])

    def _continuar(self, trigger):
        with patch(
            'core.tutor_ia_modulo.generar_reto_facilitador',
            return_value='RETO_FINAL_PROD_MARYURI',
        ):
            return get_response_for_intent(
                'continuar_leccion',
                self.est.nombre,
                estudiante_id=self.est.id,
                mensaje_original=trigger,
            )

    def test_continuemos_lanza_formador_y_progreso_sigue_activo(self):
        out = self._continuar('continuemos')
        self.assertIn('RETO_FINAL_PROD_MARYURI', out)
        self.assertNotIn('Ya completaste', out)
        self.est.refresh_from_db()
        self.prog.refresh_from_db()
        self.assertEqual(self.est.estado_onboarding, 'esperando_respuesta_reto')
        self.assertTrue((self.est.contexto_temporal or {}).get('es_final'))
        self.assertFalse(self.prog.completado)

    def test_ok_tambien_lanza_formador(self):
        out = self._continuar('Ok')
        self.assertIn('RETO_FINAL_PROD_MARYURI', out)
        self.est.refresh_from_db()
        self.assertEqual(self.est.estado_onboarding, 'esperando_respuesta_reto')


class MaryuriLegadoCompletadoPrematuroTests(TestCase):
    """Alumnos ya marcados completado=True en prod antes del deploy del refactor."""

    def setUp(self):
        _cli, self.curso, self.mods, self.est = _cliente_curso_mods(
            cedula='QA-MARYURI-LEG',
            telefono='573145707551',
            nombre='Maryuri Legado',
        )
        self.prog = ProgresoEstudiante.objects.create(
            estudiante=self.est,
            curso=self.curso,
            modulo_actual=self.mods[-1],
            completado=True,
            fecha_completado=timezone.now(),
        )
        self.est.contexto_temporal = {
            'tipo': 'asistente_dario',
            'curso_activo_id': self.curso.id,
            'modulo_id': self.mods[-1].id,
            'progreso_id': self.prog.id,
            'modulos_reto_ids': [m.id for m in self.mods],
            'preguntas_hechas': 1,
            'es_reto_final': True,
        }
        self.est.save(update_fields=['contexto_temporal'])

    def test_bypass_no_responde_ya_completaste(self):
        with patch(
            'core.tutor_ia_modulo.generar_reto_facilitador',
            return_value='RETO_LEGADO',
        ):
            out = get_response_for_intent(
                'continuar_leccion',
                self.est.nombre,
                estudiante_id=self.est.id,
                mensaje_original='continuemos',
            )
        self.assertIn('RETO_LEGADO', out)
        self.assertNotIn('Ya completaste', out)


class ElsaCheckpointMidCursoTests(TestCase):
    """Prod: Elsa Yubely — Tome las riendas, checkpoint mód. 1-3, sin Formador."""

    def setUp(self):
        cli = Cliente.objects.create(nombre='AgriCapital Elsa QA', usar_gamificacion=True)
        curso = Curso.objects.create(
            nombre='Tome las riendas de su dinero',
            usar_gamificacion=True,
            usar_agentes_ia=True,
            cliente=cli,
        )
        mods = [
            Modulo.objects.create(
                curso=curso, numero=n, titulo=f'M{n}', descripcion='d', contenido=f'c{n}',
            )
            for n in (1, 2, 3)
        ]
        self.est = Estudiante.objects.create(
            cedula='QA-ELSA',
            nombre='Elsa Yubely Volveras',
            telefono='573142656878',
            cliente=cli,
            activo=True,
            acepto_terminos=True,
            estado_chat='ACTIVO',
            estado_onboarding='esperando_respuesta_asistente',
        )
        self.prog = ProgresoEstudiante.objects.create(
            estudiante=self.est,
            curso=curso,
            modulo_actual=mods[-1],
            completado=False,
        )
        self.est.contexto_temporal = {
            'tipo': 'asistente_dario',
            'curso_activo_id': curso.id,
            'modulo_id': mods[-1].id,
            'progreso_id': self.prog.id,
            'modulos_reto_ids': [m.id for m in mods],
            'preguntas_hechas': 0,
        }
        self.est.save(update_fields=['contexto_temporal'])

    def test_ok_lanza_formador_mid_curso(self):
        with patch(
            'core.tutor_ia_modulo.generar_reto_facilitador',
            return_value='RETO_ELSA_MID',
        ):
            out = get_response_for_intent(
                'continuar_leccion',
                self.est.nombre,
                estudiante_id=self.est.id,
                mensaje_original='Ok',
            )
        self.assertIn('RETO_ELSA_MID', out)
        self.est.refresh_from_db()
        self.assertEqual(self.est.estado_onboarding, 'esperando_respuesta_reto')
        self.assertFalse((self.est.contexto_temporal or {}).get('es_final', False))


class ConfirmaCortaSoloHandoffTests(TestCase):
    def test_ok_no_ensancha_listo_global(self):
        for msg in ('Ok', 'dale', 'si', 'sí'):
            with self.subTest(msg=msg):
                self.assertFalse(mensaje_indica_listo(msg))
                self.assertTrue(mensaje_indica_listo_o_confirma_handoff(msg))

    def test_listo_sigue_en_ambos(self):
        self.assertTrue(mensaje_indica_listo('listo'))
        self.assertTrue(mensaje_indica_listo_o_confirma_handoff('listo'))
