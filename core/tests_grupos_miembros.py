from django.test import TestCase

from core.models import Cliente, Estudiante
from core.models_extras import GrupoEstudiantes
from core.grupos_miembros import (
    agregar_miembros_por_identificadores,
    parsear_lineas_identificadores,
    quitar_miembros_por_identificadores,
)


class GruposMiembrosTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(nombre='Cliente Test', activo=True)
        self.grupo = GrupoEstudiantes.objects.create(
            nombre='Grupo A', emoji='G', cliente=self.cliente, activo=True,
        )
        self.est = Estudiante.objects.create(
            cedula='999888777',
            nombre='Ana Test',
            telefono='573001112233',
            cliente=self.cliente,
            activo=True,
            estado_onboarding='completado',
        )

    def test_agregar_y_quitar_por_cedula(self):
        r = agregar_miembros_por_identificadores(self.grupo, ['999888777'])
        self.assertEqual(r['agregados'], 1)
        self.assertTrue(self.grupo.estudiantes.filter(pk=self.est.pk).exists())

        r2 = quitar_miembros_por_identificadores(self.grupo, ['999888777'])
        self.assertEqual(r2['quitados'], 1)
        self.assertFalse(self.grupo.estudiantes.filter(pk=self.est.pk).exists())

    def test_parsear_lineas(self):
        texto = '111\n222, 333;444'
        self.assertEqual(parsear_lineas_identificadores(texto), ['111', '222', '333', '444'])
