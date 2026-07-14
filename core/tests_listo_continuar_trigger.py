"""Regresión: *listo* y *continuar* deben comportarse igual en todo el flujo del curso."""
import sys
import time
from types import ModuleType
from unittest.mock import MagicMock, patch

from django.test import TestCase

from core.intent_detector import mensaje_indica_listo
from core.models import (
    Curso,
    Estudiante,
    Modulo,
    ModuloCompletado,
    PasoModulo,
    ProgresoEstudiante,
    SeccionModulo,
)
from core.response_templates import _es_mensaje_listo_avance_curso, get_response_for_intent

TRIGGERS_VALIDOS = ('listo', 'continuar', '*listo*', '*continuar*', 'ok continuar', 'ya listo')
TRIGGERS_INVALIDOS = (
    'ya terminé el material y quiero continuar con el curso paso a paso',
    'hola qué tal',
)


def _install_twilio_rest_stub(client_class):
    root = sys.modules.get('twilio') or ModuleType('twilio')
    rest = sys.modules.get('twilio.rest') or ModuleType('twilio.rest')
    rest.Client = client_class
    sys.modules.setdefault('twilio', root)
    sys.modules['twilio.rest'] = rest


def _twilio_client_patch(client_class):
    try:
        import twilio.rest  # noqa: F401

        return patch('twilio.rest.Client', client_class)
    except ImportError:
        _install_twilio_rest_stub(client_class)
        return patch('twilio.rest.Client', client_class)


class ListoContinuarMismoCriterioTests(TestCase):
    def test_avance_curso_usa_misma_regla_que_gate(self):
        for msg in TRIGGERS_VALIDOS:
            with self.subTest(msg=msg):
                self.assertTrue(mensaje_indica_listo(msg))
                self.assertEqual(_es_mensaje_listo_avance_curso(msg), mensaje_indica_listo(msg))

    def test_prosa_larga_no_dispara_avance(self):
        for msg in TRIGGERS_INVALIDOS:
            with self.subTest(msg=msg):
                self.assertFalse(mensaje_indica_listo(msg))
                self.assertFalse(_es_mensaje_listo_avance_curso(msg))


