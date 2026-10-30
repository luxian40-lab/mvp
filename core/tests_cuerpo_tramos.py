"""Caracterización de los tramos del cuerpo del webhook que quedan por mover (fase D).

Cada clase fija lo que hoy responde un tramo: no registrado (prospecto B2B),
intercepciones previas, migración de estado legado, prioridad global, entrada
de ACTIVO, puerta de *listo*, menú 1-4, respaldo (agente, intent, IA) y envío
común. Los colaboradores se parchean en su módulo de origen: el cuerpo los
importa dentro de la función, antes y después de mover.
"""
from __future__ import annotations

import itertools
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from core.models import Cliente, Estudiante, ProspectoB2B, WhatsappLog

TEL = '573009995555'
TEL_PROSPECTO = '573009996666'
TWILIO = dict(
    SECURE_SSL_REDIRECT=False,
    TWILIO_ACCOUNT_SID='ACtramos',
    TWILIO_AUTH_TOKEN='tok_tramos',
    TWILIO_PHONE_NUMBER='whatsapp:+573202948806',
)


@override_settings(**TWILIO)
class _Base(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            nombre='Org Tramos', contacto_principal='A', email='tramos@t.com',
            telefono='573001111555', activo=True,
        )
        self._sids = itertools.count(1)

    def _est(self, **campos):
        datos = dict(
            cedula='tramo_1', nombre='Tomas Tramo', telefono=TEL, cliente=self.cliente, activo=True,
            estado_chat='ACTIVO', estado_onboarding='completado', acepto_terminos=True, contexto_temporal={},
        )
        datos.update(campos)
        return Estudiante.objects.create(**datos)

    def _post(self, body, sid, tel=TEL, **extra):
        from core.views import _procesar_twilio_webhook

        cliente_tw = MagicMock()
        cliente_tw.messages.create.side_effect = lambda **kw: SimpleNamespace(sid=f'{sid}_out{next(self._sids)}')
        datos = {'From': f'whatsapp:+{tel}', 'To': 'whatsapp:+573202948806', 'MessageSid': sid, 'Body': body}
        datos.update(extra)
        with patch('twilio.rest.Client', return_value=cliente_tw):
            _procesar_twilio_webhook(datos)
        return cliente_tw

    @staticmethod
    def _cuerpos(cliente_tw):
        return [c.kwargs.get('body') for c in cliente_tw.messages.create.call_args_list]


class NoRegistradoTests(_Base):
    def _post_p(self, body, sid):
        return self._post(body, sid, tel=TEL_PROSPECTO)

    def test_numero_nuevo_crea_prospecto_y_manda_ventas(self):
        with patch('core.catalogo_demo_carousel.intentar_flujo_prospecto_carrusel', return_value=False), \
                patch('core.whatsapp_service.enviar_mensaje_ventas') as ventas:
            self._post_p('hola', 'SM_tr_p_nuevo')
        p = ProspectoB2B.objects.get(telefono=TEL_PROSPECTO)
        self.assertEqual((p.mensaje_original, p.origen), ('hola', 'whatsapp_bot'))
        ventas.assert_called_once_with(f'+{TEL_PROSPECTO}')

    def test_prospecto_que_elige_empresa_queda_esperando_correo(self):
        ProspectoB2B.objects.create(telefono=TEL_PROSPECTO, mensaje_original='hola', origen='whatsapp_bot')
        with patch('core.catalogo_demo_carousel.intentar_flujo_prospecto_carrusel', return_value=False):
            cli = self._post_p('1', 'SM_tr_p_empresa')
        self.assertTrue(ProspectoB2B.objects.get(telefono=TEL_PROSPECTO).esperando_email)
        self.assertEqual(len(self._cuerpos(cli)), 1)
        self.assertTrue(self._cuerpos(cli)[0].startswith('🏢 *¡Excelente!*'))

    def test_correo_valido_se_guarda_y_avisa_a_ventas(self):
        ProspectoB2B.objects.create(
            telefono=TEL_PROSPECTO, mensaje_original='hola', origen='whatsapp_bot', esperando_email=True,
        )
        with patch('core.catalogo_demo_carousel.intentar_flujo_prospecto_carrusel', return_value=False), \
                patch('django.core.mail.send_mail') as correo:
            cli = self._post_p('mi correo es juan@empresa.com', 'SM_tr_p_correo')
        p = ProspectoB2B.objects.get(telefono=TEL_PROSPECTO)
        self.assertEqual((p.email, p.esperando_email), ('juan@empresa.com', False))
        correo.assert_called_once()
        self.assertIn('Hemos registrado tu correo: *juan@empresa.com*', self._cuerpos(cli)[0])

    def test_correo_invalido_pide_otro(self):
        ProspectoB2B.objects.create(
            telefono=TEL_PROSPECTO, mensaje_original='hola', origen='whatsapp_bot', esperando_email=True,
        )
        with patch('core.catalogo_demo_carousel.intentar_flujo_prospecto_carrusel', return_value=False):
            cli = self._post_p('no tengo', 'SM_tr_p_invalido')
        self.assertEqual(
            self._cuerpos(cli), ['📧 Por favor envía un correo electrónico válido (ej: nombre@empresa.com)'],
        )


