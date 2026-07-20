"""Tests telemetría de aprendizaje (Centro de Éxito)."""

from django.test import TestCase
from django.utils import timezone

from core.models import (
    Cliente,
    Curso,
    Estudiante,
    EstudianteEventoAprendizaje,
    Modulo,
    ModuloCompletado,
    PasoModulo,
    ProgresoEstudiante,
    SeccionModulo,
)
from core.telemetria import (
    mapa_abandono_por_paso,
    marcar_recordatorio_respondido,
    recordatorios_ignorados_estudiante,
    registrar_evento,
)


class TelemetriaTests(TestCase):
    def setUp(self):
        self.cli = Cliente.objects.create(
            nombre='Tel Org',
            contacto_principal='A',
            email='tel@test.com',
            telefono='573009990001',
            activo=True,
        )
        self.curso = Curso.objects.create(nombre='Curso Tel', cliente=self.cli, activo=True)
        self.mod = Modulo.objects.create(
            curso=self.curso, numero=1, titulo='M1', descripcion='', contenido='c',
        )
        self.sec = SeccionModulo.objects.create(modulo=self.mod, orden=1, titulo='S1')
        self.paso = PasoModulo.objects.create(
            modulo=self.mod,
            seccion=self.sec,
            orden=1,
            titulo='Video intro',
            tipo=PasoModulo.TIPO_CONTENIDO,
            contenido='mira el video',
            media_url='https://example.com/v.mp4',
        )
        self.est = Estudiante.objects.create(
            cedula='tel1',
            nombre='Tel Uno',
            telefono='573009990002',
            cliente=self.cli,
            estado_chat='ACTIVO',
        )
        self.prog = ProgresoEstudiante.objects.create(
            estudiante=self.est,
            curso=self.curso,
            modulo_actual=self.mod,
            fecha_ultimo_avance=timezone.now(),
        )

    def test_registrar_evento(self):
        ev = registrar_evento(
            tipo=EstudianteEventoAprendizaje.TIPO_CONTENIDO_ENVIADO,
            estudiante=self.est,
            curso=self.curso,
            modulo=self.mod,
            paso=self.paso,
            metadata={'tiene_media': True},
        )
        self.assertIsNotNone(ev)
        self.assertEqual(ev.cliente_id, self.cli.pk)
        self.assertEqual(ev.paso_id, self.paso.pk)
        self.assertEqual(
            EstudianteEventoAprendizaje.objects.filter(estudiante=self.est).count(), 1
        )

    def test_signal_modulo_completado(self):
        ModuloCompletado.objects.create(progreso=self.prog, modulo=self.mod)
        self.assertTrue(
            EstudianteEventoAprendizaje.objects.filter(
                estudiante=self.est,
                tipo=EstudianteEventoAprendizaje.TIPO_MODULO_COMPLETADO,
            ).exists()
        )

    def test_recordatorio_ignorado_y_respondido(self):
        registrar_evento(
            tipo=EstudianteEventoAprendizaje.TIPO_RECORDATORIO_ENVIADO,
            estudiante=self.est,
            curso=self.curso,
            modulo=self.mod,
        )
        # Aún dentro de 72h → 0 ignorados
        self.assertEqual(recordatorios_ignorados_estudiante(self.est.pk), 0)
        marcar_recordatorio_respondido(self.est)
        self.assertTrue(
            EstudianteEventoAprendizaje.objects.filter(
                tipo=EstudianteEventoAprendizaje.TIPO_RECORDATORIO_RESPONDIDO,
                estudiante=self.est,
            ).exists()
        )

    def test_mapa_por_paso(self):
        registrar_evento(
            tipo=EstudianteEventoAprendizaje.TIPO_CONTENIDO_ENVIADO,
            estudiante=self.est,
            curso=self.curso,
            modulo=self.mod,
            paso=self.paso,
            metadata={'tiene_media': True},
        )
        qs = ProgresoEstudiante.objects.filter(pk=self.prog.pk)
        mapa = mapa_abandono_por_paso(qs, self.curso)
        self.assertTrue(mapa)
        self.assertEqual(mapa[0]['paso_id'], self.paso.pk)
        self.assertEqual(mapa[0]['caidas'], 1)