class PostRetoListoContinuarParidadTests(TestCase):
    """Tras facilitadora: primer trigger entrega módulo; el segundo cierra y avanza."""

    def _setup_post_reto(self, sufijo):
        estudiante = Estudiante.objects.create(
            cedula=f'100088{sufijo}',
            nombre=f'Est Paridad {sufijo}',
            telefono=f'5730088776{sufijo}',
            acepto_terminos=True,
            estado_chat='ACTIVO',
            estado_onboarding='completado',
        )
        curso = Curso.objects.create(
            nombre=f'Curso paridad {sufijo}',
            dias_espera_entre_modulos=0,
        )
        mods = [
            Modulo.objects.create(
                curso=curso,
                numero=n,
                titulo=f'M{n}',
                descripcion='D',
                contenido=f'CONTENIDO_MOD_{n}_{sufijo}',
            )
            for n in range(1, 4)
        ]
        m1, m2, m3 = mods
        progreso = ProgresoEstudiante.objects.create(
            estudiante=estudiante,
            curso=curso,
            modulo_actual=m2,
            completado=False,
        )
        ModuloCompletado.objects.create(progreso=progreso, modulo=m1)
        estudiante.contexto_temporal = {
            'post_reto_entregar_modulo_id': m2.id,
            'curso_activo_id': curso.id,
        }
        estudiante.save()
        return estudiante, progreso, m2, m3

    def _continuar_leccion(self, estudiante, trigger):
        return get_response_for_intent(
            'continuar_leccion',
            estudiante.nombre,
            estudiante_id=estudiante.id,
            mensaje_original=trigger,
        )

    def test_primer_trigger_entrega_modulo_sin_cerrarlo(self):
        for idx, trigger in enumerate(('listo', 'continuar')):
            with self.subTest(trigger=trigger):
                estudiante, progreso, m2, _m3 = self._setup_post_reto(f'1{idx}')
                respuesta = self._continuar_leccion(estudiante, trigger)
                self.assertIn(f'CONTENIDO_MOD_2_1{idx}', respuesta)
                progreso.refresh_from_db()
                self.assertEqual(progreso.modulo_actual_id, m2.id)
                self.assertFalse(
                    ModuloCompletado.objects.filter(progreso=progreso, modulo=m2).exists()
                )

    def test_segundo_trigger_cierra_modulo_y_avanza(self):
        for idx, trigger in enumerate(('listo', 'continuar')):
            with self.subTest(trigger=trigger):
                estudiante, progreso, m2, m3 = self._setup_post_reto(f'2{idx}')
                self._continuar_leccion(estudiante, trigger)
                estudiante.refresh_from_db()
                ctx = dict(estudiante.contexto_temporal or {})
                ctx['_ts_leccion'] = time.time() - 60
                estudiante.contexto_temporal = ctx
                estudiante.save(update_fields=['contexto_temporal'])
                self._continuar_leccion(estudiante, trigger)
                progreso.refresh_from_db()
                self.assertEqual(progreso.modulo_actual_id, m3.id)
                self.assertTrue(
                    ModuloCompletado.objects.filter(progreso=progreso, modulo=m2).exists()
                )

    def test_primer_listo_post_reto_con_micros_entrega_no_recordatorio(self):
        """Regresión prod: tras facilitadora no debe mandar 'Sigues en este material'."""
        estudiante, progreso, m2, _m3 = self._setup_post_reto('micros')
        sec = SeccionModulo.objects.create(modulo=m2, orden=1, titulo='Sec post')
        PasoModulo.objects.create(
            modulo=m2,
            seccion=sec,
            orden=1,
            titulo='Micro post',
            contenido='TEXTO_MICRO_POST_RETO',
            tipo=PasoModulo.TIPO_CONTENIDO,
        )
        progreso.paso_actual_modulo = 1
        progreso.save(update_fields=['paso_actual_modulo'])

        respuesta = self._continuar_leccion(estudiante, 'listo')
        self.assertIn('TEXTO_MICRO_POST_RETO', respuesta)
        self.assertNotIn('Sigues en este material', respuesta)
        estudiante.refresh_from_db()
        self.assertNotIn(
            'post_reto_entregar_modulo_id',
            estudiante.contexto_temporal or {},
        )
        progreso.refresh_from_db()
        self.assertEqual(progreso.modulo_actual_id, m2.id)
        self.assertFalse(
            ModuloCompletado.objects.filter(progreso=progreso, modulo=m2).exists()
        )


class DaríoHandoffContinuarTests(TestCase):
    """Con Darío activo, *continuar* debe pasar a facilitadora igual que *listo*."""

    def setUp(self):
        self.est = Estudiante.objects.create(
            cedula='10006655',
            nombre='Darío Handoff',
            telefono='573006655443',
            acepto_terminos=True,
            estado_chat='ACTIVO',
            estado_onboarding='esperando_respuesta_asistente',
        )
        self.curso = Curso.objects.create(
            nombre='Curso Darío',
            dias_espera_entre_modulos=0,
            usar_agentes_ia=True,
        )
        self.mod = Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='M1',
            descripcion='D',
            contenido='C',
        )
        self.prog = ProgresoEstudiante.objects.create(
            estudiante=self.est,
            curso=self.curso,
            modulo_actual=self.mod,
        )

    def _ctx_dario(self):
        return {
            'tipo': 'asistente_dario',
            'progreso_id': self.prog.id,
            'modulos_reto_ids': [self.mod.id],
            'preguntas_hechas': 0,
        }

    @patch('core.tutor_ia_modulo.generar_reto_facilitador', return_value='Reto de prueba')
    @patch('core.tutor_ia_modulo.cargar_modulos_reto')
    def test_continuar_activa_facilitadora_como_listo(self, mock_cargar, _mock_reto):
        mock_cargar.return_value = [self.mod]
        from core.views import _procesar_twilio_webhook

        for trigger in ('listo', 'continuar'):
            with self.subTest(trigger=trigger):
                self.est.estado_onboarding = 'esperando_respuesta_asistente'
                self.est.contexto_temporal = self._ctx_dario()
                self.est.save()

                mock_instance = MagicMock()
                sent_msg = MagicMock(sid=f'SM_dario_{trigger}')
                mock_instance.messages.create.return_value = sent_msg
                FakeTwilioClient = MagicMock(return_value=mock_instance)

                with _twilio_client_patch(FakeTwilioClient):
                    _procesar_twilio_webhook(
                        {
                            'Body': trigger,
                            'From': 'whatsapp:+573006655443',
                            'To': 'whatsapp:+14155238886',
                            'MessageSid': f'SM_dario_{trigger}',
                            'NumMedia': '0',
                        }
                    )

                self.est.refresh_from_db()
                self.assertEqual(self.est.estado_onboarding, 'esperando_respuesta_reto')
                bodies = [
                    c.kwargs.get('body', '') for c in mock_instance.messages.create.call_args_list
                ]
                texto = ' '.join(bodies)
                self.assertIn('Reto de prueba', texto)
                self.assertNotIn('No entendí', texto)


