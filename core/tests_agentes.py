from django.test import SimpleTestCase

from core.helpers_examenes import debe_activar_checkpoint_reto_ia as debe_activar_reto
from core.helpers_examenes import es_modulo_checkpoint_reto_ia


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

	def test_curso_5_modulos_checkpoint_1_3_y_ultimo(self):
		self.assertTrue(debe_activar_reto(numero_modulo=1, total_modulos=5, usar_agentes_ia_curso=True))
		self.assertFalse(debe_activar_reto(numero_modulo=2, total_modulos=5, usar_agentes_ia_curso=True))
		self.assertTrue(debe_activar_reto(numero_modulo=3, total_modulos=5, usar_agentes_ia_curso=True))
		self.assertTrue(debe_activar_reto(numero_modulo=5, total_modulos=5, usar_agentes_ia_curso=True))

	def test_modulo_3_siempre_activa_en_curso_largo(self):
		self.assertTrue(debe_activar_reto(numero_modulo=3, total_modulos=10, usar_agentes_ia_curso=True))

	def test_curso_10_modulos_checkpoints_1_3_6_9_10(self):
		"""Cursos largos (>5): retos al cerrar 1, 3, cada múltiplo de 3 >5 (no último), y último módulo."""
		self.assertTrue(debe_activar_reto(1, 10, True))
		self.assertFalse(debe_activar_reto(2, 10, True))
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

	def test_override_modulo_fuerza_si(self):
		from types import SimpleNamespace
		from core.models import Modulo

		m = SimpleNamespace(numero=1, facilitador_checkpoint=Modulo.FACILITADOR_CP_SI)
		self.assertTrue(es_modulo_checkpoint_reto_ia(m, 5, True))

	def test_override_modulo_fuerza_no_mismo_que_seria_reto(self):
		from types import SimpleNamespace
		from core.models import Modulo

		m = SimpleNamespace(numero=3, facilitador_checkpoint=Modulo.FACILITADOR_CP_NO)
		self.assertFalse(es_modulo_checkpoint_reto_ia(m, 5, True))

	def test_override_auto_igual_regla_numerica(self):
		from types import SimpleNamespace
		from core.models import Modulo

		m = SimpleNamespace(numero=4, facilitador_checkpoint=Modulo.FACILITADOR_CP_AUTO)
		self.assertEqual(
			es_modulo_checkpoint_reto_ia(m, 10, True),
			debe_activar_reto(4, 10, True),
		)
