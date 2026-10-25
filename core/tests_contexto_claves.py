"""contexto_temporal conserva las claves de la persona al cambiar de estado (EKI_CONTEXTO_CONSERVA_CLAVES)."""
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings

from core.conversacion.claves_contexto import contexto_limpio
from core.models import Cliente, Curso, Estudiante, Modulo, PreguntaModulo, ProgresoEstudiante

CERT = {'certificado_id': 7, 'curso_id': 3, 'ts': '2026-10-25T00:00:00', 'cerrar_avance': False}
ANTES = {
    'tipo': 'reto_facilitador',
    'progreso_id': 9,
    'reto_texto': 'x',
    'curso_activo_id': 3,
    'cert_envio_pendiente': CERT,
    'radar_empleabilidad_activo': True,
    'conteo_ayuda': 2,
}


class ContextoLimpioTests(SimpleTestCase):
    def test_apagado_es_lo_de_siempre(self):
        self.assertIsNone(contexto_limpio(ANTES))
        nuevo = {'tipo': 'pregunta_modulo', 'progreso_id': 9}
        self.assertIs(contexto_limpio(ANTES, nuevo), nuevo)

    @override_settings(EKI_CONTEXTO_CONSERVA_CLAVES=True)
    def test_al_cerrar_quedan_solo_las_claves_de_la_persona(self):
        self.assertEqual(
            contexto_limpio(ANTES),
            {'curso_activo_id': 3, 'cert_envio_pendiente': CERT, 'radar_empleabilidad_activo': True},
        )

    @override_settings(EKI_CONTEXTO_CONSERVA_CLAVES=True)
    def test_al_abrir_el_estado_nuevo_se_suma_y_gana(self):
        nuevo = {'tipo': 'asistente_dario', 'curso_activo_id': 5, 'progreso_id': 10}
        self.assertEqual(
            contexto_limpio(ANTES, nuevo),
            {
                'tipo': 'asistente_dario', 'curso_activo_id': 5, 'progreso_id': 10,
                'cert_envio_pendiente': CERT, 'radar_empleabilidad_activo': True,
            },
        )

    @override_settings(EKI_CONTEXTO_CONSERVA_CLAVES=True)
    def test_sin_nada_que_conservar_queda_vacio(self):
        self.assertIsNone(contexto_limpio({'tipo': 'pregunta_modulo'}))
        self.assertIsNone(contexto_limpio(None))
        self.assertIsNone(contexto_limpio(['no', 'es', 'dict']))
        self.assertEqual(contexto_limpio(None, {'tipo': 'x'}), {'tipo': 'x'})

    @override_settings(EKI_CONTEXTO_CONSERVA_CLAVES=True)
    def test_no_modifica_el_contexto_de_entrada(self):
        antes = dict(ANTES)
        contexto_limpio(antes, {'tipo': 'y'})
        self.assertEqual(antes, ANTES)


class ConCursoTestCase(TestCase):
    """Una persona en el módulo 1 con certificado por enviar y empleabilidad en el contexto."""

    def setUp(self):
        self.cli = Cliente.objects.create(nombre='Org Claves', activo=True)
        self.curso = Curso.objects.create(nombre='Claves', cliente=self.cli, activo=True, dias_espera_entre_modulos=0)
        self.mod = Modulo.objects.create(
            curso=self.curso, numero=1, titulo='M1', descripcion='d', contenido='c', publicado_wa=True,
        )
        Modulo.objects.create(curso=self.curso, numero=2, titulo='M2', descripcion='d', contenido='c', publicado_wa=True)
        self.est = Estudiante.objects.create(
            cedula='CC-CLAVES', nombre='Lu', telefono='573009991212', cliente=self.cli, activo=True,
            acepto_terminos=True, estado_chat='ACTIVO',
        )
        self.progreso = ProgresoEstudiante.objects.create(estudiante=self.est, curso=self.curso, modulo_actual=self.mod)

    def _con_contexto(self, **estado):
        self.est.contexto_temporal = {'cert_envio_pendiente': CERT, 'radar_empleabilidad_activo': True, **estado}
        self.est.save()

    def _contexto(self):
        self.est.refresh_from_db()
        return self.est.contexto_temporal


