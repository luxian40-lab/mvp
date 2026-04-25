from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from core.gamificacion import PerfilGamificacion
from core.models import (
	AliadoEmpleabilidad,
	Cliente,
	ConfiguracionDripCliente,
	Curso,
	Estudiante,
	Modulo,
	ModuloCompletado,
	PreguntaAbiertaFinalCurso,
	ProgresoEstudiante,
)
from core.drip_schedule import dias_espera_efectivos
from core.response_templates import get_response_for_intent, _generar_completado_final
from core.selector_curso import continuar_curso_seleccionado
from core.views import _haversine_metros, _procesar_ubicacion_empleabilidad


class DripGeoGamificacionTests(TestCase):
	def _crear_estudiante(self, sufijo='1'):
		return Estudiante.objects.create(
			cedula=f'1000{sufijo}',
			nombre=f'Estudiante {sufijo}',
			telefono=f'5730012345{sufijo}',
		)

	def _crear_curso_y_modulos(self, nombre='Curso Demo', dias_espera=0):
		curso = Curso.objects.create(
			nombre=nombre,
			descripcion='Curso de prueba',
			dias_espera_entre_modulos=dias_espera,
		)
		modulo_1 = Modulo.objects.create(
			curso=curso,
			numero=1,
			titulo='Modulo 1',
			descripcion='Desc 1',
			contenido='Contenido 1',
			duracion_dias=7,
		)
		modulo_2 = Modulo.objects.create(
			curso=curso,
			numero=2,
			titulo='Modulo 2',
			descripcion='Desc 2',
			contenido='Contenido 2',
			duracion_dias=7,
		)
		return curso, modulo_1, modulo_2

	def test_drip_content_bloquea_continuar_leccion(self):
		estudiante = self._crear_estudiante('11')
		curso, modulo_1, _ = self._crear_curso_y_modulos('Curso Drip', dias_espera=7)
		progreso = ProgresoEstudiante.objects.create(
			estudiante=estudiante,
			curso=curso,
			modulo_actual=modulo_1,
			fecha_ultimo_avance=timezone.now() - timedelta(days=1),
		)
		ModuloCompletado.objects.create(progreso=progreso, modulo=modulo_1)

		respuesta = get_response_for_intent(
			'continuar_leccion',
			estudiante.nombre,
			estudiante_id=estudiante.id,
			mensaje_original='listo',
		)

		self.assertIn('se desbloquea el', respuesta)
		self.assertIn('Excelente energía', respuesta)

	def test_drip_override_por_cliente(self):
		cliente = Cliente.objects.create(
			nombre='Coop Test',
			contacto_principal='A',
			email='a@test.com',
			telefono='57',
		)
		estudiante = Estudiante.objects.create(
			cedula='100099',
			nombre='Estudiante Override',
			telefono='573001234599',
			cliente=cliente,
		)
		curso, modulo_1, _ = self._crear_curso_y_modulos('Curso Global', dias_espera=0)
		ConfiguracionDripCliente.objects.create(
			cliente=cliente,
			curso=curso,
			dias_espera_entre_modulos=7,
			activo=True,
		)
		self.assertEqual(dias_espera_efectivos(estudiante, curso), 7)

		progreso = ProgresoEstudiante.objects.create(
			estudiante=estudiante,
			curso=curso,
			modulo_actual=modulo_1,
			fecha_ultimo_avance=timezone.now() - timedelta(days=1),
		)
		ModuloCompletado.objects.create(progreso=progreso, modulo=modulo_1)

		respuesta = get_response_for_intent(
			'continuar_leccion',
			estudiante.nombre,
			estudiante_id=estudiante.id,
			mensaje_original='listo',
		)
		self.assertIn('se desbloquea el', respuesta)

	def test_continuar_leccion_no_lista_cursos_si_drip_en_uno(self):
		estudiante = self._crear_estudiante('22')
		curso_a, mod_a1, _ = self._crear_curso_y_modulos('Curso A Drip', dias_espera=7)
		curso_b, mod_b1, _ = self._crear_curso_y_modulos('Curso B Libre', dias_espera=0)
		pa = ProgresoEstudiante.objects.create(
			estudiante=estudiante,
			curso=curso_a,
			modulo_actual=mod_a1,
			fecha_ultimo_avance=timezone.now() - timedelta(days=1),
		)
		ModuloCompletado.objects.create(progreso=pa, modulo=mod_a1)
		ProgresoEstudiante.objects.create(
			estudiante=estudiante,
			curso=curso_b,
			modulo_actual=mod_b1,
		)
		respuesta = get_response_for_intent(
			'continuar_leccion',
			estudiante.nombre,
			estudiante_id=estudiante.id,
			mensaje_original='continuar',
		)
		self.assertNotIn('Tienes varios cursos activos', respuesta)

	def test_selector_curso_drip_al_elegir_por_numero(self):
		estudiante = self._crear_estudiante('21')
		curso, modulo_1, _ = self._crear_curso_y_modulos('Curso Selector Drip', dias_espera=7)
		progreso = ProgresoEstudiante.objects.create(
			estudiante=estudiante,
			curso=curso,
			modulo_actual=modulo_1,
			fecha_ultimo_avance=timezone.now() - timedelta(days=1),
		)
		ModuloCompletado.objects.create(progreso=progreso, modulo=modulo_1)
		cursos_list = list(Curso.objects.filter(activo=True).order_by('orden', 'nombre'))
		indice = next(i for i, c in enumerate(cursos_list, 1) if c.id == curso.id)
		respuesta = continuar_curso_seleccionado(estudiante.id, indice, str(indice))
		self.assertIn('preparando tu siguiente sesión', respuesta)
		self.assertIn('se desbloquea el', respuesta)

	def test_geogamificacion_respuesta_cercana(self):
		estudiante = self._crear_estudiante('12')
		aliado = AliadoEmpleabilidad.objects.create(
			nombre_empresa='Empresa Aliada',
			latitud=4.926,
			longitud=-74.173,
			vacantes_activas=True,
			codigo_secreto='SUBA123',
			indicacion_sector='costado oriental del parque principal',
		)

		distancia = _haversine_metros(4.926, -74.173, aliado.latitud, aliado.longitud)
		self.assertLessEqual(distancia, 100)

		respuesta = _procesar_ubicacion_empleabilidad(estudiante, 4.926, -74.173)
		estudiante.refresh_from_db()

		self.assertIn('Estás a', respuesta)
		self.assertIn('código secreto', respuesta)
		self.assertEqual(estudiante.estado_onboarding, 'esperando_codigo_empleabilidad')
		self.assertEqual(estudiante.contexto_temporal.get('aliado_empleabilidad_objetivo_id'), aliado.id)

	def test_completado_final_pide_pregunta_abierta(self):
		estudiante = self._crear_estudiante('13')
		curso, modulo_1, _ = self._crear_curso_y_modulos('Curso Abierta', dias_espera=0)
		progreso = ProgresoEstudiante.objects.create(
			estudiante=estudiante,
			curso=curso,
			modulo_actual=modulo_1,
			completado=True,
			fecha_completado=timezone.now(),
		)
		ModuloCompletado.objects.create(progreso=progreso, modulo=modulo_1)
		PerfilGamificacion.objects.get_or_create(estudiante=estudiante)
		PreguntaAbiertaFinalCurso.objects.create(
			curso=curso,
			pregunta='¿Cómo aplicarás este aprendizaje en tu comunidad?',
			activa=True,
		)

		respuesta = _generar_completado_final(estudiante, curso.id)
		estudiante.refresh_from_db()

		self.assertRegex(respuesta.lower(), r'(reto final|pregunta)')
		self.assertIn(
			estudiante.estado_onboarding,
			['esperando_respuesta_pregunta_abierta_final', 'esperando_respuesta_asistente']
		)
		self.assertIsNotNone(estudiante.contexto_temporal)

	@override_settings(TWILIO_TEMPLATE_DRIP_REENGANCHE='HX_TEST_DRIP')
	@patch('core.whatsapp_service.enviar_template_twilio')
	@patch('core.utils.enviar_whatsapp_twilio')
	def test_reenganche_drip_usa_template_hsm_si_configurado(self, mock_texto, mock_template):
		try:
			from core.tasks import reenganche_drip_content_diario
		except ModuleNotFoundError as exc:
			self.skipTest(f"Dependencia no disponible para task test: {exc}")

		mock_template.return_value = {'success': True, 'mensaje_id': 'SM123', 'response': 'ok'}
		mock_texto.return_value = {'success': True, 'mensaje_id': 'SM999', 'response': 'ok'}

		estudiante = self._crear_estudiante('14')
		curso, modulo_1, _ = self._crear_curso_y_modulos('Curso Reenganche', dias_espera=2)
		ProgresoEstudiante.objects.create(
			estudiante=estudiante,
			curso=curso,
			modulo_actual=modulo_1,
			fecha_ultimo_avance=timezone.now() - timedelta(days=2),
		)

		resultado = reenganche_drip_content_diario()

		self.assertEqual(resultado.get('enviados'), 1)
		mock_template.assert_called_once()
		mock_texto.assert_not_called()

	def test_proximidad_bloqueada_por_cliente_fuera_de_ventana(self):
		cliente = Cliente.objects.create(
			nombre='Cliente Sin Ventana',
			contacto_principal='Admin',
			email='cliente@example.com',
			telefono='3000000000',
			habilitar_gamificacion_proximidad=False,
		)
		estudiante = Estudiante.objects.create(
			cedula='200001',
			nombre='Estudiante Ventana',
			telefono='573009999901',
			cliente=cliente,
		)
		AliadoEmpleabilidad.objects.create(
			nombre_empresa='Aliado A',
			cliente=cliente,
			latitud=4.926,
			longitud=-74.173,
			vacantes_activas=True,
			codigo_secreto='COD1',
		)

		respuesta = _procesar_ubicacion_empleabilidad(estudiante, 4.926, -74.173)
		self.assertIn('no está activo', respuesta)

	def test_pregunta_abierta_bloqueada_por_cliente(self):
		cliente = Cliente.objects.create(
			nombre='Cliente Sin Pregunta',
			contacto_principal='Admin 2',
			email='cliente2@example.com',
			telefono='3000000001',
			habilitar_pregunta_abierta_final=False,
		)
		estudiante = Estudiante.objects.create(
			cedula='200002',
			nombre='Estudiante Sin Pregunta',
			telefono='573009999902',
			cliente=cliente,
		)
		curso, modulo_1, _ = self._crear_curso_y_modulos('Curso Sin Pregunta Cliente', dias_espera=0)
		progreso = ProgresoEstudiante.objects.create(
			estudiante=estudiante,
			curso=curso,
			modulo_actual=modulo_1,
			completado=True,
			fecha_completado=timezone.now(),
		)
		ModuloCompletado.objects.create(progreso=progreso, modulo=modulo_1)
		PerfilGamificacion.objects.get_or_create(estudiante=estudiante)
		PreguntaAbiertaFinalCurso.objects.create(
			curso=curso,
			pregunta='Esta pregunta no debe salir para este cliente',
			activa=True,
		)

		respuesta = _generar_completado_final(estudiante, curso.id)
		self.assertNotIn('Pregunta abierta final', respuesta)
