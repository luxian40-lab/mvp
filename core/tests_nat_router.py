"""Tests router Nat — modelos y escalado GPT-5."""

from types import SimpleNamespace

from django.test import SimpleTestCase, override_settings

from core.nat_router import decidir_routing_nat, evaluar_calidad_rag


class NatRouterTests(SimpleTestCase):
    @override_settings(
        BOT_COMERCIAL_OPENAI_MODEL='gpt-5-mini',
        BOT_COMERCIAL_MODEL_TECNICO='gpt-5',
        BOT_COMERCIAL_ROUTER_USE_NANO=False,
    )
    def test_saludo_usa_mini(self):
        d = decidir_routing_nat('hola buenos días', es_saludo=True)
        self.assertEqual(d.modelo, 'gpt-5-mini')
        self.assertFalse(d.escala_premium)

    @override_settings(
        BOT_COMERCIAL_OPENAI_MODEL='gpt-5-mini',
        BOT_COMERCIAL_MODEL_TECNICO='gpt-5',
        BOT_COMERCIAL_RAG_MIN_SIMILARITY=0.5,
        BOT_COMERCIAL_ROUTER_USE_NANO=False,
    )
    def test_tecnico_con_rag_fuerte_escala_gpt5(self):
        chunks = [{'similitud': 0.82, 'fuente': 'ficha.pdf'}]
        d = decidir_routing_nat(
            'Tengo roya en café con manchas amarillas en Huila',
            rag_chunks=chunks,
            tiene_rag_texto=True,
        )
        self.assertEqual(d.modelo, 'gpt-5')
        self.assertTrue(d.escala_premium)
        self.assertEqual(d.modo, 'tecnico')

    @override_settings(
        BOT_COMERCIAL_OPENAI_MODEL='gpt-5-mini',
        BOT_COMERCIAL_MODEL_TECNICO='gpt-5',
        BOT_COMERCIAL_ROUTER_USE_NANO=False,
        BOT_COMERCIAL_WEB_FALLBACK_ENABLED=True,
    )
    def test_tecnico_sin_rag_pide_web(self):
        d = decidir_routing_nat('Necesito dosis de calcio foliar en maíz en etapa V6')
        self.assertTrue(d.usar_web)
        self.assertEqual(d.modo, 'tecnico')

    @override_settings(
        BOT_COMERCIAL_OPENAI_MODEL='gpt-5-mini',
        BOT_COMERCIAL_MODEL_TECNICO='gpt-5',
        BOT_COMERCIAL_ROUTER_USE_NANO=False,
        BOT_COMERCIAL_WEB_FALLBACK_ENABLED=True,
        BOT_COMERCIAL_RAG_MIN_SIMILARITY=0.5,
    )
    def test_plan_b_sin_catalogo_fuerza_web_aunque_haya_rag(self):
        """Sin productos cargados: Plan B busca web aunque RAG tenga algo débil."""
        d = decidir_routing_nat(
            'mancha en tomate hojas de abajo Guateque',
            rag_chunks=[{'similitud': 0.55, 'fuente': 'nota.pdf'}],
            tiene_rag_texto=True,
            contexto_rag_chars=400,
            sin_catalogo_productos=True,
        )
        self.assertEqual(d.modo, 'tecnico')
        self.assertTrue(d.usar_web)
        self.assertIn('plan_b', d.razon)

    @override_settings(
        BOT_COMERCIAL_OPENAI_MODEL='gpt-5-mini',
        BOT_COMERCIAL_MODEL_TECNICO='gpt-5',
        BOT_COMERCIAL_ROUTER_USE_NANO=False,
    )
    def test_precio_con_rag_escala_premium(self):
        d = decidir_routing_nat(
            '¿Cuánto cuesta el fertilizante?',
            rag_chunks=[{'similitud': 0.61, 'fuente': 'lista.xlsx'}],
            tiene_rag_texto=True,
        )
        self.assertEqual(d.modelo, 'gpt-5')
        self.assertEqual(d.modo, 'catalogo')

    def test_evaluar_calidad_rag(self):
        mx, n = evaluar_calidad_rag([
            {'similitud': 0.4},
            {'similitud': 0.7},
        ])
        self.assertEqual(mx, 0.7)
        self.assertEqual(n, 1)

    @override_settings(BOT_COMERCIAL_RAG_MIN_SIMILARITY=0.52)
    def test_filtrar_chunks_por_similitud(self):
        from core.nat_router import filtrar_chunks_por_similitud
        out = filtrar_chunks_por_similitud([
            {'similitud': 0.4, 'fuente': 'ruido'},
            {'similitud': 0.6, 'fuente': 'util'},
            {'fuente': 'sin_score'},
        ])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]['fuente'], 'util')
