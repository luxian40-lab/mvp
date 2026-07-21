"""Tests ampliados del agente PQRS (máx. 2 preguntas, alcance, contenido curso)."""
from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase

from core.models import Cliente, Estudiante, SolicitudSoporte
from core.pqrs_agent import (
    MENSAJE_CONTENIDO_CURSO,
    MENSAJE_FUERA_ALCANCE,
    aplicar_resultado_pqrs,
    intentar_procesar_seguimiento_pqrs_whatsapp,
    mensaje_activa_soporte,
    procesar_pqrs_automatico,
    procesar_seguimiento_pqrs,
)


def _estudiante() -> Estudiante:
    cliente = Cliente.objects.create(
        nombre='Coop Test',
        nit='900000001-0',
        contacto_principal='Tester',
        email='pqrs@example.com',
        telefono='573000099990',
        activo=True,
    )
    return Estudiante.objects.create(
        cedula='8888888',
        nombre='Est PQRS',
        telefono='573000099991',
        cliente=cliente,
        estado_chat='ACTIVO',
        acepto_terminos=True,
        activo=True,
    )


class TestPQRSAgentReglas(TestCase):
    def setUp(self):
        self.est = _estudiante()

    def test_max_dos_preguntas_escalada(self):
        solicitud = SolicitudSoporte.objects.create(
            estudiante=self.est,
            mensaje_original='ayuda',
            keyword_usada='ayuda',
            estado='en_atencion',
            resuelto_por_agente=False,
            preguntas_realizadas=2,
        )
        resultado = procesar_seguimiento_pqrs(solicitud, 'sigue sin funcionar')
        self.assertTrue(resultado['escalar'])
        self.assertEqual(resultado['categoria'], 'otro')
        self.assertIn('2 intentos', resultado['nota_interna'])

        aplicar_resultado_pqrs(solicitud, resultado)
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, 'pendiente')
        self.assertFalse(solicitud.resuelto_por_agente)

    def test_fuera_de_alcance_remite_facilitador(self):
        solicitud = SolicitudSoporte.objects.create(
            estudiante=self.est,
            mensaje_original='Quiero cambiar mi teléfono',
            keyword_usada='ayuda',
        )
        resultado = procesar_pqrs_automatico(solicitud)
        self.assertIn(MENSAJE_FUERA_ALCANCE, resultado['respuesta_whatsapp'])
        aplicar_resultado_pqrs(solicitud, resultado)
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, 'pendiente')
        self.assertIn('fuera de alcance', solicitud.notas_internas.lower())

    def test_consulta_contenido_no_respondida(self):
        solicitud = SolicitudSoporte.objects.create(
            estudiante=self.est,
            mensaje_original='¿Cuándo se fumiga el café y qué dosis de fertilizante?',
            keyword_usada='ayuda',
        )
        resultado = procesar_pqrs_automatico(solicitud)
        self.assertIn(MENSAJE_CONTENIDO_CURSO, resultado['respuesta_whatsapp'])
        self.assertFalse(resultado['escalar'])
        self.assertNotIn('dosis', resultado['respuesta_whatsapp'].lower())

    def test_pregunta_clarificacion_incrementa_contador(self):
        solicitud = SolicitudSoporte.objects.create(
            estudiante=self.est,
            mensaje_original='ayuda',
            keyword_usada='ayuda',
            estado='en_atencion',
            resuelto_por_agente=False,
            preguntas_realizadas=0,
        )
        raw = (
            '{"categoria":"acceso","respuesta_whatsapp":"¿Podría indicar si es acceso o contenido?",'
            '"escalar":false,"nota_interna":"ambiguo",'
            '"hacer_pregunta_clarificacion":true,"fuera_de_alcance":false,"consulta_contenido_curso":false}'
        )
        with patch('core.pqrs_agent._llamar_openai_pqrs', return_value=raw):
            resultado = procesar_seguimiento_pqrs(solicitud, 'no sé')
        aplicar_resultado_pqrs(solicitud, resultado)
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.preguntas_realizadas, 1)
        self.assertFalse(solicitud.resuelto_por_agente)


