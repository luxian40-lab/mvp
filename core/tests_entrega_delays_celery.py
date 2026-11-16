"""G3: [DELAY:N] con flag off duerme; con flag on encola countdown."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase, override_settings

from core.conversacion.marcas import TEXTO, partes
from core.lineas.entrega_delays import recorrer_partes
from core.lineas.envio import enviar_meta

TEL = '573001110051'


@override_settings(WHATSAPP_TOKEN='tok', WHATSAPP_PHONE_ID='100000000000001', META_LINEAS='')
class EntregaDelaysFlagOffTests(TestCase):
    def setUp(self):
        self.enviados = []

        def graph(payload, agente=''):
            self.enviados.append(payload)
            return {'success': True, 'mensaje_id': f'wamid.{len(self.enviados)}', 'response': ''}

        self.graph = patch('core.lineas.envio._post_graph', side_effect=graph).start()
        self.pausas = patch('core.lineas.entrega_delays.time.sleep').start()
        self.encolar = patch('core.lineas.entrega_delays.encolar_continuacion').start()
        self.addCleanup(patch.stopall)

    def test_delay_sigue_durmiendo_con_flag_apagado(self):
        enviar_meta(TEL, '[MULTI_MSG]Uno[SEP][DELAY:3][SEP]Dos')
        self.assertEqual(
            [p.get('text', {}).get('body') for p in self.enviados],
            ['Uno', 'Dos'],
        )
        self.pausas.assert_any_call(3.0)
        self.encolar.assert_not_called()


@override_settings(
    WHATSAPP_TOKEN='tok',
    WHATSAPP_PHONE_ID='100000000000001',
    META_LINEAS='',
    EKI_ENTREGA_DELAYS_CELERY=True,
)
class EntregaDelaysFlagOnTests(TestCase):
    def setUp(self):
        self.enviados = []

        def graph(payload, agente=''):
            self.enviados.append(payload)
            return {'success': True, 'mensaje_id': f'wamid.{len(self.enviados)}', 'response': ''}

        self.graph = patch('core.lineas.envio._post_graph', side_effect=graph).start()
        self.sleep = patch('core.lineas.entrega_delays.time.sleep').start()
        self.encolar = patch('core.lineas.entrega_delays.encolar_continuacion').start()
        self.addCleanup(patch.stopall)

    def test_delay_encola_y_no_manda_la_segunda_parte_aun(self):
        enviar_meta(TEL, '[MULTI_MSG]Uno[SEP][DELAY:3][SEP]Dos')
        self.assertEqual(
            [p.get('text', {}).get('body') for p in self.enviados],
            ['Uno'],
        )
        self.encolar.assert_called_once()
        kwargs = self.encolar.call_args.kwargs
        self.assertEqual(kwargs['countdown'], 3)
        self.assertEqual(kwargs['canal'], 'meta')
        self.assertEqual(kwargs['payload']['desde_idx'], 2)
        self.assertFalse(any(c.args and c.args[0] == 3.0 for c in self.sleep.call_args_list))


class RecorrerPartesTests(TestCase):
    def test_desde_idx_salta_lo_ya_enviado(self):
        vistos = []

        def on_parte(parte):
            vistos.append(parte.texto)
            return True

        texto = '[MULTI_MSG]Uno[SEP][DELAY:3][SEP]Dos'
        self.assertEqual([p.tipo for p in partes(texto)], ['texto', 'pausa', 'texto'])
        with patch('core.lineas.entrega_delays.time.sleep'):
            resultado = recorrer_partes(
                texto,
                desde_idx=2,
                on_parte=on_parte,
                canal='meta',
                payload_continuacion={'to': TEL},
            )
        self.assertEqual(resultado, 'done')
        self.assertEqual(vistos, ['Dos'])
        self.assertEqual(partes(texto)[2].tipo, TEXTO)

    def test_flag_apagado_por_defecto(self):
        from django.conf import settings

        self.assertFalse(settings.EKI_ENTREGA_DELAYS_CELERY)


class PausaLoteAvisosTests(SimpleTestCase):
    def test_flag_apagado_duerme_y_no_encola(self):
        from core.lineas.entrega_delays import pausar_lote

        with patch('core.lineas.entrega_delays.time.sleep') as dormir, \
                patch('core.lineas.entrega_delays.encolar_tarea') as encolar:
            self.assertFalse(
                pausar_lote(0.35, tarea='core.avisos.tareas.aviso_modulo_disponible'),
            )
        dormir.assert_called_once_with(0.35)
        encolar.assert_not_called()

    @override_settings(EKI_ENTREGA_DELAYS_CELERY=True)
    def test_flag_prendido_encola_y_pide_cortar(self):
        from core.lineas.entrega_delays import pausar_lote

        with patch('core.lineas.entrega_delays.time.sleep') as dormir, \
                patch('core.lineas.entrega_delays.encolar_tarea') as encolar:
            self.assertTrue(
                pausar_lote(0.35, tarea='core.avisos.tareas.aviso_modulo_disponible'),
            )
        encolar.assert_called_once_with(
            'core.avisos.tareas.aviso_modulo_disponible',
            0.35,
        )
        self.assertFalse(any(c.args and c.args[0] == 0.35 for c in dormir.call_args_list))

    def test_sin_pausa_no_duerme_ni_encola(self):
        from core.lineas.entrega_delays import pausar_lote

        with patch('core.lineas.entrega_delays.time.sleep') as dormir, \
                patch('core.lineas.entrega_delays.encolar_tarea') as encolar:
            self.assertFalse(pausar_lote(0, tarea='core.avisos.tareas.recordatorio_curso'))
        dormir.assert_not_called()
        encolar.assert_not_called()


@override_settings(
    TWILIO_ACCOUNT_SID='ACdelay',
    TWILIO_AUTH_TOKEN='tok',
    TWILIO_PHONE_NUMBER='whatsapp:+573202948806',
    EKI_ENTREGA_DELAYS_CELERY=True,
)
class DelayMenuPuertaFlagOnTests(TestCase):
    def setUp(self):
        self.enviados = []
        cliente = MagicMock()

        def create(**kw):
            self.enviados.append(kw)
            return SimpleNamespace(sid=f'SM{len(self.enviados)}')

        cliente.messages.create.side_effect = create
        patch('twilio.rest.Client', return_value=cliente).start()
        self.sleep = patch('core.lineas.entrega_delays.time.sleep').start()
        self.encolar = patch('core.lineas.entrega_delays.encolar_continuacion').start()
        self.addCleanup(patch.stopall)

    def test_envio_comun_encola_y_no_manda_la_segunda(self):
        from core.conversacion.estados.envio_comun import _enviar_partes_multimsg

        _enviar_partes_multimsg(
            MagicMock(),
            'whatsapp:+573202948806',
            f'whatsapp:+{TEL}',
            f'+{TEL}',
            TEL,
            '[MULTI_MSG]Uno[SEP][DELAY:3][SEP]Dos',
        )
        self.assertEqual([e.get('body') for e in self.enviados], ['Uno'])
        self.encolar.assert_called_once()
        self.assertEqual(self.encolar.call_args.kwargs['canal'], 'twilio_marcado')
        self.assertFalse(any(c.args and c.args[0] == 3.0 for c in self.sleep.call_args_list))

    def test_reenvio_menu_encola_y_no_manda_la_segunda(self):
        from core.conversacion.estados.activo_menu import _enviar_reenvio_menu

        _enviar_reenvio_menu(f'+{TEL}', TEL, '[MULTI_MSG]Uno[SEP][DELAY:3][SEP]Dos')
        self.assertEqual([e.get('body') for e in self.enviados], ['Uno'])
        self.encolar.assert_called_once()
        self.assertEqual(self.encolar.call_args.kwargs['canal'], 'twilio_marcado')
        self.assertFalse(any(c.args and c.args[0] == 3.0 for c in self.sleep.call_args_list))
