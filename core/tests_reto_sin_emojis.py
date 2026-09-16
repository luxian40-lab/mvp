"""Retos y traspasos entre agentes en prosa y sin emojis."""
from unittest.mock import MagicMock, patch

from django.test import TestCase

from core.models import Cliente, Curso, Modulo
from core.prompts_tecnicoagro import (
    ANEXO_EVALUACION_NOTAS,
    ANEXO_EVALUACION_PUNTOS,
    ANEXO_RETO_CHECKPOINT_WA,
    PROMPT_TECNICOAGRO,
)
from core.tutor_ia_modulo import (
    PROMPT_FACILITADOR_EVALUACION,
    PROMPT_FACILITADOR_EVALUACION_NOTAS,
    PROMPT_FACILITADOR_RETO,
    generar_presentacion_agentes,
    generar_reto_facilitador,
    limpiar_emojis,
)

EMOJIS_FRECUENTES = ('🌱', '📋', '✍️', '💬', '📸', '⏱️', '💡', '💰', '🤓', '💪', '📚', '🤝')


class LimpiarEmojisTests(TestCase):
    def test_quita_emojis_y_deja_texto_legible(self):
        texto = (
            '🌱 RETO DE CAMPO\n\n'
            'Hoy: revise 10 colmenas 🐝 y cuente cuántas presentan cría salteada.'
        )
        limpio = limpiar_emojis(texto)

        for emoji in ('🌱', '🐝'):
            self.assertNotIn(emoji, limpio)
        self.assertIn('revise 10 colmenas', limpio)
        self.assertNotIn('  ', limpio)

    def test_texto_sin_emojis_no_cambia(self):
        texto = 'Revise 10 colmenas y registre cuántas presentan cría salteada.'
        self.assertEqual(limpiar_emojis(texto), texto)

    def test_vacio_no_rompe(self):
        self.assertEqual(limpiar_emojis(''), '')
        self.assertEqual(limpiar_emojis(None), '')


class PromptsSinEmojisTests(TestCase):
    def test_prompts_prohiben_emojis(self):
        for prompt in (
            PROMPT_FACILITADOR_RETO,
            PROMPT_FACILITADOR_EVALUACION,
            PROMPT_FACILITADOR_EVALUACION_NOTAS,
            ANEXO_RETO_CHECKPOINT_WA,
            ANEXO_EVALUACION_PUNTOS,
            ANEXO_EVALUACION_NOTAS,
        ):
            with self.subTest(prompt=prompt[:40]):
                self.assertIn('PROHIBIDO usar emojis', prompt)
                self.assertNotIn('Máximo 2 emojis', prompt)

    def test_tecnicoagro_pide_prosa_y_no_bloques(self):
        self.assertNotIn('RETO DE CAMPO', PROMPT_TECNICOAGRO)
        self.assertIn('prosa corrida', PROMPT_TECNICOAGRO)
        self.assertIn('Prosa corrida', ANEXO_RETO_CHECKPOINT_WA)


class RetoGeneradoSinEmojisTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(nombre='Org Agro Emoji', activo=True)
        self.curso = Curso.objects.create(
            nombre='Apiarios',
            cliente=self.cliente,
            activo=True,
            perfil_facilitador=Curso.PERFIL_FACILITADOR_TECNICOAGRO,
        )
        self.modulo = Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='Reconozca el problema',
            contenido='Señales de alarma.',
            publicado_wa=True,
        )

    @patch('core.tutor_ia_modulo._get_client')
    def test_reto_se_entrega_sin_emojis(self, mock_client):
        fake = MagicMock()
        fake.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(
                content='🌱 Hoy: revise 10 colmenas 🐝 y registre cuántas tienen cría salteada.'
            ))]
        )
        mock_client.return_value = fake

        reto = generar_reto_facilitador(
            [self.modulo], self.curso.nombre, curso=self.curso, modulo_checkpoint=self.modulo,
        )

        for emoji in ('🌱', '🐝'):
            self.assertNotIn(emoji, reto)
        self.assertIn('revise 10 colmenas', reto)

    def test_presentaciones_entre_agentes_sin_emojis(self):
        msg_facilitador, msg_asistente = generar_presentacion_agentes(
            self.curso.nombre, 'Ana', curso=self.curso,
        )

        for texto in (msg_facilitador, msg_asistente):
            for emoji in EMOJIS_FRECUENTES:
                self.assertNotIn(emoji, texto)
        self.assertIn('Ana', msg_facilitador)
