"""Contrato A2: lo que hace hoy la línea principal (versión Meta), de la campaña al fin del curso.

Fija el comportamiento actual, también donde es raro: si un test cae,
el cambio de comportamiento tiene que ser a propósito.
"""
from datetime import date

from core.models import Cliente, Estudiante, ProgresoEstudiante, SandboxCanalSesion
from core.planes_linea import PLAN_ASESOR_60, PLAN_CURSO_ASESOR, inicio_mes_local
from core.tests_support.contrato_linea import (
    LINEA_PRINCIPAL,
    ContratoLineaTestCase,
    crear_curso,
    mensaje_boton_plantilla,
)

TEL = '573001110001'
CEDULA = '1012345678'
RESPUESTA_LLM = 'RESPUESTA_LLM_FIJA'


class ContratoLineaPrincipalTests(ContratoLineaTestCase):
    def setUp(self):
        super().setUp()
        self.org = Cliente.objects.create(
            nombre='Org Contrato',
            contacto_principal='Coord',
            email='contrato@eki.test',
            telefono='573000000111',
            activo=True,
            fecha_fin_suscripcion=date(2099, 12, 31),
            plan_linea_meta=PLAN_CURSO_ASESOR,
        )
        self.curso_1 = crear_curso('General1', catalogo=True, orden=1)
        self.curso_2 = crear_curso('General2', catalogo=True, orden=2)
        self.est = Estudiante.objects.create(
            cedula=CEDULA, nombre='Ana Contrato', telefono=TEL, cliente=self.org, activo=True,
        )

    def _hasta_menu(self):
        self.lanzar_campana([self.est])
        self.turno(TEL, mensaje_boton_plantilla('Iniciar'))
        self.escribir(TEL, 'acepto')
        self.escribir(TEL, CEDULA)
        return self.tocar(TEL, 'si', 'Sí')

    def _hasta_modulo_1(self):
        self._hasta_menu()
        self.tocar(TEL, 'formacion', 'Formación')
        self.tocar(TEL, f'ver_curso_{self.curso_1.id}', 'Ver curso')
        self.tocar(TEL, f'si_curso_{self.curso_1.id}', 'Sí, este')
        return self.tocar(TEL, 'continuemos', 'Continuar')

    def _hasta_reto_final(self):
        self._hasta_modulo_1()
        self.escribir(TEL, 'listo')
        return self.escribir(TEL, 'listo')

    def _refrescar(self):
        self.est.refresh_from_db()
        return self.est

    # Campaña, habeas, cédula

    def test_campana_manda_la_plantilla_y_deja_a_la_persona_en_habeas(self):
        envios = self.lanzar_campana([self.est])
        self.assertEqual([e.tipo for e in envios], ['template'])
        self.assertEqual(envios[0].phone_id, LINEA_PRINCIPAL.phone_id)
        self.assertEqual(envios[0].destino, TEL)
        est = self._refrescar()
        self.assertEqual(est.estado_chat, 'ESPERANDO_HABEAS_DATA')
        self.assertFalse(est.acepto_terminos)
        self.assertEqual(est.estado_onboarding, 'nuevo')

    def test_boton_iniciar_pide_el_habeas_con_acepto_y_no_acepto(self):
        self.lanzar_campana([self.est])
        envios = self.turno(TEL, mensaje_boton_plantilla('Iniciar'))
        self.assertEqual(len(envios), 1)
        self.assertIn('Ley 1581 de 2012', envios[0].texto)
        self.assertEqual(envios[0].ids, ['acepto', 'no_acepto'])

    def test_no_acepto_no_abre_nada(self):
        self.lanzar_campana([self.est])
        self.turno(TEL, mensaje_boton_plantilla('Iniciar'))
        envios = self.tocar(TEL, 'no_acepto', 'No acepto')
        self.assertEqual(len(envios), 1)
        self.assertIn('Sin la autorización', envios[0].texto)
        self.assertEqual(self._refrescar().estado_chat, 'ESPERANDO_HABEAS_DATA')

    def test_acepto_pide_la_cedula(self):
        self.lanzar_campana([self.est])
        self.turno(TEL, mensaje_boton_plantilla('Iniciar'))
        envios = self.tocar(TEL, 'acepto', 'Acepto')
        self.assertEqual(len(envios), 1)
        self.assertIn('número de cédula', envios[0].texto)
        est = self._refrescar()
        self.assertEqual(est.estado_chat, 'ESPERANDO_CEDULA')
        self.assertTrue(est.acepto_terminos)

    def test_cedula_que_no_coincide_no_avanza(self):
        self.lanzar_campana([self.est])
        self.turno(TEL, mensaje_boton_plantilla('Iniciar'))
        self.escribir(TEL, 'acepto')
        envios = self.escribir(TEL, '999')
        self.assertEqual(len(envios), 1)
        self.assertIn('no coincide', envios[0].texto)
        self.assertEqual(self._refrescar().estado_chat, 'ESPERANDO_CEDULA')

    def test_cedula_correcta_pide_confirmar_los_datos(self):
        self.lanzar_campana([self.est])
        self.turno(TEL, mensaje_boton_plantilla('Iniciar'))
        self.escribir(TEL, 'acepto')
        envios = self.escribir(TEL, '1.012.345.678')
        self.assertEqual(len(envios), 1)
        self.assertIn('Ana Contrato', envios[0].texto)
        self.assertIn(f'CC {CEDULA}', envios[0].texto)
        self.assertEqual(envios[0].ids, ['si', 'no'])
        self.assertEqual(self._refrescar().estado_chat, 'CONFIRMANDO_DATOS')

    # Menú por plan

    def test_confirmar_abre_el_menu_del_plan(self):
        envios = self._hasta_menu()
        self.assertEqual(len(envios), 1)
        self.assertIn('un curso de formación este mes', envios[0].texto)
        self.assertIn('hasta 60 preguntas', envios[0].texto)
        self.assertEqual(envios[0].ids, ['formacion', 'asesoria'])
        est = self._refrescar()
        self.assertEqual(est.estado_chat, 'ACTIVO')
        self.assertEqual(est.estado_onboarding, 'completado')

    def test_sin_plan_no_hay_menu(self):
        self.org.plan_linea_meta = ''
        self.org.save(update_fields=['plan_linea_meta'])
        envios = self._hasta_menu()
        self.assertEqual(len(envios), 1)
        self.assertIn('no tiene un plan activo', envios[0].texto)
        self.assertEqual(envios[0].ids, [])

    def test_plan_solo_asesor_no_ofrece_formacion(self):
        self.org.plan_linea_meta = PLAN_ASESOR_60
        self.org.save(update_fields=['plan_linea_meta'])
        envios = self._hasta_menu()
        self.assertEqual(envios[0].ids, ['asesoria'])
        bloqueo = self.tocar(TEL, 'formacion', 'Formación')
        self.assertIn('no incluye cursos nuevos', bloqueo[0].texto)

    # Carrusel y curso

    def test_formacion_muestra_el_carrusel_de_cursos_generales(self):
        self._hasta_menu()
        envios = self.tocar(TEL, 'formacion', 'Formación')
        self.assertEqual(len(envios), 1)
        self.assertEqual(envios[0].cuerpo['interactive']['type'], 'carousel')
        self.assertEqual(envios[0].ids, [
            f'ver_curso_{self.curso_1.id}', f'info_curso_{self.curso_1.id}',
            f'ver_curso_{self.curso_2.id}', f'info_curso_{self.curso_2.id}',
        ])

    def test_ver_curso_pregunta_y_el_si_inscribe(self):
        self._hasta_menu()
        self.tocar(TEL, 'formacion', 'Formación')
        envios = self.tocar(TEL, f'ver_curso_{self.curso_1.id}', 'Ver curso')
        self.assertEqual(len(envios), 1)
        self.assertIn('¿Arrancamos *General1*?', envios[0].texto)
        self.assertIn('Este mes puede elegir un curso', envios[0].texto)
        self.assertEqual(envios[0].botones, ['Sí, este', 'Otro curso'])
        self.assertEqual(envios[0].ids, [f'si_curso_{self.curso_1.id}', 'otro_curso'])
        self.assertFalse(ProgresoEstudiante.objects.filter(estudiante=self.est, curso=self.curso_1).exists())
        alta = self.tocar(TEL, f'si_curso_{self.curso_1.id}', 'Sí, este')
        self.assertEqual(len(alta), 1)
        self.assertIn('Quedó en *General1*', alta[0].texto)
        self.assertEqual(alta[0].ids, ['continuemos'])
        self.assertTrue(ProgresoEstudiante.objects.filter(estudiante=self.est, curso=self.curso_1).exists())

    def test_otro_curso_vuelve_al_carrusel_sin_inscribir(self):
        self._hasta_menu()
        self.tocar(TEL, 'formacion', 'Formación')
        self.tocar(TEL, f'ver_curso_{self.curso_1.id}', 'Ver curso')
        envios = self.tocar(TEL, 'otro_curso', 'Otro curso')
        self.assertEqual(envios[0].cuerpo['interactive']['type'], 'carousel')
        self.assertFalse(ProgresoEstudiante.objects.filter(estudiante=self.est).exists())

    def test_si_de_la_tarjeta_anterior_no_inscribe(self):
        self._hasta_menu()
        self.tocar(TEL, 'formacion', 'Formación')
        self.tocar(TEL, f'ver_curso_{self.curso_1.id}', 'Ver curso')
        self.tocar(TEL, f'ver_curso_{self.curso_2.id}', 'Ver curso')
        viejo = self.tocar(TEL, f'si_curso_{self.curso_1.id}', 'Sí, este')
        self.assertIn('¿Arrancamos *General2*?', viejo[0].texto)
        self.assertFalse(ProgresoEstudiante.objects.filter(estudiante=self.est).exists())
        self.tocar(TEL, f'si_curso_{self.curso_2.id}', 'Sí, este')
        self.assertFalse(ProgresoEstudiante.objects.filter(estudiante=self.est, curso=self.curso_1).exists())
        self.assertTrue(ProgresoEstudiante.objects.filter(estudiante=self.est, curso=self.curso_2).exists())

    def test_ver_curso_ya_empezado_no_vuelve_a_preguntar(self):
        self._hasta_menu()
        self.tocar(TEL, 'formacion', 'Formación')
        self.tocar(TEL, f'ver_curso_{self.curso_1.id}', 'Ver curso')
        self.tocar(TEL, f'si_curso_{self.curso_1.id}', 'Sí, este')
        envios = self.tocar(TEL, f'ver_curso_{self.curso_1.id}', 'Ver curso')
        self.assertIn('Quedó en *General1*', envios[0].texto)
        self.assertEqual(envios[0].ids, ['continuemos'])
        self.assertEqual(
            ProgresoEstudiante.objects.filter(estudiante=self.est, curso=self.curso_1).count(),
            1,
        )

    def test_continuar_presenta_formador_companero_y_modulo_1(self):
        envios = self._hasta_modulo_1()
        textos = [e.texto for e in envios]
        self.assertEqual(len(textos), 5)
        self.assertIn('Soy el Formador', textos[0])
        self.assertIn('soy el Compañero', textos[1])
        self.assertIn('funciona a través de puntos', textos[2])
        self.assertIn('primer módulo', textos[3])
        self.assertIn('*Módulo 1: General1 M1*', textos[4])
        self.assertIn('CONTENIDO_General1_1', textos[4])

    def test_listo_entrega_el_modulo_siguiente(self):
        self._hasta_modulo_1()
        envios = self.escribir(TEL, 'listo')
        self.assertEqual(len(envios), 2)
        self.assertIn('*Módulo 2: General1 M2*', envios[0].texto)
        self.assertIn('CONTENIDO_General1_2', envios[0].texto)
        self.assertEqual(envios[1].ids, ['continuemos'])

    def test_ultimo_listo_abre_el_reto_final(self):
        envios = self._hasta_reto_final()
        self.assertEqual(len(envios), 1)
        self.assertIn('reto final', envios[0].texto)
        self.assertEqual(envios[0].ids, ['continuemos'])
        est = self._refrescar()
        self.assertEqual(est.estado_onboarding, 'esperando_respuesta_asistente')
        self.assertTrue(est.contexto_temporal.get('es_reto_final'))

    def test_reto_respondido_completa_el_curso(self):
        self.salida.llm_responde(RESPUESTA_LLM)
        self._hasta_reto_final()
        planteo = self.tocar(TEL, 'continuemos', 'Continuar')
        self.assertEqual(len(planteo), 1)
        self.assertIn(RESPUESTA_LLM, planteo[0].texto)
        self.assertEqual(self._refrescar().estado_onboarding, 'esperando_respuesta_reto')
        cierre = self.escribir(TEL, 'Primero mido la finca y anoto los gastos cada semana')
        self.assertIn('De 1 a 10', cierre[0].texto)
        self.assertNotIn('certificado', cierre[0].texto.lower())
        self.assertTrue(ProgresoEstudiante.objects.get(estudiante=self.est, curso=self.curso_1).completado)
        self.assertEqual(self._refrescar().estado_onboarding, 'esperando_nota_cierre')
        diploma = self.escribir(TEL, '8')
        self.assertIn('Ha completado el curso: *General1*', diploma[0].texto)
        self.assertIn('certificado', diploma[-1].texto.lower())
        self.assertEqual(self._refrescar().estado_onboarding, 'curso_finalizado')
        from core.models import NotaCierreCurso
        self.assertEqual(
            NotaCierreCurso.objects.get(estudiante=self.est, curso=self.curso_1).nota,
            8,
        )

    def test_tras_el_curso_listo_avisa_el_cierre_y_menu_vuelve_al_menu(self):
        self.salida.llm_responde(RESPUESTA_LLM)
        self._hasta_reto_final()
        self.tocar(TEL, 'continuemos', 'Continuar')
        self.escribir(TEL, 'Primero mido la finca y anoto los gastos cada semana')
        self.escribir(TEL, '8')
        listo = self.escribir(TEL, 'listo')
        self.assertEqual(len(listo), 1)
        self.assertIn('ya finalizó', listo[0].texto)
        self.assertEqual(listo[0].ids, [])
        menu = self.escribir(TEL, 'menu')
        self.assertEqual(menu[0].ids, ['formacion', 'asesoria'])

    def test_segundo_curso_del_mes_choca_con_el_cupo_del_plan(self):
        self._hasta_menu()
        self.tocar(TEL, 'formacion', 'Formación')
        self.tocar(TEL, f'ver_curso_{self.curso_1.id}', 'Ver curso')
        self.tocar(TEL, f'si_curso_{self.curso_1.id}', 'Sí, este')
        envios = self.tocar(TEL, f'ver_curso_{self.curso_2.id}', 'Ver curso')
        self.assertIn('Este mes ya eligió *General1*', envios[0].texto)
        self.assertFalse(ProgresoEstudiante.objects.filter(estudiante=self.est, curso=self.curso_2).exists())

    # Asesor

    def test_asesoria_lista_los_cinco_agentes(self):
        self._hasta_menu()
        envios = self.tocar(TEL, 'asesoria', 'Asesoría')
        self.assertEqual(envios[0].botones, ['Agrónomo', 'Coach', 'Innovación e IA', 'Ventas', 'Finanzas'])
        self.assertIn('hasta 60 preguntas este mes', envios[0].texto)

    def test_asesor_responde_y_cuenta_la_pregunta(self):
        self.salida.llm_responde(RESPUESTA_LLM)
        self._hasta_menu()
        self.tocar(TEL, 'asesoria', 'Asesoría')
        saludo = self.escribir(TEL, 'nat')
        self.assertIn('*Agrónomo*', saludo[0].texto)
        respuesta = self.escribir(TEL, 'como controlo la broca')
        self.assertEqual([e.texto for e in respuesta], [RESPUESTA_LLM])
        sesion = SandboxCanalSesion.objects.get(telefono=TEL, phone_id=LINEA_PRINCIPAL.phone_id)
        self.assertEqual(sesion.preguntas_mes, 1)

    def test_asesor_sin_cupo_no_llama_al_llm(self):
        self.salida.llm_responde(RESPUESTA_LLM)
        self._hasta_menu()
        self.tocar(TEL, 'asesoria', 'Asesoría')
        self.escribir(TEL, 'nat')
        SandboxCanalSesion.objects.filter(telefono=TEL).update(
            preguntas_mes=60, preguntas_mes_desde=inicio_mes_local().date(),
        )
        llamadas = len(self.salida.llamadas_llm)
        envios = self.escribir(TEL, 'y la roya?')
        self.assertEqual(len(envios), 1)
        self.assertIn('ya usó las 60 preguntas', envios[0].texto)
        self.assertEqual(len(self.salida.llamadas_llm), llamadas)

    # Línea

    def test_aula_de_un_registrado_entrega_el_codigo_por_meta(self):
        self._hasta_menu()
        envios = self.escribir(TEL, 'aula')
        self.assertEqual(len(envios), 1)
        self.assertEqual(envios[0].phone_id, LINEA_PRINCIPAL.phone_id)
        self.assertIn('eki Aprende', envios[0].texto)
        self.assertRegex(envios[0].texto, r'\*\d{6}\*')

    def test_todo_sale_por_la_linea_principal(self):
        self.salida.llm_responde(RESPUESTA_LLM)
        self._hasta_reto_final()
        self.assertEqual({e.phone_id for e in self.salida.mensajes()}, {LINEA_PRINCIPAL.phone_id})
        self.assertFalse([e for e in self.salida.envios if e.canal == 'twilio'])
