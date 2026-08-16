import time
from datetime import date, datetime, timedelta
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
from core.drip_schedule import drip_bloquea_siguiente_modulo
from core.response_templates import get_response_for_intent, _generar_completado_final
from core.security_handler import _url_politica_datos_cliente
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

	def test_drip_bloquea_primer_listo_tras_completar_modulo(self):
		estudiante = self._crear_estudiante('111')
		curso, modulo_1, _ = self._crear_curso_y_modulos('Curso Drip Primer Listo', dias_espera=1)
		modulo_1.facilitador_checkpoint = Modulo.FACILITADOR_CP_NO
		modulo_1.save(update_fields=['facilitador_checkpoint'])
		ProgresoEstudiante.objects.create(
			estudiante=estudiante,
			curso=curso,
			modulo_actual=modulo_1,
		)

		respuesta = get_response_for_intent(
			'continuar_leccion',
			estudiante.nombre,
			estudiante_id=estudiante.id,
			mensaje_original='listo',
		)
		self.assertIn('se desbloquea el', respuesta)
		self.assertIn('preparando tu siguiente sesión', respuesta)

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

	def test_drip_desbloquea_por_fecha_no_por_hora(self):
		estudiante = self._crear_estudiante('901')
		curso, modulo_1, _ = self._crear_curso_y_modulos('Curso Drip Fecha', dias_espera=1)
		progreso = ProgresoEstudiante.objects.create(
			estudiante=estudiante,
			curso=curso,
			modulo_actual=modulo_1,
			fecha_ultimo_avance=timezone.now(),
		)
		ModuloCompletado.objects.create(progreso=progreso, modulo=modulo_1)
		base = date(2026, 4, 25)
		with patch('core.drip_schedule.timezone.localdate') as mock_localdate:
			mock_localdate.side_effect = lambda dt=None: (base if dt is not None else base + timedelta(days=1))
			self.assertFalse(drip_bloquea_siguiente_modulo(progreso, modulo_1))

	def test_calendario_modulo_bloquea_sin_dias_espera(self):
		"""habilitado_desde en el siguiente módulo bloquea aunque dias_espera=0."""
		estudiante = self._crear_estudiante('cal1')
		curso, modulo_1, modulo_2 = self._crear_curso_y_modulos('Curso Solo Calendario', dias_espera=0)
		modulo_2.habilitado_desde = timezone.now() + timedelta(days=5)
		modulo_2.save(update_fields=['habilitado_desde'])
		progreso = ProgresoEstudiante.objects.create(
			estudiante=estudiante,
			curso=curso,
			modulo_actual=modulo_1,
			fecha_ultimo_avance=timezone.now(),
		)
		ModuloCompletado.objects.create(progreso=progreso, modulo=modulo_1)
		self.assertTrue(drip_bloquea_siguiente_modulo(progreso, modulo_1))
		respuesta = get_response_for_intent(
			'continuar_leccion',
			estudiante.nombre,
			estudiante_id=estudiante.id,
			mensaje_original='listo',
		)
		self.assertIn('siguiente módulo', respuesta.lower())

	def test_habilitacion_cliente_sustituye_global(self):
		from core.models import HabilitacionModuloDripCliente

		cliente = Cliente.objects.create(
			nombre='Org Cal',
			contacto_principal='X',
			email='x@test.com',
			telefono='57',
		)
		estudiante = Estudiante.objects.create(
			cedula='200200',
			nombre='Est Cal',
			telefono='573009991122',
			cliente=cliente,
		)
		curso, modulo_1, modulo_2 = self._crear_curso_y_modulos('Curso Override Cal', dias_espera=0)
		modulo_2.habilitado_desde = timezone.now() + timedelta(days=10)
		modulo_2.save(update_fields=['habilitado_desde'])
		# Cliente: más pronto → debe bloquear hasta la fecha cliente, no la global
		antes = timezone.now() + timedelta(days=1)
		HabilitacionModuloDripCliente.objects.create(
			cliente=cliente,
			curso=curso,
			modulo=modulo_2,
			habilitado_desde=antes,
			activo=True,
		)
		progreso = ProgresoEstudiante.objects.create(
			estudiante=estudiante,
			curso=curso,
			modulo_actual=modulo_1,
			fecha_ultimo_avance=timezone.now(),
		)
		ModuloCompletado.objects.create(progreso=progreso, modulo=modulo_1)
		self.assertTrue(drip_bloquea_siguiente_modulo(progreso, modulo_1))
		from core.drip_schedule import habilitado_desde_efectivo

		self.assertEqual(habilitado_desde_efectivo(estudiante, modulo_2), antes)

	def test_continuar_leccion_lista_cursos_si_otro_esta_disponible(self):
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
		# Un curso bloqueado no debe ocultar otro que sí puede continuarse.
		self.assertIn('Tienes varios cursos activos', respuesta)
		self.assertIn('Curso A Drip', respuesta)
		self.assertIn('Curso B Libre', respuesta)

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

	def test_post_reto_primer_listo_muestra_siguiente_modulo_sin_saltar(self):
		"""Tras Darío+facilitadora el puntero pasa al módulo 4; el primer 'listo' debe mostrar el 4, no cerrarlo."""
		estudiante = self._crear_estudiante('44')
		curso = Curso.objects.create(nombre='Curso Reto cinco mods', dias_espera_entre_modulos=0)
		mods = []
		for n in range(1, 6):
			mods.append(
				Modulo.objects.create(
					curso=curso,
					numero=n,
					titulo=f'Módulo test {n}',
					descripcion='D',
					contenido=f'CONTENIDO_BLOQUE_{n}',
				)
			)
		m1, m2, m3, m4, m5 = mods
		progreso = ProgresoEstudiante.objects.create(
			estudiante=estudiante,
			curso=curso,
			modulo_actual=m4,
			completado=False,
		)
		for m in (m1, m2, m3):
			ModuloCompletado.objects.create(progreso=progreso, modulo=m)
		estudiante.contexto_temporal = {
			'post_reto_entregar_modulo_id': m4.id,
			'curso_activo_id': curso.id,
		}
		estudiante.save()
		respuesta = get_response_for_intent(
			'continuar_leccion',
			estudiante.nombre,
			estudiante_id=estudiante.id,
			mensaje_original='listo',
		)
		self.assertIn('CONTENIDO_BLOQUE_4', respuesta)
		progreso.refresh_from_db()
		self.assertEqual(progreso.modulo_actual_id, m4.id)
		self.assertFalse(ModuloCompletado.objects.filter(progreso=progreso, modulo=m4).exists())

		# El lock anti-duplicado impide otro *listo* en <45s; retrocedemos el timestamp de prueba.
		estudiante.refresh_from_db()
		_ctx = dict(estudiante.contexto_temporal or {})
		_ctx['_ts_leccion'] = time.time() - 60
		estudiante.contexto_temporal = _ctx
		estudiante.save(update_fields=['contexto_temporal'])

		respuesta2 = get_response_for_intent(
			'continuar_leccion',
			estudiante.nombre,
			estudiante_id=estudiante.id,
			mensaje_original='listo',
		)
		progreso.refresh_from_db()
		self.assertEqual(progreso.modulo_actual_id, m5.id)
		self.assertTrue(ModuloCompletado.objects.filter(progreso=progreso, modulo=m4).exists())

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
	def test_reenganche_drip_usa_template_hsm_si_configurado(self):
		try:
			from core.tasks import reenganche_drip_content_diario
			from core import whatsapp_service as ws_module
			from core import utils as utils_module
		except ModuleNotFoundError as exc:
			self.skipTest(f"Dependencia no disponible para task test: {exc}")
		with patch.object(ws_module, 'enviar_template_twilio') as mock_template, \
			 patch.object(utils_module, 'enviar_whatsapp_twilio') as mock_texto:
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

	@override_settings(URL_POLITICA_DATOS='https://eki.com.co/politica-general')
	def test_url_habeas_data_prefiere_override_de_cliente(self):
		cliente = Cliente.objects.create(
			nombre='Cliente Habeas',
			contacto_principal='Legal',
			email='legal@cliente.com',
			telefono='3001230000',
			enlace_habeas_data='https://cliente.com/politica-datos',
		)
		estudiante = Estudiante.objects.create(
			cedula='300001',
			nombre='Estudiante Habeas',
			telefono='573001110001',
			cliente=cliente,
		)
		self.assertEqual(
			_url_politica_datos_cliente(estudiante=estudiante),
			'https://cliente.com/politica-datos'
		)
