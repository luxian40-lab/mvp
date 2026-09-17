"""P0 Impulso: examen de módulo sin pregunta no puede tragar *listo*."""
from unittest.mock import MagicMock, patch

from django.test import TestCase

from core.models import (
    Cliente,
    Curso,
    Estudiante,
    Modulo,
    PasoModulo,
    PreguntaModulo,
    ProgresoEstudiante,
    SeccionModulo,
    WhatsappLog,
)
from core.pregunta_handler import (
    examen_modulo_sin_pregunta_pendiente,
    recuperar_examen_modulo_vacio,
)


def _twilio_ok():
    mock_instance = MagicMock()
    mock_instance.messages.create.return_value = MagicMock(sid='SM_exam_vacio')
    return MagicMock(return_value=mock_instance)


class ExamenModuloVacioTests(TestCase):
    def setUp(self):
        self.cli = Cliente.objects.create(nombre='Zoraida QA', activo=True)
        self.curso = Curso.objects.create(
            nombre='Impulso QA',
            cliente=self.cli,
            activo=True,
            usar_agentes_ia=True,
            dias_espera_entre_modulos=0,
        )
        self.est = Estudiante.objects.create(
            cedula='QA-EX-001',
            nombre='Tatiana QA',
            telefono='573223030001',
            cliente=self.cli,
            activo=True,
            acepto_terminos=True,
            estado_chat='ACTIVO',
            estado_onboarding='esperando_respuesta_modulo',
            contexto_temporal={'_ts_leccion': 1.0, 'curso_activo_id': None},
        )
        self.mod = Modulo.objects.create(
            curso=self.curso,
            numero=6,
            titulo='De negocios a ventas',
            descripcion='d',
            contenido='Contenido M6',
            publicado_wa=True,
            modo_entrega=Modulo.MODO_ENTREGA_PASOS,
        )
        sec = SeccionModulo.objects.create(modulo=self.mod, orden=1, titulo='S1')
        PasoModulo.objects.create(
            modulo=self.mod,
            seccion=sec,
            orden=1,
            titulo='Intro',
            contenido='Material real del módulo seis',
            activo=True,
        )
        self.prog = ProgresoEstudiante.objects.create(
            estudiante=self.est,
            curso=self.curso,
            modulo_actual=self.mod,
            paso_actual_modulo=1,
        )

    def _webhook(self, body):
        from core.views import _procesar_twilio_webhook

        with patch('builtins.print'), patch('twilio.rest.Client', _twilio_ok()):
            _procesar_twilio_webhook(
                {
                    'Body': body,
                    'From': f'whatsapp:+{self.est.telefono}',
                    'To': 'whatsapp:+14155238886',
                    'MessageSid': 'SM_exam_vacio_listo',
                    'NumMedia': '0',
                }
            )

    def test_helper_detecta_examen_sin_pregunta(self):
        self.assertTrue(examen_modulo_sin_pregunta_pendiente(self.est))
        self.est.contexto_temporal = {
            'tipo': 'pregunta_modulo',
            'modulo_id': self.mod.id,
            'pregunta_id': 99,
            'progreso_id': self.prog.id,
        }
        self.assertFalse(examen_modulo_sin_pregunta_pendiente(self.est))

    def test_recuperar_deja_completado_sin_ts_leccion(self):
        recuperar_examen_modulo_vacio(self.est)
        self.est.refresh_from_db()
        self.assertEqual(self.est.estado_onboarding, 'completado')
        ctx = self.est.contexto_temporal or {}
        self.assertNotIn('_ts_leccion', ctx)

    def test_listo_sin_pregunta_entrega_modulo_no_no_entendi(self):
        self._webhook('Listo')
        self.est.refresh_from_db()
        cuerpos = ' '.join(
            WhatsappLog.objects.filter(
                telefono__endswith=self.est.telefono[-10:]
            ).values_list('mensaje', flat=True)
        )
        self.assertNotIn('No entendí', cuerpos)
        self.assertIn('Material real del módulo seis', cuerpos)
        self.assertNotEqual(self.est.estado_onboarding, 'esperando_respuesta_modulo')

    def test_texto_libre_sin_pregunta_desatasca_y_pide_listo(self):
        self._webhook('buenas tardes')
        self.est.refresh_from_db()
        self.assertEqual(self.est.estado_onboarding, 'completado')
        cuerpos = ' '.join(
            WhatsappLog.objects.filter(
                telefono__endswith=self.est.telefono[-10:]
            ).values_list('mensaje', flat=True)
        )
        self.assertNotIn('No entendí', cuerpos)
        self.assertIn('listo', cuerpos.lower())

    def test_examen_real_listo_no_avanza_como_leccion(self):
        pregunta = PreguntaModulo.objects.create(
            modulo=self.mod,
            pregunta='¿Qué es una venta?',
            opcion_a='Intercambio',
            opcion_b='Nada',
            respuesta_correcta='A',
        )
        self.est.contexto_temporal = {
            'tipo': 'pregunta_modulo',
            'modulo_id': self.mod.id,
            'pregunta_id': pregunta.id,
            'progreso_id': self.prog.id,
        }
        self.est.estado_onboarding = 'esperando_respuesta_modulo'
        self.est.save(update_fields=['contexto_temporal', 'estado_onboarding'])
        self._webhook('Listo')
        cuerpos = ' '.join(
            WhatsappLog.objects.filter(
                telefono__endswith=self.est.telefono[-10:]
            ).values_list('mensaje', flat=True)
        )
        self.assertNotIn('No entendí', cuerpos)
        self.assertIn('Opción inválida', cuerpos)
        self.est.refresh_from_db()
        self.assertEqual(self.est.estado_onboarding, 'esperando_respuesta_modulo')

    def test_continuar_sin_pregunta_tambien_entrega(self):
        self._webhook('continuar')
        cuerpos = ' '.join(
            WhatsappLog.objects.filter(
                telefono__endswith=self.est.telefono[-10:]
            ).values_list('mensaje', flat=True)
        )
        self.assertNotIn('No entendí', cuerpos)
        self.assertIn('Material real del módulo seis', cuerpos)


