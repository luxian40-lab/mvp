"""Regresión: Continuemos no debe caer por NameError en _preparar_progresos."""
from django.test import TestCase

from core.models import Cliente, Curso, Estudiante, Modulo, ProgresoEstudiante
from core.response_templates import get_response_for_intent


class ContinuarLeccionImportsTests(TestCase):
    def test_continuemos_no_nameerror(self):
        cliente = Cliente.objects.create(nombre='Org cont')
        curso = Curso.objects.create(nombre='Curso cont', cliente=cliente)
        mod = Modulo.objects.create(curso=curso, numero=1, titulo='M1', contenido='HOLA_CONT')
        est = Estudiante.objects.create(
            nombre='Cont Test',
            telefono='573009991888',
            cliente=cliente,
            estado_chat='ACTIVO',
            estado_onboarding='completado',
            acepto_terminos=True,
        )
        ProgresoEstudiante.objects.create(
            estudiante=est,
            curso=curso,
            modulo_actual=mod,
            paso_actual_modulo=1,
        )
        texto = get_response_for_intent(
            'continuar_leccion',
            est.nombre,
            estudiante_id=est.id,
            mensaje_original='continuemos',
        )
        self.assertIsInstance(texto, str)
        self.assertTrue(len(texto) > 0)
        self.assertNotIn('problema técnico', texto.lower())