class FacilitadoraNoSaltaConListoTests(TestCase):
    """Regresión prod: listo no debe forzar completado ni saltar la facilitadora."""

    def setUp(self):
        self.est = Estudiante.objects.create(
            cedula='10007766',
            nombre='Facil Gate',
            telefono='573007766554',
            acepto_terminos=True,
            estado_chat='ACTIVO',
            estado_onboarding='esperando_respuesta_reto',
        )
        self.curso = Curso.objects.create(
            nombre='Curso Facil',
            dias_espera_entre_modulos=0,
            usar_agentes_ia=True,
        )
        self.mod = Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='M1',
            descripcion='D',
            contenido='C',
        )
        self.prog = ProgresoEstudiante.objects.create(
            estudiante=self.est,
            curso=self.curso,
            modulo_actual=self.mod,
        )
        self.est.contexto_temporal = {
            'tipo': 'reto_facilitador',
            'reto_texto': '¿Qué haría usted?',
            'modulos_reto_ids': [self.mod.id],
            'progreso_id': self.prog.id,
            'es_final': False,
        }
        self.est.save(update_fields=['contexto_temporal'])

    def test_listo_durante_reto_no_avanza_ni_evalua(self):
        from core.views import _procesar_twilio_webhook

        mock_instance = MagicMock()
        mock_instance.messages.create.return_value = MagicMock(sid='SM_facil_listo')
        FakeTwilioClient = MagicMock(return_value=mock_instance)

        with _twilio_client_patch(FakeTwilioClient):
            _procesar_twilio_webhook(
                {
                    'Body': 'listo',
                    'From': 'whatsapp:+573007766554',
                    'To': 'whatsapp:+14155238886',
                    'MessageSid': 'SM_facil_listo',
                    'NumMedia': '0',
                }
            )

        self.est.refresh_from_db()
        self.assertEqual(self.est.estado_onboarding, 'esperando_respuesta_reto')
        bodies = [c.kwargs.get('body', '') for c in mock_instance.messages.create.call_args_list]
        texto = ' '.join(bodies)
        self.assertIn('texto o audio', texto.lower())
        self.assertNotIn('módulo se está cargando', texto.lower())
        self.assertNotIn('Combinar redes', texto)

    @patch('core.tutor_ia_modulo.evaluar_reto_facilitador', return_value=(8, 'Buen enfoque en autocuidado.'))
    def test_respuesta_real_evalua_facilitadora(self, _mock_eval):
        from core.views import _procesar_twilio_webhook

        mock_instance = MagicMock()
        mock_instance.messages.create.return_value = MagicMock(sid='SM_facil_ans')
        FakeTwilioClient = MagicMock(return_value=mock_instance)

        with _twilio_client_patch(FakeTwilioClient):
            _procesar_twilio_webhook(
                {
                    'Body': 'Practicaría hablarme con cariño y limitar comparaciones en redes.',
                    'From': 'whatsapp:+573007766554',
                    'To': 'whatsapp:+14155238886',
                    'MessageSid': 'SM_facil_ans',
                    'NumMedia': '0',
                }
            )

        self.est.refresh_from_db()
        self.assertEqual(self.est.estado_onboarding, 'completado')
        bodies = [c.kwargs.get('body', '') for c in mock_instance.messages.create.call_args_list]
        texto = ' '.join(bodies)
        self.assertIn('Buen enfoque', texto)