class IntercepcionesTests(_Base):
    def test_acuse_de_campana_unica_responde_y_corta(self):
        est = self._est()
        with patch(
            'core.campana_respuestas.intentar_registrar_respuesta_campana_unica',
            return_value='✅ Gracias, registramos su respuesta.',
        ):
            cli = self._post('Sí', 'SM_tr_campana')
        self.assertEqual(self._cuerpos(cli), ['✅ Gracias, registramos su respuesta.'])
        self.assertTrue(WhatsappLog.objects.filter(
            telefono=TEL, tipo='SENT', mensaje='✅ Gracias, registramos su respuesta.',
        ).exists())
        est.refresh_from_db()
        self.assertEqual(est.estado_chat, 'ACTIVO')

    def test_ubicacion_con_empleabilidad_en_pausa_y_sin_texto_no_responde(self):
        self._est()
        with patch('core.empleabilidad_pausa.empleabilidad_en_pausa', return_value=True):
            cli = self._post('', 'SM_tr_ubicacion', Latitude='4.6', Longitude='-74.1')
        cli.messages.create.assert_not_called()


class ArranqueTests(_Base):
    def _menu(self, est, sid):
        with patch('core.utils.enviar_whatsapp_twilio') as enviar:
            self._post('menu', sid)
        est.refresh_from_db()
        return enviar

    def test_sin_estado_con_terminos_y_curso_completado_pasa_a_activo(self):
        est = self._est(estado_chat='')
        self._menu(est, 'SM_tr_arr_activo')
        self.assertEqual(est.estado_chat, 'ACTIVO')

    def test_sin_estado_con_terminos_pasa_a_cedula(self):
        est = self._est(estado_chat='', estado_onboarding='nuevo')
        self._menu(est, 'SM_tr_arr_cedula')
        self.assertEqual(est.estado_chat, 'ESPERANDO_CEDULA')

    def test_sin_estado_sin_terminos_pasa_a_habeas(self):
        est = self._est(estado_chat='', acepto_terminos=False, estado_onboarding='nuevo')
        with patch('core.whatsapp_service.enviar_habeas_data', return_value=True) as habeas:
            self._post('hola', 'SM_tr_arr_habeas')
        est.refresh_from_db()
        self.assertEqual(est.estado_chat, 'ESPERANDO_HABEAS_DATA')
        habeas.assert_called_once()

    def test_habeas_con_terminos_aceptados_se_autocorrige(self):
        est = self._est(estado_chat='ESPERANDO_HABEAS_DATA')
        self._menu(est, 'SM_tr_arr_auto')
        self.assertEqual(est.estado_chat, 'ACTIVO')