@override_settings(EKI_CONTEXTO_CONSERVA_CLAVES=True)
class PreguntaHandlerTests(ConCursoTestCase):
    def setUp(self):
        super().setUp()
        self.pregunta = PreguntaModulo.objects.create(
            modulo=self.mod, pregunta='¿?', opcion_a='a', opcion_b='b', respuesta_correcta='A',
        )

    def test_abrir_la_pregunta_conserva_el_certificado(self):
        from core.pregunta_handler import guardar_contexto_pregunta, guardar_contexto_pregunta_rag

        self._con_contexto(tipo='reto_facilitador', reto_texto='x')
        guardar_contexto_pregunta(self.est, self.mod, self.pregunta, self.progreso)
        ctx = self._contexto()
        self.assertEqual(ctx['tipo'], 'pregunta_modulo')
        self.assertEqual(ctx['cert_envio_pendiente'], CERT)
        self.assertNotIn('reto_texto', ctx)
        guardar_contexto_pregunta_rag(self.est, self.mod, '¿qué aprendió?', self.progreso)
        ctx = self._contexto()
        self.assertEqual((ctx['tipo'], ctx['cert_envio_pendiente']), ('pregunta_rag_ia', CERT))
        self.assertNotIn('pregunta_id', ctx)

    def test_responder_la_pregunta_deja_solo_las_claves_de_la_persona(self):
        from core.pregunta_handler import guardar_contexto_pregunta, validar_respuesta

        self._con_contexto()
        guardar_contexto_pregunta(self.est, self.mod, self.pregunta, self.progreso)
        validar_respuesta(self.est, 'A')
        self.assertEqual(self._contexto(), {'cert_envio_pendiente': CERT, 'radar_empleabilidad_activo': True})

    def test_respuesta_abierta_deja_solo_las_claves_de_la_persona(self):
        from core.pregunta_handler import guardar_contexto_pregunta_rag, procesar_respuesta_abierta_ia

        self._con_contexto()
        guardar_contexto_pregunta_rag(self.est, self.mod, '¿qué aprendió?', self.progreso)
        with patch('core.tutor_ia_modulo.evaluar_respuesta_modulo', return_value=(True, 'bien')):
            procesar_respuesta_abierta_ia(self.est, 'aprendí a regar')
        self.assertEqual(self._contexto(), {'cert_envio_pendiente': CERT, 'radar_empleabilidad_activo': True})

    @override_settings(EKI_CONTEXTO_CONSERVA_CLAVES=False)
    def test_apagado_se_pisa_como_siempre(self):
        from core.pregunta_handler import guardar_contexto_pregunta, validar_respuesta

        self._con_contexto()
        guardar_contexto_pregunta(self.est, self.mod, self.pregunta, self.progreso)
        self.assertNotIn('cert_envio_pendiente', self._contexto())
        validar_respuesta(self.est, 'A')
        self.assertIsNone(self._contexto())


@override_settings(EKI_CONTEXTO_CONSERVA_CLAVES=True)
class IaEmpaticaTests(ConCursoTestCase):
    def setUp(self):
        super().setUp()
        self.est.estado_onboarding = 'completado'
        self.est.save()

    def _pedir_ayuda_y_seguir(self, segundo):
        from core.security_handler import interceptar_mensaje

        self._con_contexto(curso_activo_id=self.curso.id, tipo='reto_facilitador')
        with patch('core.ia_empatica.responder_con_empatia', return_value='Tranquilo, vamos paso a paso.'):
            interceptar_mensaje(self.est, 'necesito ayuda con el módulo')
        ctx = self._contexto()
        self.assertEqual(ctx['tipo'], 'post_ia_empatica')
        self.assertEqual((ctx['cert_envio_pendiente'], ctx['curso_activo_id']), (CERT, self.curso.id))
        with patch('core.security_handler.procesar_solicitud_soporte', return_value='Le escribe un humano.'):
            interceptar_mensaje(self.est, segundo)
        return self._contexto()

    def test_tras_la_ia_empatica_seguir_normal_conserva_las_claves(self):
        self.assertEqual(
            self._pedir_ayuda_y_seguir('ya entendí, gracias'),
            {'cert_envio_pendiente': CERT, 'radar_empleabilidad_activo': True, 'curso_activo_id': self.curso.id},
        )

    def test_cancelar_la_correccion_de_datos_conserva_las_claves(self):
        from core.correccion_datos import iniciar_flujo_correccion, procesar_flujo_correccion

        self._con_contexto(curso_activo_id=self.curso.id)
        iniciar_flujo_correccion(self.est)
        self.assertEqual(self._contexto()['tipo'], 'correccion_datos')
        procesar_flujo_correccion(self.est, 'cancelar')
        self.assertEqual(
            self._contexto(),
            {'cert_envio_pendiente': CERT, 'radar_empleabilidad_activo': True, 'curso_activo_id': self.curso.id},
        )

    def test_salir_de_la_seleccion_de_curso_conserva_las_claves(self):
        from core.conversacion.contexto import Contexto
        from core.conversacion.estados import seleccion_curso

        for texto in ('menu', 'quiero ver el clima'):
            with self.subTest(texto=texto):
                self._con_contexto(curso_activo_id=self.curso.id, tipo='seleccion_curso')
                self.est.estado_onboarding = 'esperando_seleccion_curso'
                self.est.save()
                with patch('core.response_templates.get_response_for_intent', return_value='hola'), \
                        patch('core.eventos_ia.detectar_intent_con_evento', return_value='desconocido'):
                    seleccion_curso.manejar(Contexto(self.est, texto, self.est.telefono, self.est.telefono))
                self.assertEqual(
                    self._contexto(),
                    {'cert_envio_pendiente': CERT, 'radar_empleabilidad_activo': True, 'curso_activo_id': self.curso.id},
                )

    def test_tras_la_ia_empatica_escalar_conserva_las_claves(self):
        self.assertEqual(
            self._pedir_ayuda_y_seguir('quiero hablar con alguien de soporte humano'),
            {'cert_envio_pendiente': CERT, 'radar_empleabilidad_activo': True, 'curso_activo_id': self.curso.id},
        )


