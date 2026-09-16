"""El calificador del reto debe citar evidencia y exigir cifras (perfil tecnicoagro)."""
from django.test import TestCase

from core.facilitador_perfil import system_prompt_evaluacion_para_curso
from core.models import Cliente, Curso
from core.tutor_ia_modulo import limpiar_plantilla_evaluacion


class LimpiarPlantillaEvaluacionTests(TestCase):
    def test_quita_enunciado_de_rubrica_copiado(self):
        feedback = (
            '1. Identificó bien los síntomas.\n'
            '5. Veredicto por componente (Diagnóstico / Acción) logrado/parcial/no logrado. '
            'Diagnóstico logrado / Acción parcial.'
        )

        limpio = limpiar_plantilla_evaluacion(feedback)

        self.assertNotIn('logrado/parcial/no logrado', limpio)
        self.assertIn('Diagnóstico logrado / Acción parcial.', limpio)

    def test_quita_linea_de_instruccion_suelta(self):
        feedback = (
            '1. Retroalimentación positiva primero (qué hizo bien).\n'
            '2. Revisó 10 colmenas y reportó 3 con cría salteada.'
        )

        limpio = limpiar_plantilla_evaluacion(feedback)

        self.assertNotIn('Retroalimentación positiva primero', limpio)
        self.assertIn('Revisó 10 colmenas', limpio)

    def test_feedback_limpio_no_cambia(self):
        feedback = 'Usted reportó "3 de 10 colmenas con cría salteada". Falta el conteo de varroa.'
        self.assertEqual(limpiar_plantilla_evaluacion(feedback), feedback)


class PromptEvaluacionTecnicoagroTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(nombre='Org Rigor', activo=True)
        self.curso = Curso.objects.create(
            nombre='Apiarios rigor',
            cliente=self.cliente,
            activo=True,
            perfil_facilitador=Curso.PERFIL_FACILITADOR_TECNICOAGRO,
        )

    def test_puntos_exige_cita_y_cifras_sin_castigar_foto(self):
        prompt = system_prompt_evaluacion_para_curso(self.curso, usar_notas=False)

        self.assertIn('citando TEXTUALMENTE', prompt)
        self.assertIn('sin ninguna cifra ni conteo', prompt)
        self.assertIn('su ausencia NO baja el puntaje', prompt)
        self.assertIn('PROHIBIDO elogios sin evidencia', prompt)

    def test_notas_mantiene_misma_exigencia(self):
        prompt = system_prompt_evaluacion_para_curso(self.curso, usar_notas=True)

        self.assertIn('citando TEXTUALMENTE', prompt)
        self.assertIn('sin ninguna cifra ni conteo', prompt)
        self.assertIn('su ausencia NO baja la nota', prompt)

    def test_formato_numerado_se_mantiene(self):
        prompt = system_prompt_evaluacion_para_curso(self.curso, usar_notas=False)

        self.assertIn('Puntaje total: X/10', prompt)
        self.assertIn('Desglose: Enfoque X/3', prompt)