class PrioridadGlobalTests(_Base):
    def test_menu_sin_cliente_manda_el_menu_principal(self):
        from core.correccion_datos import construir_menu_principal_texto

        est = self._est(cliente=None)
        with patch('core.utils.enviar_whatsapp_twilio') as enviar:
            self._post('menu', 'SM_tr_pg_menu')
        enviar.assert_called_once_with(f'+{TEL}', construir_menu_principal_texto(est))

    def test_hola_de_b2b_retoma_la_leccion(self):
        est = self._est()
        with patch('core.utils.enviar_whatsapp_twilio') as enviar, \
                patch('core.response_templates.get_response_for_intent', return_value='RETOMA') as intent:
            self._post('hola', 'SM_tr_pg_hola')
        intent.assert_called_once_with(
            'continuar_leccion', 'Tomas Tramo', estudiante_id=est.id, mensaje_original='hola',
        )
        enviar.assert_called_once_with(f'+{TEL}', 'RETOMA')

    def test_corregir_datos_abre_el_flujo_de_correccion(self):
        est = self._est()
        with patch('core.utils.enviar_whatsapp_twilio') as enviar:
            self._post('corregir datos', 'SM_tr_pg_corregir')
        est.refresh_from_db()
        self.assertEqual(est.contexto_temporal.get('tipo'), 'correccion_datos')
        self.assertTrue(enviar.call_args.args[1].startswith('✏️ *Correccion de datos*'))

    def test_en_flujo_de_correccion_sigue_el_flujo(self):
        self._est(contexto_temporal={'tipo': 'correccion_datos', 'estado': 'esperando_opcion', 'campo': ''})
        with patch('core.utils.enviar_whatsapp_twilio') as enviar, \
                patch('core.correccion_datos.procesar_flujo_correccion', return_value='PASO_CORR'):
            self._post('1', 'SM_tr_pg_flujo')
        enviar.assert_called_once_with(f'+{TEL}', 'PASO_CORR')

    def test_formulario_activo_tiene_prioridad(self):
        self._est()
        with patch('core.utils.enviar_whatsapp_twilio') as enviar, \
                patch('core.puentes.debe_usar_agente_formulario', return_value=True), \
                patch('core.puentes.manejar_mensaje_formulario', return_value='FORM'):
            self._post('mi finca tiene 3 hectareas', 'SM_tr_pg_form')
        enviar.assert_called_once_with(f'+{TEL}', 'FORM')
        self.assertTrue(WhatsappLog.objects.filter(telefono=TEL, tipo='SENT', mensaje='FORM').exists())


class EntradaActivoTests(_Base):
    def test_aula_entrega_el_acceso(self):
        self._est()
        with patch('core.puentes.mensaje_pide_acceso_aula', side_effect=lambda t: t == 'aula'), \
                patch('core.puentes.emitir_acceso_desde_whatsapp', return_value='AULA_OK'):
            cli = self._post('aula', 'SM_tr_ea_aula')
        self.assertEqual(self._cuerpos(cli), ['AULA_OK'])
        self.assertTrue(WhatsappLog.objects.filter(telefono=TEL, tipo='SENT', mensaje='AULA_OK').exists())

    def test_formulario_sin_terminos_lo_atiende_el_bloque_activo(self):
        self._est(acepto_terminos=False)
        with patch('core.puentes.debe_usar_agente_formulario', return_value=True), \
                patch('core.puentes.manejar_mensaje_formulario', return_value='FORM2'):
            cli = self._post('mi finca', 'SM_tr_ea_form')
        self.assertEqual(self._cuerpos(cli), ['FORM2'])