class TestAyudaWhatsAppFlujo(TestCase):
    def setUp(self):
        self.est = _estudiante()

    def test_ayuda_con_detalle_activa_soporte(self):
        self.assertTrue(mensaje_activa_soporte('Ayuda no funciona el curso'))

    def test_seguimiento_con_detalle_usa_agente(self):
        solicitud = SolicitudSoporte.objects.create(
            estudiante=self.est,
            mensaje_original='ayuda',
            keyword_usada='curso_ayuda',
            estado='pendiente',
            resuelto_por_agente=False,
        )
        raw = (
            '{"categoria":"contenido","respuesta_whatsapp":"Revise el material del módulo.",'
            '"escalar":false,"accion":"ninguna","nota_interna":"ok",'
            '"hacer_pregunta_clarificacion":false,"fuera_de_alcance":false,'
            '"consulta_contenido_curso":false}'
        )
        with patch('core.pqrs_agent._llamar_openai_pqrs', return_value=raw):
            resp = intentar_procesar_seguimiento_pqrs_whatsapp(
                self.est, 'No funciona el curso',
            )
        self.assertIsNotNone(resp)
        self.assertIn('listo', resp.lower())
        solicitud.refresh_from_db()
        self.assertTrue(solicitud.resuelto_por_agente)
        self.assertEqual(solicitud.estado, 'resuelta')

    def test_listo_no_secuestrado_por_ticket_pendiente(self):
        SolicitudSoporte.objects.create(
            estudiante=self.est,
            mensaje_original='ayuda',
            keyword_usada='curso_ayuda',
            estado='pendiente',
            resuelto_por_agente=False,
        )
        for msg in ('listo', 'Listo', 'continuar', '*listo*'):
            with self.subTest(msg=msg):
                self.assertIsNone(
                    intentar_procesar_seguimiento_pqrs_whatsapp(self.est, msg)
                )


class TestMensajeWhatsAppPQRS(TestCase):
    def test_sin_plantilla_robotica(self):
        from core.pqrs_respuesta import mensaje_whatsapp_pqrs

        msg = mensaje_whatsapp_pqrs('María López', 'Ya puedes ingresar con tu cédula.')
        self.assertEqual(msg, 'Hola María,\n\nYa puedes ingresar con tu cédula.')
        self.assertNotIn('respuesta a tu solicitud', msg.lower())

    def test_respeta_saludo_del_operador(self):
        from core.pqrs_respuesta import mensaje_whatsapp_pqrs

        texto = 'Hola, revisamos tu caso y quedó listo.'
        self.assertEqual(mensaje_whatsapp_pqrs('Pedro', texto), texto)


class TestPQRSRespuestaWhatsApp(TestCase):
    def setUp(self):
        self.est = _estudiante()

    @patch('core.utils.enviar_whatsapp_twilio', return_value={'success': True, 'mensaje_id': 'SM1'})
    def test_aplicar_respuesta_envia_y_resuelve(self, _mock_twilio):
        from core.pqrs_respuesta import aplicar_respuesta_pqrs

        solicitud = SolicitudSoporte.objects.create(
            estudiante=self.est,
            mensaje_original='No puedo entrar',
            estado='pendiente',
        )
        ok, err = aplicar_respuesta_pqrs(solicitud, 'Intente de nuevo con su cédula.', user=None)
        self.assertTrue(ok)
        self.assertIsNone(err)
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, 'resuelta')
        self.assertIn('cédula', solicitud.respuesta)