class MediaNoAptaYPasosVaciosTests(TestCase):
    def setUp(self):
        self.cli = Cliente.objects.create(nombre='QA media', activo=True)
        self.curso = Curso.objects.create(nombre='C media', cliente=self.cli, activo=True)
        self.mod = Modulo.objects.create(
            curso=self.curso,
            numero=8,
            titulo='Finanzas',
            descripcion='d',
            contenido='c',
            publicado_wa=True,
            modo_entrega=Modulo.MODO_ENTREGA_PASOS,
        )
        self.sec = SeccionModulo.objects.create(modulo=self.mod, orden=1, titulo='S1')

    def test_media_no_apta_no_pone_url_en_whatsapp(self):
        from core.module_steps import partes_mensaje_paso

        paso = PasoModulo.objects.create(
            modulo=self.mod,
            seccion=self.sec,
            orden=1,
            titulo='clip',
            contenido='Lea este resumen de finanzas rurales',
            media_url='https://eki-produccion.s3.us-east-2.amazonaws.com/media/malo.mp4',
            media_wa_apto=False,
            activo=True,
        )
        partes = partes_mensaje_paso(paso, self.curso)
        blob = ' '.join(partes)
        self.assertNotIn('[MEDIA:', blob)
        self.assertNotIn('malo.mp4', blob)
        self.assertIn('finanzas rurales', blob)

    def test_lote_salta_pasos_sin_texto_ni_media(self):
        from core.module_steps import entregar_bloque_secciones_desde_paso

        PasoModulo.objects.create(
            modulo=self.mod, seccion=self.sec, orden=1, contenido='Primera idea útil', activo=True,
        )
        PasoModulo.objects.create(
            modulo=self.mod, seccion=self.sec, orden=2, contenido='', activo=True,
        )
        PasoModulo.objects.create(
            modulo=self.mod, seccion=self.sec, orden=3, contenido='', activo=True,
        )
        PasoModulo.objects.create(
            modulo=self.mod, seccion=self.sec, orden=4, contenido='Cierre del bloque', activo=True,
        )
        est = Estudiante.objects.create(
            cedula='QA-M5-001',
            nombre='Yuli QA',
            telefono='573144340002',
            cliente=self.cli,
            activo=True,
            acepto_terminos=True,
            estado_chat='ACTIVO',
            estado_onboarding='completado',
        )
        prog = ProgresoEstudiante.objects.create(
            estudiante=est, curso=self.curso, modulo_actual=self.mod, paso_actual_modulo=1,
        )
        msg = entregar_bloque_secciones_desde_paso(prog, self.mod, 1)
        self.assertIn('Primera idea útil', msg)
        self.assertIn('Cierre del bloque', msg)