class PuertaListoTests(_Base):
    def test_texto_que_no_es_listo_responde_no_entendi(self):
        self._est()
        cli = self._post('que tal', 'SM_tr_pl_noent')
        cuerpos = self._cuerpos(cli)
        self.assertEqual(len(cuerpos), 1)
        self.assertTrue(cuerpos[0].startswith('No entendí. Si quiere avanzar de módulo, pulse continuar'))

    def test_audio_no_transcrito_pide_repetir(self):
        self._est()
        cli = self._post('[AUDIO_NO_TRANSCRITO]', 'SM_tr_pl_audio')
        self.assertTrue(self._cuerpos(cli)[0].startswith('⚠️ No pude escuchar tu audio.'))

    def test_reenvio_de_media_manda_las_partes(self):
        self._est()
        reenvio = '[MULTI_MSG]Aquí va el video[SEP][MEDIA:https://cdn.example.com/v.mp4]'
        with patch('core.media_recuperacion.intentar_reenvio_media_curso', return_value=reenvio), \
                patch('core.utils.enviar_whatsapp_twilio') as enviar:
            self._post('reenviame el video', 'SM_tr_pl_reenvio')
        self.assertEqual(
            [(c.args[1], c.kwargs.get('media_url')) for c in enviar.call_args_list],
            [('Aquí va el video', None), (' ', 'https://cdn.example.com/v.mp4')],
        )
        self.assertTrue(WhatsappLog.objects.filter(telefono=TEL, agente_usado='REENVIAR_MEDIA').exists())


class MenuLegadoTests(_Base):
    def test_mis_puntos_durante_un_agente_manda_gamificacion(self):
        est = self._est(estado_onboarding='esperando_respuesta_asistente')
        with patch('core.whatsapp_service.enviar_gamificacion_visual') as gami:
            self._post('mis puntos', 'SM_tr_ml_puntos')
        gami.assert_called_once()
        self.assertEqual((gami.call_args.args[0], gami.call_args.args[1].id), (f'+{TEL}', est.id))

    def test_pqrs_durante_un_agente_abre_soporte(self):
        self._est(estado_onboarding='esperando_respuesta_asistente')
        with patch('core.security_handler.procesar_solicitud_soporte', return_value='TICKET_OK') as soporte:
            cli = self._post('pqrs', 'SM_tr_ml_pqrs')
        self.assertEqual(soporte.call_args.args[1:], ('pqrs', 'menu_ayuda'))
        self.assertEqual(self._cuerpos(cli), ['TICKET_OK'])


class RespaldoTests(_Base):
    def _listo(self, sid, intent='saludo', texto='HOLA_TPL'):
        with patch('core.eventos_ia.detectar_intent_con_evento', return_value=intent), \
                patch('core.response_templates.get_response_for_intent', return_value=texto), \
                patch('time.sleep'):
            return self._post('listo', sid)

    def test_intent_conocido_usa_la_plantilla(self):
        self._est()
        cli = self._listo('SM_tr_rs_intent')
        self.assertEqual(self._cuerpos(cli), ['HOLA_TPL'])

    def test_leccion_en_curso_no_manda_nada(self):
        from core.response_templates import LECCION_EN_CURSO

        self._est()
        with patch('core.sandbox_canal.descartar_reaccion_espera') as descartar:
            cli = self._listo('SM_tr_rs_leccion', texto=LECCION_EN_CURSO)
        cli.messages.create.assert_not_called()
        descartar.assert_called_once_with(TEL)

    def test_intent_corregir_datos_pasa_a_correccion_legado(self):
        est = self._est()
        cli = self._listo('SM_tr_rs_corregir', intent='corregir_datos')
        est.refresh_from_db()
        self.assertEqual(est.estado_chat, 'ESPERANDO_CORRECCION_DATOS')
        self.assertTrue(self._cuerpos(cli)[0].startswith('📝 *Corrección de Datos*'))

    def test_sin_intent_y_sin_preguntas_frena_la_ia(self):
        self._est(preguntas_ia_restantes=0)
        cli = self._listo('SM_tr_rs_sinpreg', intent='desconocido')
        self.assertTrue(
            self._cuerpos(cli)[0].startswith('⚠️ *Has agotado tus preguntas libres a la IA para este modulo.*')
        )

    def test_sin_intent_responde_la_ia_y_descuenta_una_pregunta(self):
        est = self._est(preguntas_ia_restantes=2)
        with patch('core.ai_assistant.responder_con_ia', return_value='IA_RESP') as ia, \
                patch('core.sandbox_canal.poner_reaccion_espera'):
            cli = self._listo('SM_tr_rs_ia', intent='desconocido')
        ia.assert_called_once_with('listo', TEL)
        self.assertEqual(self._cuerpos(cli), ['IA_RESP'])
        est.refresh_from_db()
        self.assertEqual(est.preguntas_ia_restantes, 1)

    def test_contexto_de_dario_resincroniza_el_estado(self):
        from core.conversacion.contexto import Respuesta

        est = self._est(contexto_temporal={'tipo': 'asistente_dario'})
        vistos = []

        def agente_de(estado):
            vistos.append(estado)
            return lambda ctx: Respuesta(texto='DARIO')

        with patch('core.conversacion.estados.despacho.agente_de', side_effect=agente_de):
            cli = self._post('listo', 'SM_tr_rs_dario')
        est.refresh_from_db()
        self.assertEqual(est.estado_onboarding, 'esperando_respuesta_asistente')
        self.assertEqual(vistos, ['esperando_respuesta_asistente'])
        self.assertEqual(self._cuerpos(cli), ['DARIO'])


