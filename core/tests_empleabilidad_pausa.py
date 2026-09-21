"""Pausa de radar/empleabilidad: no dispara Subachoque ni come el webhook."""

from unittest.mock import patch

from django.test import TestCase

from core.empleabilidad_pausa import (
    EKI_EMPLEABILIDAD_PAUSADA,
    MENSAJE_RADAR_DESBLOQUEADO,
    empleabilidad_en_pausa,
    liberar_estado_empleabilidad_si_pausada,
    mensaje_radar_desbloqueado,
)
from core.models import (
    AliadoEmpleabilidad,
    Cliente,
    Curso,
    Estudiante,
    Modulo,
    ProgresoEstudiante,
)
from core.response_templates import _generar_completado_final
from core.views import _activar_radar_empleabilidad_si_aplica, _procesar_ubicacion_empleabilidad
from portal.capabilities import modulos_portal


class EmpleabilidadPausaFlagTests(TestCase):
    def test_pausa_activa_por_defecto(self):
        self.assertTrue(EKI_EMPLEABILIDAD_PAUSADA)
        self.assertTrue(empleabilidad_en_pausa())
        self.assertEqual(mensaje_radar_desbloqueado(), '')

    def test_reactivar_devuelve_copy_historico(self):
        with patch('core.empleabilidad_pausa.EKI_EMPLEABILIDAD_PAUSADA', False):
            self.assertFalse(empleabilidad_en_pausa())
            self.assertIn('Radar de Empleos', mensaje_radar_desbloqueado())
            self.assertIn('Subachoque', MENSAJE_RADAR_DESBLOQUEADO)


class EmpleabilidadPausaWhatsappTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            nombre='Org Radar Pausa',
            contacto_principal='A',
            email='radar-pausa@test.co',
            telefono='573009990010',
            activo=True,
            habilitar_gamificacion_proximidad=True,
            empleabilidad_exploracion_activa=True,
            portal_productos='cursos,empleabilidad',
        )
        self.est = Estudiante.objects.create(
            cedula='pausa01',
            nombre='Joven Pausa',
            telefono='573009990011',
            cliente=self.cliente,
            activo=True,
        )
        AliadoEmpleabilidad.objects.create(
            nombre_empresa='Aliado Suba',
            cliente=self.cliente,
            latitud=4.926,
            longitud=-74.173,
            vacantes_activas=True,
            codigo_secreto='SUBA123',
            indicacion_sector='parque principal',
        )

    def test_no_activa_radar_aunque_haya_aliados(self):
        self.assertFalse(_activar_radar_empleabilidad_si_aplica(self.est))
        self.est.refresh_from_db()
        self.assertFalse((self.est.contexto_temporal or {}).get('radar_empleabilidad_activo'))

    def test_ubicacion_no_pide_codigo_ni_crea_mision(self):
        from core.models import MisionEmpleabilidad

        msg = _procesar_ubicacion_empleabilidad(self.est, 4.926, -74.173)
        self.est.refresh_from_db()
        self.assertNotEqual(self.est.estado_onboarding, 'esperando_codigo_empleabilidad')
        self.assertEqual(MisionEmpleabilidad.objects.filter(estudiante=self.est).count(), 0)
        self.assertNotIn('Subachoque', msg or '')
        self.assertNotIn('código secreto', (msg or '').lower())

    def test_completado_final_no_menciona_radar(self):
        curso = Curso.objects.create(nombre='Curso cierre', cliente=self.cliente, activo=True)
        m1 = Modulo.objects.create(curso=curso, numero=1, titulo='Uno', contenido='a')
        ProgresoEstudiante.objects.create(
            estudiante=self.est,
            curso=curso,
            modulo_actual=m1,
            completado=False,
        )
        out = _generar_completado_final(self.est, curso.id)
        self.assertNotIn('Radar de Empleos', out)
        self.assertNotIn('Subachoque', out)

    def test_portal_oculta_modulo_aunque_este_contratado(self):
        mods = modulos_portal(self.cliente)
        self.assertTrue(mods['cursos'])
        self.assertFalse(mods['empleabilidad'])

    def test_libera_estudiante_atascado_en_codigo(self):
        curso = Curso.objects.create(nombre='Curso abierto', cliente=self.cliente, activo=True)
        m1 = Modulo.objects.create(curso=curso, numero=1, titulo='Uno', contenido='a')
        ProgresoEstudiante.objects.create(
            estudiante=self.est,
            curso=curso,
            modulo_actual=m1,
            completado=False,
        )
        self.est.estado_onboarding = 'esperando_codigo_empleabilidad'
        self.est.contexto_temporal = {
            'radar_empleabilidad_activo': True,
            'aliado_empleabilidad_objetivo_id': 99,
        }
        self.est.save(update_fields=['estado_onboarding', 'contexto_temporal'])
        self.assertTrue(liberar_estado_empleabilidad_si_pausada(self.est))
        self.est.refresh_from_db()
        self.assertEqual(self.est.estado_onboarding, 'completado')
        self.assertIsNone((self.est.contexto_temporal or {}).get('radar_empleabilidad_activo'))
