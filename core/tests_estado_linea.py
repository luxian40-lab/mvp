"""Fase E: estado del curso por persona y línea."""
from django.db import IntegrityError, transaction
from django.test import TestCase

from core.conversacion.estado_linea import EstadoLinea
from core.models import Estudiante

TEL = '573001110021'
LINEA_1 = '100000000000001'
LINEA_2 = '100000000000002'


class EstadoLineaModeloTests(TestCase):
    def setUp(self):
        self.est = Estudiante.objects.create(cedula='CC5550021', nombre='Eva', telefono=TEL)

    def test_una_fila_por_estudiante_y_linea(self):
        EstadoLinea.objects.create(estudiante=self.est, phone_id=LINEA_1)
        EstadoLinea.objects.create(estudiante=self.est, phone_id=LINEA_2)
        with self.assertRaises(IntegrityError), transaction.atomic():
            EstadoLinea.objects.create(estudiante=self.est, phone_id=LINEA_1)

    def test_se_borra_con_el_estudiante(self):
        EstadoLinea.objects.create(estudiante=self.est, phone_id=LINEA_1, estado_chat='ACTIVO')
        self.est.delete()
        self.assertFalse(EstadoLinea.objects.exists())