class EnvioComunTests(_Base):
    def _enviar(self, texto, sid):
        self._est()
        with patch('core.eventos_ia.detectar_intent_con_evento', return_value='saludo'), \
                patch('core.response_templates.get_response_for_intent', return_value=texto), \
                patch('time.sleep') as dormir, \
                patch('core.whatsapp_service.enviar_template_twilio') as plantilla:
            cli = self._post('listo', sid)
        return cli, dormir, plantilla

    def test_multi_mensaje_con_pausa_y_media(self):
        cli, dormir, _ = self._enviar(
            '[MULTI_MSG]Uno[SEP][DELAY:2][SEP]Dos[MEDIA:https://cdn.example.com/a.jpg]', 'SM_tr_en_multi',
        )
        self.assertEqual(self._cuerpos(cli), ['Uno', 'Dos'])
        self.assertIn('https://cdn.example.com/a.jpg', str(cli.messages.create.call_args_list[1].kwargs))
        self.assertIn(2, [c.args[0] for c in dormir.call_args_list])
        enviados = list(
            WhatsappLog.objects.filter(telefono=TEL, tipo='SENT').order_by('id').values_list('mensaje', flat=True)
        )
        self.assertEqual(enviados, ['Uno', 'Dos\n[MEDIA:https://cdn.example.com/a.jpg]'])

    def test_media_simple(self):
        cli, _, _ = self._enviar('Hola[MEDIA:https://cdn.example.com/b.jpg]', 'SM_tr_en_media')
        self.assertEqual(self._cuerpos(cli), ['Hola'])
        self.assertIn('https://cdn.example.com/b.jpg', str(cli.messages.create.call_args.kwargs))

    def test_plantilla_sola(self):
        cli, _, plantilla = self._enviar('[SEND_TEMPLATE:HXabc123]', 'SM_tr_en_tpl')
        plantilla.assert_called_once_with(TEL, 'HXabc123')
        cli.messages.create.assert_not_called()

    def test_plantilla_dentro_de_multi_mensaje(self):
        cli, _, plantilla = self._enviar('[MULTI_MSG]Antes[SEP][SEND_TEMPLATE:HXdef456]', 'SM_tr_en_tplmulti')
        self.assertEqual(self._cuerpos(cli), ['Antes'])
        plantilla.assert_called_once_with(TEL, 'HXdef456')
