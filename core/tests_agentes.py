from django.test import SimpleTestCase

from core.helpers_examenes import debe_activar_checkpoint_reto_ia as debe_activar_reto


class ActivacionAgentesRetoTests(SimpleTestCase):
	def test_curso_6_modulos_activa_en_6(self):
		self.assertTrue(debe_activar_reto(numero_modulo=6, total_modulos=6, usar_agentes_ia_curso=True))

	def test_curso_7_modulos_activa_en_6_y_7(self):
		self.assertTrue(debe_activar_reto(numero_modulo=6, total_modulos=7, usar_agentes_ia_curso=True))
		self.assertTrue(debe_activar_reto(numero_modulo=7, total_modulos=7, usar_agentes_ia_curso=True))

	def test_curso_9_modulos_activa_en_6_9(self):
		self.assertTrue(debe_activar_reto(numero_modulo=6, total_modulos=9, usar_agentes_ia_curso=True))
		self.assertFalse(debe_activar_reto(numero_modulo=7, total_modulos=9, usar_agentes_ia_curso=True))
		self.assertFalse(debe_activar_reto(numero_modulo=8, total_modulos=9, usar_agentes_ia_curso=True))
		self.assertTrue(debe_activar_reto(numero_modulo=9, total_modulos=9, usar_agentes_ia_curso=True))

	def test_curso_5_modulos_solo_3_y_ultimo(self):
		self.assertFalse(debe_activar_reto(numero_modulo=1, total_modulos=5, usar_agentes_ia_curso=True))
		self.assertFalse(debe_activar_reto(numero_modulo=2, total_modulos=5, usar_agentes_ia_curso=True))
		self.assertTrue(debe_activar_reto(numero_modulo=3, total_modulos=5, usar_agentes_ia_curso=True))
		self.assertTrue(debe_activar_reto(numero_modulo=5, total_modulos=5, usar_agentes_ia_curso=True))

	def test_modulo_3_siempre_activa_en_curso_largo(self):
		self.assertTrue(debe_activar_reto(numero_modulo=3, total_modulos=10, usar_agentes_ia_curso=True))

	def test_curso_10_modulos_checkpoints_3_6_9_10(self):
		"""Cursos largos (>5): retos en 3, cada múltiplo de 3 >5 (no último), y último módulo."""
		self.assertTrue(debe_activar_reto(3, 10, True))
		self.assertFalse(debe_activar_reto(4, 10, True))
		self.assertFalse(debe_activar_reto(5, 10, True))
		self.assertTrue(debe_activar_reto(6, 10, True))
		self.assertFalse(debe_activar_reto(7, 10, True))
		self.assertFalse(debe_activar_reto(8, 10, True))
		self.assertTrue(debe_activar_reto(9, 10, True))
		self.assertTrue(debe_activar_reto(10, 10, True))

	def test_usar_agentes_ia_curso_off(self):
		self.assertFalse(debe_activar_reto(3, 10, False))
		self.assertFalse(debe_activar_reto(10, 10, False))