class TestContextoYAccionesPQRS(TestCase):
    def setUp(self):
        from core.models import Curso, Modulo, ProgresoEstudiante

        self.est = _estudiante()
        self.est.municipio = 'Ibagué'
        self.est.save(update_fields=['municipio'])
        self.curso = Curso.objects.create(
            nombre='Curso PQRS Ctx',
            cliente=self.est.cliente,
            activo=True,
            emoji='📗',
        )
        self.mod = Modulo.objects.create(
            curso=self.curso,
            numero=2,
            titulo='Modulo dos',
            contenido='CONTENIDO_MODULO_DOS_PQRS',
        )
        self.prog = ProgresoEstudiante.objects.create(
            estudiante=self.est,
            curso=self.curso,
            modulo_actual=self.mod,
            completado=False,
        )
        self.est.contexto_temporal = {'curso_activo_id': self.curso.id}
        self.est.save(update_fields=['contexto_temporal'])

    def test_construir_contexto_incluye_curso_y_datos(self):
        from core.pqrs_agent import construir_contexto_estudiante

        ctx = construir_contexto_estudiante(self.est)
        self.assertIn('Curso PQRS Ctx', ctx)
        self.assertIn('Modulo dos', ctx)
        self.assertIn('Ibagué', ctx)
        self.assertIn(self.est.cedula, ctx)

    def test_accion_explicar_progreso(self):
        solicitud = SolicitudSoporte.objects.create(
            estudiante=self.est,
            mensaje_original='quiero ver mi progreso',
            keyword_usada='ayuda',
        )
        resultado = procesar_pqrs_automatico(solicitud)
        self.assertEqual(resultado['accion'], 'explicar_progreso')
        self.assertFalse(resultado['escalar'])
        self.assertIn('Curso PQRS Ctx', resultado['respuesta_whatsapp'])
        self.assertIn('listo', resultado['respuesta_whatsapp'].lower())
        aplicar_resultado_pqrs(solicitud, resultado)
        solicitud.refresh_from_db()
        self.assertTrue(solicitud.resuelto_por_agente)
        self.assertEqual(solicitud.estado, 'resuelta')

    def test_accion_reenviar_modulo(self):
        solicitud = SolicitudSoporte.objects.create(
            estudiante=self.est,
            mensaje_original='reenvia el modulo por favor',
            keyword_usada='ayuda',
        )
        resultado = procesar_pqrs_automatico(solicitud)
        self.assertEqual(resultado['accion'], 'reenviar_modulo')
        self.assertIn('CONTENIDO_MODULO_DOS_PQRS', resultado['respuesta_whatsapp'])
        self.assertIn('listo', resultado['respuesta_whatsapp'].lower())

    def test_accion_corregir_datos_inicia_flujo(self):
        solicitud = SolicitudSoporte.objects.create(
            estudiante=self.est,
            mensaje_original='necesito corregir mi nombre',
            keyword_usada='ayuda',
        )
        resultado = procesar_pqrs_automatico(solicitud)
        self.assertEqual(resultado['accion'], 'corregir_datos')
        self.assertIn('Correccion de datos', resultado['respuesta_whatsapp'])
        self.est.refresh_from_db()
        self.assertEqual((self.est.contexto_temporal or {}).get('tipo'), 'correccion_datos')

    def test_accion_corregir_datos_aplica_valor(self):
        from core.pqrs_acciones import ejecutar_accion_pqrs

        resultado = ejecutar_accion_pqrs(
            self.est,
            {
                'accion': 'corregir_datos',
                'campo_correccion': 'municipio',
                'valor_nuevo': 'Espinal',
                'escalar': False,
                'respuesta_whatsapp': '',
                'nota_interna': '',
                'categoria': 'acceso',
            },
        )
        self.est.refresh_from_db()
        self.assertEqual(self.est.municipio, 'Espinal')
        self.assertIn('listo', resultado['respuesta_whatsapp'].lower())
        self.assertFalse(resultado['escalar'])

    def test_escalacion_deja_pendiente(self):
        solicitud = SolicitudSoporte.objects.create(
            estudiante=self.est,
            mensaje_original='el sistema tira error 500 siempre',
            keyword_usada='ayuda',
        )
        raw = (
            '{"categoria":"tecnico","respuesta_whatsapp":"Lo pasamos al equipo.",'
            '"escalar":true,"accion":"escalar","nota_interna":"error sistema",'
            '"hacer_pregunta_clarificacion":false,"fuera_de_alcance":false,'
            '"consulta_contenido_curso":false}'
        )
        with patch('core.pqrs_agent._llamar_openai_pqrs', return_value=raw):
            with patch('core.pqrs_agent.notificar_escalacion_humana') as mock_mail:
                resultado = procesar_pqrs_automatico(solicitud)
                aplicar_resultado_pqrs(solicitud, resultado)
                if resultado.get('escalar'):
                    mock_mail(solicitud, motivo='test')
        self.assertTrue(resultado['escalar'])
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, 'pendiente')
        self.assertFalse(solicitud.resuelto_por_agente)
