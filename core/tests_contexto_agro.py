"""Tests Parte 3 — contexto agronómico estructurado Nati."""

from django.test import TestCase

from core.contexto_agro import (
    actualizar_contexto_desde_mensaje,
    extraer_campos_desde_mensaje,
    formatear_bloque_contexto_para_prompt,
    obtener_o_crear_contexto,
)
from core.models import Cliente, ContextoAgroSession, SesionComercial


class ContextoAgroExtraccionTests(TestCase):
    def test_extrae_cultivo_y_problema(self):
        msg = 'Tengo roya en mi café en Huila, etapa de floración'
        campos = extraer_campos_desde_mensaje(msg)
        self.assertEqual(campos.get('cultivo'), 'café')
        self.assertIn('roya', (campos.get('problema') or '').lower())
        self.assertEqual(campos.get('region'), 'Huila')
        self.assertIn('flor', (campos.get('etapa') or '').lower())

    def test_mensaje_vacio(self):
        self.assertEqual(extraer_campos_desde_mensaje(''), {})


class ContextoAgroSessionTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            nombre='Finca Test',
            contacto_principal='Ana',
            email='ana@test.co',
            telefono='573001112233',
        )
        self.sesion = SesionComercial.objects.create(
            telefono='573001112233',
            cliente=self.cliente,
        )

    def test_crea_y_actualiza_sesion(self):
        ctx = actualizar_contexto_desde_mensaje(
            self.sesion,
            'Mi cultivo de cacao tiene broca en Santander',
        )
        self.assertIsInstance(ctx, ContextoAgroSession)
        self.assertEqual(ctx.cultivo, 'cacao')
        self.assertEqual(ctx.problema, 'broca')
        self.assertEqual(ctx.region, 'Santander')
        self.assertGreaterEqual(ctx.completitud_pct(), 50)

    def test_problema_se_actualiza_en_conversacion(self):
        ctx = obtener_o_crear_contexto(self.sesion)
        ctx.cultivo = 'maíz'
        ctx.problema = 'sequía'
        ctx.save()
        actualizar_contexto_desde_mensaje(self.sesion, 'Ahora apareció roya en las hojas')
        ctx.refresh_from_db()
        self.assertEqual(ctx.cultivo, 'maíz')
        self.assertEqual(ctx.problema, 'roya')

    def test_correccion_cultivo_con_pista(self):
        ctx = obtener_o_crear_contexto(self.sesion)
        ctx.cultivo = 'maíz'
        ctx.save()
        actualizar_contexto_desde_mensaje(self.sesion, 'No es maíz, en realidad es café con roya')
        ctx.refresh_from_db()
        self.assertEqual(ctx.cultivo, 'café')

    def test_formatear_bloque_prompt(self):
        ctx = actualizar_contexto_desde_mensaje(
            self.sesion,
            'Aguacate con sequía en Antioquia',
        )
        bloque = formatear_bloque_contexto_para_prompt(ctx)
        self.assertIn('CONTEXTO AGRONÓMICO', bloque)
        self.assertIn('completitud', bloque.lower())

    def test_formatear_bloque_incompleto(self):
        ctx = obtener_o_crear_contexto(self.sesion)
        bloque = formatear_bloque_contexto_para_prompt(ctx)
        self.assertIn('parcial', bloque.lower())
