"""Tests nota mínima certificado y drip por estudiante."""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from core.certificado_service import evaluar_elegibilidad_certificado
from core.drip_schedule import estudiante_autorizado_en_modulo, modulo_disponible_por_calendario
from core.gamificacion_modo import MODO_CALIFICACION, registrar_nota_gamificacion
from core.models import (
    Cliente,
    Curso,
    Estudiante,
    HabilitacionModuloEstudiante,
    Modulo,
)


class TestNotaMinimaCertificado(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            nombre='Cert Coop',
            contacto_principal='X',
            email='c@b.co',
            telefono='573000000020',
            modo_gamificacion=MODO_CALIFICACION,
            exigir_nota_minima_certificado=True,
            nota_minima_certificado=Decimal('3'),
        )
        self.curso = Curso.objects.create(nombre='Curso C', cliente=self.cliente, activo=True)
        self.est = Estudiante.objects.create(
            cedula='999',
            nombre='Test',
            telefono='573000000021',
            cliente=self.cliente,
            activo=True,
        )

    def test_rechaza_promedio_bajo(self):
        registrar_nota_gamificacion(self.est, 2.5, 'reto', curso=self.curso)
        ok, motivo = evaluar_elegibilidad_certificado(self.est, self.curso)
        self.assertFalse(ok)
        self.assertIn('2.5', motivo)

    def test_aprueba_promedio_suficiente(self):
        registrar_nota_gamificacion(self.est, 4, 'reto', curso=self.curso)
        ok, _ = evaluar_elegibilidad_certificado(self.est, self.curso)
        self.assertTrue(ok)


class TestDripPorEstudiante(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            nombre='Drip Coop',
            contacto_principal='Y',
            email='d@b.co',
            telefono='573000000030',
            drip_modulos_solo_estudiantes_listados=True,
        )
        self.curso = Curso.objects.create(nombre='Drip C', cliente=self.cliente, activo=True)
        self.m1 = Modulo.objects.create(curso=self.curso, numero=1, titulo='M1')
        self.m2 = Modulo.objects.create(curso=self.curso, numero=2, titulo='M2')
        self.ana = Estudiante.objects.create(
            cedula='1111', nombre='Ana', telefono='573000000031', cliente=self.cliente, activo=True,
        )
        self.luis = Estudiante.objects.create(
            cedula='2222', nombre='Luis', telefono='573000000032', cliente=self.cliente, activo=True,
        )

    def test_lista_blanca_modulo(self):
        self.assertFalse(estudiante_autorizado_en_modulo(self.luis, self.m2))
        HabilitacionModuloEstudiante.objects.create(
            estudiante=self.ana,
            curso=self.curso,
            modulo=self.m2,
            habilitado_desde=timezone.now() - timedelta(hours=1),
        )
        self.assertTrue(estudiante_autorizado_en_modulo(self.ana, self.m2))
        self.assertTrue(modulo_disponible_por_calendario(self.ana, self.m2))
        self.assertFalse(modulo_disponible_por_calendario(self.luis, self.m2))
