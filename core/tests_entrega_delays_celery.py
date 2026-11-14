"""G3: [DELAY:N] con flag off duerme; con flag on encola countdown."""
from unittest.mock import patch

from django.test import TestCase, override_settings

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
