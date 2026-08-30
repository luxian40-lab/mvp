# -*- coding: utf-8 -*-
from django.test import SimpleTestCase
from types import SimpleNamespace

from core.course_engine.voice_config import (
    resolver_tier_modulo,
    resolver_voice_id_modulo,
)


class VoiceConfigTests(SimpleTestCase):
    def test_modulo_hereda_curso(self):
        curso = SimpleNamespace(
            course_engine_tier='estandar',
            course_engine_voice_id='voice_curso',
            course_engine_voice_label='Maria',
        )
        modulo = SimpleNamespace(
            course_engine_tier='',
            course_engine_voice_id='',
            course_engine_voice_label='',
            curso=curso,
        )
        self.assertEqual(resolver_tier_modulo(modulo), 'estandar')
        self.assertEqual(resolver_voice_id_modulo(modulo), 'voice_curso')

    def test_modulo_override_voz_clonada(self):
        curso = SimpleNamespace(
            course_engine_tier='economico',
            course_engine_voice_id='voice_default',
            course_engine_voice_label='eki',
        )
        modulo = SimpleNamespace(
            course_engine_tier='estandar',
            course_engine_voice_id='voice_cliente_clonada',
            course_engine_voice_label='Agronomo Cenipalma',
            curso=curso,
        )
        self.assertEqual(resolver_tier_modulo(modulo), 'estandar')
        self.assertEqual(resolver_voice_id_modulo(modulo), 'voice_cliente_clonada')
