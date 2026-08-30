# -*- coding: utf-8 -*-
from django.test import SimpleTestCase

from core.course_engine.bundle import ModuloMixtoPlan, estimar_costo_curso, estimar_costo_modulo_mixto


class BundleCostTests(SimpleTestCase):
    def test_modulo_mixto_estandar(self):
        plan = ModuloMixtoPlan(tier_video='estandar', podcast_chars=1200)
        c = estimar_costo_modulo_mixto(plan)
        self.assertGreater(c.video_usd, 0.3)
        self.assertGreater(c.total_usd, 0.6)

    def test_curso_10_modulos(self):
        plan = ModuloMixtoPlan(tier_video='estandar')
        r = estimar_costo_curso(10, plan)
        self.assertEqual(r['n_modulos'], 10)
        self.assertGreater(r['con_qa_usd'], r['subtotal_usd'])
        self.assertGreater(r['elevenlabs_chars_aprox'], 10000)
