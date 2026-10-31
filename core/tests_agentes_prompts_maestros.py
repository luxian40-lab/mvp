"""Los cinco agentes comparten las instrucciones eki y conservan sus nombres."""
from django.test import SimpleTestCase

from core.sandbox_agentes import (
    IDENTIDAD_AGRONOMO_LINEA,
    INSTRUCCIONES_EKI,
    _respuesta_si_falla,
    nombre_agente,
    presentacion_agente,
    prompt_para,
)

AGENTES = ('coach', 'ia_campo', 'ventas', 'finanzas', 'cafe')


class InstruccionesComunesTests(SimpleTestCase):
    def test_los_cinco_llevan_las_instrucciones_eki(self):
        for agente in AGENTES:
            prompt = prompt_para(agente)
            self.assertIn(INSTRUCCIONES_EKI, prompt, agente)
            self.assertIn('REGISTRO Y ESTILO', prompt, agente)
            self.assertIn('RECORDATORIO FINAL', prompt, agente)
        self.assertIn(INSTRUCCIONES_EKI, IDENTIDAD_AGRONOMO_LINEA)

    def test_metodo_y_limites_comunes(self):
        texto = INSTRUCCIONES_EKI
        self.assertIn('comprender, razonar, decidir, aplicar, aprender', texto)
        self.assertIn('lo que veo', texto)
        self.assertIn('el criterio', texto)
        self.assertIn('hacer hoy (un solo paso', texto)
        self.assertIn('una pregunta para que ella juzgue', texto)
        self.assertIn('no cierra el caso por ella', texto)
        self.assertIn('UNA pregunta breve', texto)
        self.assertIn('No prometa recordatorios', texto)
        self.assertIn('Nunca reemplace la decisión de la persona', texto)
        self.assertIn('No simule que lo transfiere', texto)

    def test_estilo_sin_tope_viejo(self):
        for agente in AGENTES:
            prompt = prompt_para(agente)
            self.assertIn('de 30 a 90 palabras', prompt, agente)
            self.assertIn('Como máximo UNA pregunta', prompt, agente)
            self.assertNotIn('Máximo 70 palabras', prompt, agente)
            self.assertNotIn('180 palabras', prompt, agente)

    def test_nombres_sin_cambio(self):
        self.assertEqual(
            {agente: nombre_agente(agente) for agente in AGENTES},
            {
                'coach': 'Coach',
                'ia_campo': 'Innovación e IA',
                'ventas': 'Ventas',
                'finanzas': 'Finanzas',
                'cafe': 'Agrónomo',
            },
        )
        for agente in AGENTES:
            self.assertIn('No tiene nombre propio', prompt_para(agente), agente)


class LimitesPorAgenteTests(SimpleTestCase):
    def test_agronomo_no_diagnostica_con_certeza(self):
        for texto in (prompt_para('cafe'), IDENTIDAD_AGRONOMO_LINEA):
            self.assertIn('No diagnostique plagas ni deficiencias con certeza', texto)
            self.assertIn('productos regulados', texto)
            self.assertIn('encuesta agronómica', texto)

    def test_ventas_no_inventa_precios(self):
        prompt = prompt_para('ventas')
        self.assertIn('No invente precios de mercado, compradores ni certificaciones', prompt)
        self.assertIn('¿cuánto vendió?', prompt)

    def test_finanzas_parte_de_una_decision_y_no_inventa_tasas(self):
        prompt = prompt_para('finanzas')
        self.assertIn('No es un registrador de gastos', prompt)
        self.assertIn('No le pida "¿cuánto gastó hoy?"', prompt)
        self.assertIn('No invente condiciones de crédito, tasas', prompt)
        self.assertNotIn('gasto', presentacion_agente('finanzas').lower())
        self.assertNotIn('lo que gastó', _respuesta_si_falla('finanzas', 'un crédito'))

    def test_innovacion_no_presenta_la_ia_como_infalible(self):
        prompt = prompt_para('ia_campo')
        self.assertIn('Eficiencia', prompt)
        self.assertIn('Diferenciación', prompt)
        self.assertIn('no la presente como infalible', prompt)

    def test_coach_es_liderazgo_y_desarrollo_humano(self):
        prompt = prompt_para('coach')
        self.assertIn('liderazgo', prompt.lower())
        self.assertIn('No es terapeuta ni autoridad moral', prompt)
        self.assertIn('No diagnostique problemas psicológicos', prompt)
        self.assertIn('liderar', presentacion_agente('coach').lower())
