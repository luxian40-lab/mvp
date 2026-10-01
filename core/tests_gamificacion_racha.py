"""Racha en hora local, badges RACHA del admin y puntos de curso sin duplicar."""
import time
from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.test import TestCase

from core.gamificacion import Badge, BadgeEstudiante, PerfilGamificacion, TransaccionPuntos
from core.models import Curso, Estudiante, ProgresoEstudiante

BOGOTA = ZoneInfo('America/Bogota')


class RachaHoraLocalTests(TestCase):
    def setUp(self):
        self.est = Estudiante.objects.create(nombre='R', cedula='GR1', telefono='573005551000')

    def _perfil(self, dias, ultima):
        perfil, _ = PerfilGamificacion.objects.update_or_create(
            estudiante=self.est, defaults={'racha_dias_actual': dias, 'ultima_actividad': ultima}
        )
        return perfil

    def test_noche_en_bogota_no_cuenta_como_otro_dia(self):
        perfil = self._perfil(2, datetime(2026, 9, 29, 18, 0, tzinfo=BOGOTA))
        with patch('django.utils.timezone.now', return_value=datetime(2026, 9, 29, 20, 30, tzinfo=BOGOTA)):
            self.assertFalse(perfil.actualizar_racha())
        self.assertEqual(perfil.racha_dias_actual, 2)

    def test_dia_siguiente_local_suma(self):
        perfil = self._perfil(2, datetime(2026, 9, 29, 20, 30, tzinfo=BOGOTA))
        with patch('django.utils.timezone.now', return_value=datetime(2026, 9, 30, 8, 0, tzinfo=BOGOTA)):
            self.assertTrue(perfil.actualizar_racha())
        self.assertEqual(perfil.racha_dias_actual, 3)

    def test_badge_racha_con_dias_configurados_en_admin(self):
        badge = Badge.objects.create(nombre='Diez', descripcion='10', tipo='RACHA', valor_requerido=10)
        perfil = self._perfil(9, datetime.now(BOGOTA) - timedelta(days=1))
        perfil.actualizar_racha()
        self.assertEqual(perfil.badges_racha_nuevos, [badge])
        self.assertTrue(BadgeEstudiante.objects.filter(estudiante=self.est, badge=badge).exists())


class TurnoDeListoTests(TestCase):
    def setUp(self):
        self.est = Estudiante.objects.create(nombre='L', cedula='TL1', telefono='573005551009')

    def _listo(self):
        from core.response_templates import get_response_for_intent

        return get_response_for_intent(
            'continuar_leccion', self.est.nombre, estudiante_id=self.est.id, mensaje_original='listo'
        )

    def test_un_listo_mientras_se_envia_no_avanza(self):
        from core.response_templates import LECCION_EN_CURSO

        self.est.contexto_temporal = {'_leccion_enviando': True, '_ts_leccion': time.time()}
        self.est.save(update_fields=['contexto_temporal'])
        self.assertEqual(self._listo(), LECCION_EN_CURSO)
        self.est.refresh_from_db()
        self.assertTrue(self.est.contexto_temporal.get('_leccion_enviando'))

    def test_al_soltar_el_turno_el_siguiente_listo_sigue(self):
        from core.response_templates import LECCION_EN_CURSO, _turno_estudiante, soltar_turno_entrega_actual

        self.est.contexto_temporal = {'_leccion_enviando': True, '_ts_leccion': time.time()}
        self.est.save(update_fields=['contexto_temporal'])
        _turno_estudiante.set(self.est.id)
        soltar_turno_entrega_actual()
        self.est.refresh_from_db()
        self.assertNotIn('_leccion_enviando', self.est.contexto_temporal or {})
        self.assertNotEqual(self._listo(), LECCION_EN_CURSO)

    def test_un_turno_atascado_no_bloquea_para_siempre(self):
        from core.response_templates import LECCION_EN_CURSO

        self.est.contexto_temporal = {'_leccion_enviando': True, '_ts_leccion': time.time() - 120}
        self.est.save(update_fields=['contexto_temporal'])
        self.assertNotEqual(self._listo(), LECCION_EN_CURSO)


class PuntosCursoCompletadoTests(TestCase):
    def setUp(self):
        self.est = Estudiante.objects.create(nombre='P', cedula='GP1', telefono='573005551001')
        self.curso = Curso.objects.create(nombre='Curso puntos', descripcion='x')

    def _puntos_curso(self):
        return TransaccionPuntos.objects.filter(
            perfil__estudiante=self.est, razon=f'Completó curso {self.curso.nombre}'
        ).count()

    def test_guardar_progreso_completado_no_repite_puntos(self):
        prog = ProgresoEstudiante.objects.create(estudiante=self.est, curso=self.curso)
        prog.completado = True
        prog.save()
        prog.save()
        ProgresoEstudiante.objects.get(pk=prog.pk).save()
        self.assertEqual(self._puntos_curso(), 1)
        self.assertEqual(PerfilGamificacion.objects.get(estudiante=self.est).puntos_totales, 15)

    def test_creado_ya_completado_da_puntos_una_vez(self):
        ProgresoEstudiante.objects.create(estudiante=self.est, curso=self.curso, completado=True)
        self.assertEqual(self._puntos_curso(), 1)

    def test_reabrir_y_volver_a_completar_no_paga_doble(self):
        prog = ProgresoEstudiante.objects.create(estudiante=self.est, curso=self.curso, completado=True)
        prog.completado = False
        prog.save()
        prog.completado = True
        prog.save()
        self.assertEqual(self._puntos_curso(), 1)
