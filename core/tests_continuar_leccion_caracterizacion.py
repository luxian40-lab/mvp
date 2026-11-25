"""Caracterización mínima de continuar_leccion antes de partir helpers (H4)."""
from django.test import TestCase

from core.models import Cliente, Curso, Estudiante, Modulo, ProgresoEstudiante
from core.response_templates import get_response_for_intent


class ContinuarLeccionCaracterizacionTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(nombre='Org caract')
        self.curso = Curso.objects.create(
            nombre='Curso caract',
            cliente=self.cliente,
            usar_agentes_ia=False,
            dias_espera_entre_modulos=0,
        )
        self.m1 = Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='Primer módulo',
            contenido='CONTENIDO_CARACT_M1',
            duracion_dias=7,
        )
        self.m2 = Modulo.objects.create(
            curso=self.curso,
            numero=2,
            titulo='Segundo módulo',
            contenido='CONTENIDO_CARACT_M2',
            duracion_dias=7,
        )
        self.est = Estudiante.objects.create(
            nombre='Caract Test',
            telefono='573009991777',
            cliente=self.cliente,
            estado_chat='ACTIVO',
            estado_onboarding='completado',
            acepto_terminos=True,
        )
        ProgresoEstudiante.objects.create(
            estudiante=self.est,
            curso=self.curso,
            modulo_actual=self.m1,
        )

    def test_listo_legacy_avanza_y_muestra_modulo_2(self):
        texto = get_response_for_intent(
            'continuar_leccion',
            self.est.nombre,
            estudiante_id=self.est.id,
            mensaje_original='listo',
        )
        self.assertIn('Módulo 2', texto)
        self.assertIn('Segundo módulo', texto)

    def test_continuemos_reenvia_contenido_modulo_actual(self):
        texto = get_response_for_intent(
            'continuar_leccion',
            self.est.nombre,
            estudiante_id=self.est.id,
            mensaje_original='continuemos',
        )
        self.assertIn('CONTENIDO_CARACT_M1', texto)
        self.assertIn('Primer módulo', texto)

    def test_sin_progreso_activo_mensaje_curso_no_asignado(self):
        est = Estudiante.objects.create(
            nombre='Sin curso',
            telefono='573009991666',
            cliente=self.cliente,
            estado_chat='ACTIVO',
            acepto_terminos=True,
        )
        texto = get_response_for_intent(
            'continuar_leccion',
            est.nombre,
            estudiante_id=est.id,
            mensaje_original='listo',
        )
        self.assertIn('Aún no tienes un curso asignado', texto)