@override_settings(EKI_CONTEXTO_CONSERVA_CLAVES=True)
class RetoTests(ConCursoTestCase):
    def _responder_reto(self, es_final):
        from core.conversacion.contexto import Contexto
        from core.conversacion.estados import reto

        self._con_contexto(
            tipo='reto_facilitador', reto_texto='riegue', modulos_reto_ids=[], progreso_id=self.progreso.id,
            es_final=es_final, ultimo_push_curso_id=self.curso.id,
        )
        self.est.estado_onboarding = 'esperando_respuesta_reto'
        self.est.save()
        with patch('core.tutor_ia_modulo.evaluar_reto_facilitador', return_value=(8, 'bien')), \
                patch('core.sandbox_canal.poner_reaccion_espera'), \
                patch('core.certificado_service.crear_certificado_automatico', return_value=None), \
                patch('core.conversacion.estados.reto._radar_msg_si_aplica', return_value=''):
            reto.manejar(Contexto(self.est, 'regué la huerta', self.est.telefono, self.est.telefono))
        return self._contexto()

    def test_reto_intermedio_conserva_las_claves(self):
        ctx = self._responder_reto(es_final=False)
        self.assertEqual(
            (ctx['cert_envio_pendiente'], ctx['radar_empleabilidad_activo'], ctx['ultimo_push_curso_id']),
            (CERT, True, self.curso.id),
        )
        self.assertEqual(ctx['curso_activo_id'], self.curso.id)
        self.assertNotIn('reto_texto', ctx)

    def test_reto_final_sin_pregunta_abierta_deja_solo_las_claves(self):
        self.assertEqual(
            self._responder_reto(es_final=True),
            {'cert_envio_pendiente': CERT, 'radar_empleabilidad_activo': True, 'ultimo_push_curso_id': self.curso.id},
        )

    def test_reto_final_con_pregunta_abierta_conserva_las_claves(self):
        from core.models import PreguntaAbiertaFinalCurso

        pregunta = PreguntaAbiertaFinalCurso.objects.create(curso=self.curso, pregunta='¿Qué cambiaría?', activa=True)
        ctx = self._responder_reto(es_final=True)
        self.assertEqual(ctx['tipo'], 'pregunta_abierta_final')
        self.assertEqual(ctx['pregunta_abierta_final_id'], pregunta.id)
        self.assertEqual((ctx['cert_envio_pendiente'], ctx['ultimo_push_curso_id']), (CERT, self.curso.id))
        self.assertNotIn('reto_texto', ctx)


