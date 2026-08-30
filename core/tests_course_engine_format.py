# -*- coding: utf-8 -*-
from types import SimpleNamespace

from django.test import SimpleTestCase

from core.course_engine.format_config import (
    FORMAT_MIXTO_COMPLETO,
    FORMAT_SOLO_VIDEO,
    plan_desde_curso,
    resolver_formato_curso,
)


class FormatConfigTests(SimpleTestCase):
    def test_mixto_completo_plan(self):
        curso = SimpleNamespace(
            course_engine_format=FORMAT_MIXTO_COMPLETO,
            course_engine_tier='estandar',
            course_engine_podcast_minutos=3,
        )
        plan = plan_desde_curso(curso)
        self.assertTrue(plan.incluir_podcast)
        self.assertTrue(plan.incluir_infografia)
        self.assertEqual(plan.podcast_chars, 1800)

    def test_solo_video(self):
        curso = SimpleNamespace(
            course_engine_format=FORMAT_SOLO_VIDEO,
            course_engine_tier='premium',
            course_engine_podcast_minutos=2,
        )
        plan = plan_desde_curso(curso)
        self.assertFalse(plan.incluir_podcast)
        self.assertFalse(plan.incluir_infografia)
