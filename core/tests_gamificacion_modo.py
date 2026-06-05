"""Tests modo gamificación por cliente (puntos vs calificación)."""
from unittest.mock import patch

from django.test import TestCase

from decimal import Decimal

from core.gamificacion_modo import (
    MODO_CALIFICACION,
    MODO_DESACTIVADO,
    MODO_PUNTOS,
    gamificacion_otorga_puntos,
    get_modo_gamificacion,
    ranking_calificaciones_cliente,
    registrar_nota_gamificacion,
    resumen_calificaciones_estudiante,
    sincronizar_usar_gamificacion,
)
from core.models import Cliente, Curso, Estudiante
from core.tutor_ia_modulo import _extraer_nota_1_5, evaluar_reto_facilitador


class TestModoGamificacionCliente(TestCase):
    def test_default_puntos(self):
        c = Cliente.objects.create(
            nombre='Coop',
            contacto_principal='A',
            email='a@b.co',
            telefono='573000000001',
            modo_gamificacion=MODO_PUNTOS,
        )
        self.assertEqual(get_modo_gamificacion(c), MODO_PUNTOS)
        self.assertTrue(c.usar_gamificacion)

    def test_calificacion_no_otorga_puntos(self):
        c = Cliente.objects.create(
            nombre='Coop Notas',
            contacto_principal='B',
            email='b@b.co',
            telefono='573000000002',
            modo_gamificacion=MODO_CALIFICACION,
        )
        sincronizar_usar_gamificacion(c)
        c.save()
        c.refresh_from_db()
        self.assertTrue(c.usar_gamificacion)
        self.assertFalse(gamificacion_otorga_puntos(c))

    def test_desactivado(self):
        c = Cliente.objects.create(
            nombre='Sin',
            contacto_principal='C',
            email='c@b.co',
            telefono='573000000003',
            modo_gamificacion=MODO_DESACTIVADO,
        )
        c.save()
        c.refresh_from_db()
        self.assertFalse(c.usar_gamificacion)


class TestRankingNotas(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            nombre='Ranking Coop',
            contacto_principal='X',
            email='r@b.co',
            telefono='573000000010',
            modo_gamificacion=MODO_CALIFICACION,
            peso_gamificacion_reto=Decimal('2'),
            peso_gamificacion_abierta=Decimal('1'),
        )
        self.curso = Curso.objects.create(
            nombre='Curso R',
            cliente=self.cliente,
            activo=True,
        )
        self.est_a = Estudiante.objects.create(
            cedula='111',
            nombre='Ana',
            telefono='573000000011',
            cliente=self.cliente,
            activo=True,
        )
        self.est_b = Estudiante.objects.create(
            cedula='222',
            nombre='Luis',
            telefono='573000000012',
            cliente=self.cliente,
            activo=True,
        )

    def test_promedio_ponderado_y_ranking(self):
        registrar_nota_gamificacion(self.est_a, 4, 'reto', curso=self.curso)
        registrar_nota_gamificacion(self.est_a, 5, 'pregunta_abierta', curso=self.curso)
        registrar_nota_gamificacion(self.est_b, 3, 'reto', curso=self.curso)

        res_a = resumen_calificaciones_estudiante(self.est_a, self.curso.id)
        # Ana: (4*2 + 5*1) / 3 = 13/3 ≈ 4.3
        self.assertEqual(res_a['cantidad'], 2)
        self.assertAlmostEqual(float(res_a['promedio']), 13 / 3, places=1)

        ranking = ranking_calificaciones_cliente(self.cliente, self.curso.id)
        self.assertEqual(ranking[0]['nombre'], 'Ana')
        self.assertEqual(ranking[1]['nombre'], 'Luis')


class TestPromptNotas(TestCase):
    def test_extraer_nota_decimal(self):
        fb = 'Muy bien. Nota final: 3.5/5'
        self.assertEqual(_extraer_nota_1_5(fb), 3.5)

    @patch('core.tutor_ia_modulo._get_client')
    def test_evaluar_modo_calificacion_usa_parser_5(self, mock_client):
        mock_resp = type('R', (), {})()
        mock_resp.choices = [
            type('C', (), {'message': type('M', (), {'content': 'Bien. Nota final: 4.2/5'})()})(),
        ]
        mock_client.return_value.chat.completions.create.return_value = mock_resp

        nota, _ = evaluar_reto_facilitador(
            [], 'respuesta', 'reto', modo_gamificacion=MODO_CALIFICACION,
        )
        self.assertAlmostEqual(nota, 4.2)