@override_settings(EKI_CONTEXTO_CONSERVA_CLAVES=True)
class PreguntaAbiertaFinalTests(ConCursoTestCase):
    def _responder(self, pregunta):
        from core.conversacion.contexto import Contexto
        from core.conversacion.estados import pregunta_abierta_final

        self._con_contexto(
            tipo='pregunta_abierta_final', curso_id=self.curso.id, progreso_id=self.progreso.id,
            pregunta_abierta_final_id=pregunta.id, ultimo_push_curso_id=self.curso.id,
        )
        self.est.estado_onboarding = 'esperando_respuesta_pregunta_abierta_final'
        self.est.save()
        with patch('core.tutor_ia_modulo.evaluar_reto_facilitador', return_value=(8, 'bien')), \
                patch('core.sandbox_canal.poner_reaccion_espera'), \
                patch('core.certificado_service.crear_certificado_automatico', return_value=None), \
                patch('core.conversacion.estados.pregunta_abierta_final._radar_msg_si_aplica', return_value=''):
            pregunta_abierta_final.manejar(Contexto(self.est, 'mediría la humedad', self.est.telefono, self.est.telefono))
        return self._contexto()

    def test_siguiente_pregunta_conserva_las_claves(self):
        from core.models import PreguntaAbiertaFinalCurso

        p1 = PreguntaAbiertaFinalCurso.objects.create(curso=self.curso, orden=1, pregunta='¿Uno?', activa=True)
        p2 = PreguntaAbiertaFinalCurso.objects.create(curso=self.curso, orden=2, pregunta='¿Dos?', activa=True)
        ctx = self._responder(p1)
        self.assertEqual((ctx['tipo'], ctx['pregunta_abierta_final_id']), ('pregunta_abierta_final', p2.id))
        self.assertEqual((ctx['cert_envio_pendiente'], ctx['ultimo_push_curso_id']), (CERT, self.curso.id))

    def test_ultima_pregunta_deja_solo_las_claves(self):
        from core.models import PreguntaAbiertaFinalCurso

        p1 = PreguntaAbiertaFinalCurso.objects.create(curso=self.curso, orden=1, pregunta='¿Uno?', activa=True)
        self.assertEqual(
            self._responder(p1),
            {'cert_envio_pendiente': CERT, 'radar_empleabilidad_activo': True, 'ultimo_push_curso_id': self.curso.id},
        )


@override_settings(EKI_CONTEXTO_CONSERVA_CLAVES=True)
class AsistenteTests(ConCursoTestCase):
    def _listo(self, modulos_reto_ids):
        from core.conversacion.contexto import Contexto
        from core.conversacion.estados import asistente

        self._con_contexto(
            tipo='asistente_dario', preguntas_hechas=1, modulos_reto_ids=modulos_reto_ids,
            progreso_id=self.progreso.id, curso_activo_id=self.curso.id,
        )
        self.est.estado_onboarding = 'esperando_respuesta_asistente'
        self.est.save()
        with patch('core.tutor_ia_modulo.generar_reto_facilitador', return_value='Riegue la huerta.'):
            asistente.manejar(Contexto(self.est, 'listo', self.est.telefono, self.est.telefono))
        return self._contexto()

    def test_pasar_al_reto_conserva_las_claves(self):
        ctx = self._listo([self.mod.id])
        self.assertEqual((ctx['tipo'], ctx['reto_texto']), ('reto_facilitador', 'Riegue la huerta.'))
        self.assertEqual((ctx['cert_envio_pendiente'], ctx['curso_activo_id']), (CERT, self.curso.id))
        self.assertNotIn('preguntas_hechas', ctx)

    def test_reto_vacio_deja_solo_las_claves(self):
        self.assertEqual(
            self._listo([]),
            {'cert_envio_pendiente': CERT, 'radar_empleabilidad_activo': True, 'curso_activo_id': self.curso.id},
        )


@override_settings(EKI_CONTEXTO_CONSERVA_CLAVES=True)
class RetoDespuesDeMariaTests(ConCursoTestCase):
    def test_abrir_el_reto_conserva_las_claves(self):
        from core.lineas.reto import activar_reto_despues_de_maria

        self._con_contexto(tipo='asistente_maria', modulo_id=self.mod.id, curso_activo_id=self.curso.id)
        with patch('core.tutor_ia_modulo.generar_reto_facilitador', return_value='Riegue la huerta.'):
            activar_reto_despues_de_maria(self.est, 'Bien.', self.progreso.id, [self.mod.id], False)
        ctx = self._contexto()
        self.assertEqual((ctx['tipo'], ctx['reto_texto']), ('reto_facilitador', 'Riegue la huerta.'))
        self.assertEqual((ctx['cert_envio_pendiente'], ctx['curso_activo_id']), (CERT, self.curso.id))
        self.assertNotIn('modulo_id', ctx)

    def test_reto_vacio_deja_solo_las_claves(self):
        from core.lineas.reto import activar_reto_despues_de_maria

        self._con_contexto(tipo='asistente_maria', curso_activo_id=self.curso.id)
        activar_reto_despues_de_maria(self.est, 'Bien.', None, [], False)
        self.assertEqual(
            self._contexto(),
            {'cert_envio_pendiente': CERT, 'radar_empleabilidad_activo': True, 'curso_activo_id': self.curso.id},
        )
