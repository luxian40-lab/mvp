"""Contrato A3: lo que hace hoy la línea 2 (modo Twilio, curso lineal).

La persona llega inscrita por su organización. No hay menú de planes ni agentes.
Un test marcado expectedFailure es un hueco conocido: cuando se arregle, pasa
a ser éxito inesperado y hay que quitar la marca.
"""
import unittest
from datetime import date

from core.inscripcion_curso import inscribir_estudiante_en_curso
from core.models import Cliente, Estudiante, PasoModulo, ProgresoEstudiante, SeccionModulo
from core.module_steps import entregar_paso_indice, reset_progreso_pasos_modulo
from core.tests_support.contrato_linea import (
    LINEA_2,
    ContratoLineaTestCase,
    crear_curso,
    mensaje_boton_plantilla,
)

TEL = '573001110002'
CEDULA = '1098765432'
RESPUESTA_LLM = 'RESPUESTA_LLM_FIJA'
SOLO_CURSO = 'Esta línea es solo del curso'


class ContratoLinea2Tests(ContratoLineaTestCase):
    def setUp(self):
        super().setUp()
        self.org = Cliente.objects.create(
            nombre='Org Lineal',
            contacto_principal='Coord',
            email='lineal@eki.test',
            telefono='573000000222',
            activo=True,
            fecha_fin_suscripcion=date(2099, 12, 31),
        )
        self.curso_1 = crear_curso('Lineal1', cliente=self.org, orden=1)
        self.curso_2 = crear_curso('Lineal2', cliente=self.org, orden=2)
        self.est = Estudiante.objects.create(
            cedula=CEDULA, nombre='Beto Lineal', telefono=TEL, cliente=self.org, activo=True,
        )
        inscribir_estudiante_en_curso(self.est, self.curso_1)

    def escribir2(self, texto):
        return self.escribir(TEL, texto, linea=LINEA_2)

    def _identidad(self, campana='inicio'):
        self.lanzar_campana([self.est], linea=LINEA_2, nombre=campana)
        self.turno(TEL, mensaje_boton_plantilla('Iniciar'), linea=LINEA_2)
        self.escribir2('acepto')
        self.escribir2(CEDULA)
        return self.escribir2('si')

    def _progreso(self, curso):
        return ProgresoEstudiante.objects.get(estudiante=self.est, curso=curso)

    def _hasta_reto_final(self):
        self._identidad()
        self.escribir2('continuemos')
        return self.escribir2('listo')

    # Campaña e identidad

    def test_campana_sale_por_la_linea_2_y_pide_habeas_y_cedula(self):
        envios = self.lanzar_campana([self.est], linea=LINEA_2)
        self.assertEqual([(e.tipo, e.phone_id) for e in envios], [('template', LINEA_2.phone_id)])
        habeas = self.turno(TEL, mensaje_boton_plantilla('Iniciar'), linea=LINEA_2)
        self.assertEqual(habeas[0].ids, ['acepto', 'no_acepto'])
        cedula = self.escribir2('acepto')
        self.assertIn('número de cédula', cedula[0].texto)
        confirma = self.escribir2(CEDULA)
        self.assertEqual(confirma[0].ids, ['si', 'no'])

    def test_confirmar_datos_responde_solo_curso_sin_menu(self):
        envios = self._identidad()
        self.assertEqual(len(envios), 1)
        self.assertIn(SOLO_CURSO, envios[0].texto)
        self.assertIn('*continuar*', envios[0].texto)
        self.assertEqual(envios[0].ids, [])
        self.est.refresh_from_db()
        self.assertEqual(self.est.estado_chat, 'ACTIVO')

    @unittest.expectedFailure
    def test_esperado_confirmar_entrega_el_curso_directo(self):
        """Hueco conocido: el flujo de Twilio entregaba saludo y módulo 1 al confirmar."""
        envios = self._identidad()
        textos = ' '.join(e.texto for e in envios)
        self.assertIn('Soy el Formador', textos)
        self.assertIn('CONTENIDO_Lineal1_1', textos)

    def test_hoy_continuar_salta_al_modulo_2_sin_mostrar_el_1(self):
        self._identidad()
        envios = self.escribir2('continuemos')
        self.assertEqual(len(envios), 2)
        self.assertIn('*Módulo 2: Lineal1 M2*', envios[0].texto)
        self.assertNotIn('CONTENIDO_Lineal1_1', ' '.join(e.texto for e in self.salida.mensajes()))
        self.assertEqual(envios[1].ids, ['continuemos'])
        self.assertEqual(self._progreso(self.curso_1).modulo_actual.numero, 2)

    # Curso, evaluación y certificado

    def test_ultimo_listo_abre_el_reto_final(self):
        envios = self._hasta_reto_final()
        self.assertEqual(len(envios), 1)
        self.assertIn('reto final', envios[0].texto)
        self.est.refresh_from_db()
        self.assertEqual(self.est.estado_onboarding, 'esperando_respuesta_asistente')

    def test_reto_respondido_completa_y_anuncia_el_certificado(self):
        self.salida.llm_responde(RESPUESTA_LLM)
        self._hasta_reto_final()
        planteo = self.escribir2('continuemos')
        self.assertIn(RESPUESTA_LLM, planteo[0].texto)
        cierre = self.escribir2('Primero anoto todo y reviso cada semana con mi familia')
        self.assertIn('Ha completado el curso: *Lineal1*', cierre[0].texto)
        self.assertIn('certificado se está generando', cierre[-1].texto)
        self.assertTrue(self._progreso(self.curso_1).completado)
        self.est.refresh_from_db()
        self.assertEqual(self.est.estado_onboarding, 'curso_finalizado')

    def test_evaluacion_de_opciones_pide_la_letra_y_no_avanza_con_listo(self):
        modulo = self.curso_1.modulos.order_by('numero').first()
        seccion = SeccionModulo.objects.create(modulo=modulo, orden=1, titulo='S')
        PasoModulo.objects.create(
            modulo=modulo, seccion=seccion, orden=1, titulo='Quiz',
            tipo=PasoModulo.TIPO_EVAL_OPC, contenido='Elija',
            opciones_json={'A': 'Uno', 'B': 'Dos', 'correcta': 'B'},
        )
        self._identidad()
        progreso = self._progreso(self.curso_1)
        reset_progreso_pasos_modulo(progreso, save=True)
        entregar_paso_indice(progreso, modulo, 1)
        envios = self.escribir2('listo')
        self.assertIn('letra', envios[0].texto.lower())
        progreso.refresh_from_db()
        self.assertTrue(progreso.esperando_respuesta_evaluacion_paso)
        self.assertEqual(progreso.modulo_actual_id, modulo.id)

    def test_hoy_hola_retoma_el_modulo_con_los_marcadores_crudos(self):
        self._identidad()
        envios = self.escribir2('hola')
        self.assertEqual(len(envios), 1)
        self.assertTrue(envios[0].texto.startswith('[MULTI_MSG]'))
        self.assertIn('CONTENIDO_Lineal1_1[SEP]', envios[0].texto)

    @unittest.expectedFailure
    def test_esperado_hola_parte_el_modulo_en_mensajes(self):
        """Hueco conocido: el cuerpo manda [MULTI_MSG] por enviar_whatsapp_twilio y Meta no lo parte."""
        self._identidad()
        envios = self.escribir2('hola')
        self.assertFalse([e for e in envios if '[MULTI_MSG]' in e.texto or '[SEP]' in e.texto])

    # Lo que la línea 2 no tiene

    def test_pedir_asesor_responde_solo_curso(self):
        self._identidad()
        for palabra in ('asesoria', 'nat', 'coach'):
            envios = self.escribir2(palabra)
            self.assertEqual(len(envios), 1, palabra)
            self.assertIn(SOLO_CURSO, envios[0].texto, palabra)

    def test_formacion_no_muestra_carrusel(self):
        self._identidad()
        envios = self.escribir2('formacion')
        self.assertFalse([e for e in envios if e.cuerpo.get('interactive', {}).get('type') == 'carousel'])

    def test_aula_de_un_registrado_entrega_el_codigo_por_meta(self):
        self._identidad()
        envios = self.escribir2('aula')
        self.assertEqual(len(envios), 1)
        self.assertEqual(envios[0].phone_id, LINEA_2.phone_id)
        self.assertRegex(envios[0].texto, r'\*\d{6}\*')

    # Segunda campaña

    def test_segunda_campana_vuelve_a_pedir_identidad_y_sigue_el_curso_nuevo(self):
        self.salida.llm_responde(RESPUESTA_LLM)
        self._hasta_reto_final()
        self.escribir2('continuemos')
        self.escribir2('Primero anoto todo y reviso cada semana con mi familia')
        inscribir_estudiante_en_curso(self.est, self.curso_2)
        confirma = self._identidad(campana='segunda')
        self.assertIn(SOLO_CURSO, confirma[0].texto)
        envios = self.escribir2('continuemos')
        self.assertIn('*Módulo 2: Lineal2 M2*', envios[0].texto)
        self.assertTrue(self._progreso(self.curso_1).completado)
        self.assertEqual(self._progreso(self.curso_2).modulo_actual.numero, 2)

    def test_todo_sale_por_la_linea_2(self):
        self._hasta_reto_final()
        self.assertEqual({e.phone_id for e in self.salida.mensajes()}, {LINEA_2.phone_id})
        self.assertFalse([e for e in self.salida.envios if e.canal == 'twilio'])
