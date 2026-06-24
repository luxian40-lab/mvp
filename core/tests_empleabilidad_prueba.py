"""Tests utilidades de prueba empleabilidad."""

from django.test import TestCase

from core.empleabilidad_prueba import (
    completar_mision_con_codigo,
    configurar_cliente_empleabilidad,
    crear_aliados_demo,
    setup_prueba_empleabilidad,
    simular_ubicacion_whatsapp,
)
from core.models import AliadoEmpleabilidad, Cliente, Estudiante, MisionEmpleabilidad


class EmpleabilidadPruebaSetupTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            nombre='Org Emp Prueba',
            contacto_principal='X',
            email='emp@test.com',
            telefono='573001100001',
            activo=True,
        )
        self.est = Estudiante.objects.create(
            cedula='emp99',
            nombre='Joven Prueba',
            telefono='573001100099',
            cliente=self.cliente,
            activo=True,
            estado_chat='ACTIVO',
        )

    def test_configura_cliente_y_aliados(self):
        cambios = configurar_cliente_empleabilidad(self.cliente, radio_metros=1200)
        self.assertTrue(any('empleabilidad_exploracion_activa' in c for c in cambios))
        self.cliente.refresh_from_db()
        self.assertIn('empleabilidad', self.cliente.portal_productos)

        aliados = crear_aliados_demo(self.cliente, lat_base=4.926, lng_base=-74.173)
        self.assertEqual(len(aliados), 3)
        self.assertEqual(AliadoEmpleabilidad.objects.filter(cliente=self.cliente).count(), 3)

    def test_flujo_simulado_ubicacion_y_codigo(self):
        setup_prueba_empleabilidad(self.cliente, telefono=self.est.telefono)
        msg = simular_ubicacion_whatsapp(self.est, 4.926, -74.173)
        self.est.refresh_from_db()
        self.assertIn('código secreto', msg.lower())
        self.assertEqual(self.est.estado_onboarding, 'esperando_codigo_empleabilidad')
        self.assertEqual(MisionEmpleabilidad.objects.filter(estudiante=self.est).count(), 1)

        ok, detalle = completar_mision_con_codigo(self.est, 'EKI-DEMO-01')
        self.assertTrue(ok, detalle)
        mision = MisionEmpleabilidad.objects.get(estudiante=self.est)
        self.assertEqual(mision.estado, 'completada')
        self.assertTrue(mision.codigo_validado)
