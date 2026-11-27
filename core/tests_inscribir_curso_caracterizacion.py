"""Caracterización mínima de inscribir_curso antes de partir helpers (H4)."""
from django.test import TestCase

from core.conversacion.intents import inscribir_curso
from core.models import Curso, Estudiante, Modulo, ProgresoEstudiante


def _llamar(**kwargs):
    return inscribir_curso.responder('inscribir_curso', kwargs.get('nombre', 'Test'), kwargs)


class InscribirCursoCaracterizacionTests(TestCase):
    def setUp(self):
        self.curso = Curso.objects.create(
            nombre='Curso insc caract',
            usar_agentes_ia=False,
            dias_espera_entre_modulos=0,
        )
        self.m1 = Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='Módulo uno',
            contenido='CONTENIDO_INSC_CARACT',
            duracion_dias=7,
        )
        self.est = Estudiante.objects.create(
            nombre='Insc Caract',
            telefono='573009991888',
            estado_chat='ACTIVO',
            estado_onboarding='completado',
            acepto_terminos=True,
        )

    def test_sin_estudiante_id_error(self):
        texto = _llamar(mensaje_original='1')
        self.assertIn('Error al identificar estudiante', texto)

    def test_varios_cursos_sin_numero_pide_lista(self):
        curso2 = Curso.objects.create(
            nombre='Segundo curso caract',
            usar_agentes_ia=False,
            dias_espera_entre_modulos=0,
        )
        Modulo.objects.create(
            curso=curso2,
            numero=1,
            titulo='Otro módulo',
            contenido='OTRO',
            duracion_dias=7,
        )
        texto = _llamar(
            nombre=self.est.nombre,
            estudiante_id=self.est.id,
            mensaje_original='quiero un curso',
        )
        self.assertIn('escribe el *número*', texto)
        self.assertIn('ver cursos', texto)

    def test_inscripcion_nueva_crea_progreso_y_confirma(self):
        texto = _llamar(
            nombre=self.est.nombre,
            estudiante_id=self.est.id,
            mensaje_original='1',
        )
        self.assertIn('Inscripción exitosa', texto)
        self.assertIn('CONTENIDO_INSC_CARACT', texto)
        self.assertTrue(
            ProgresoEstudiante.objects.filter(estudiante=self.est, curso=self.curso).exists()
        )

    def test_numero_invalido(self):
        texto = _llamar(
            nombre=self.est.nombre,
            estudiante_id=self.est.id,
            mensaje_original='9',
        )
        self.assertIn('Número inválido', texto)

    def test_curso_ya_completado(self):
        ProgresoEstudiante.objects.create(
            estudiante=self.est,
            curso=self.curso,
            modulo_actual=self.m1,
            completado=True,
        )
        texto = _llamar(
            nombre=self.est.nombre,
            estudiante_id=self.est.id,
            mensaje_original='1',
        )
        self.assertIn('Ya completaste', texto)
        self.assertIn('Felicidades', texto)

    def test_retoma_curso_en_progreso(self):
        ProgresoEstudiante.objects.create(
            estudiante=self.est,
            curso=self.curso,
            modulo_actual=self.m1,
            completado=False,
        )
        texto = _llamar(
            nombre=self.est.nombre,
            estudiante_id=self.est.id,
            mensaje_original='1',
        )
        self.assertIn('Retomando', texto)
        self.assertIn('Módulo actual', texto)