"""Caracterización mínima de envio_comun antes de partir helpers (H4)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from core.conversacion.contexto import Contexto
from core.models import Cliente, Estudiante, WhatsappLog

TEL = '573009997111'
TWILIO = dict(
    TWILIO_ACCOUNT_SID='ACenvio_comun',
    TWILIO_AUTH_TOKEN='tok_envio_comun',
    TWILIO_PHONE_NUMBER='whatsapp:+573202948806',
)


@override_settings(**TWILIO)
class EnvioComunCaracterizacionTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(nombre='Org envio comun', activo=True)
        self.est = Estudiante.objects.create(
            cedula='ec_1',
            nombre='Envio Comun',
            telefono=TEL,
            cliente=self.cliente,
            activo=True,
            estado_chat='ACTIVO',
            estado_onboarding='completado',
            acepto_terminos=True,
        )

    def _ctx(self, texto: str, msg_from: str | None = None) -> Contexto:
        origen = msg_from or f'whatsapp:+{TEL}'
        return Contexto(
            self.est,
            None,
            origen,
            TEL,
            texto_respuesta=texto,
        )

    def test_sin_credenciales_twilio_no_registra_log(self):
        from core.conversacion.estados import envio_comun

        with override_settings(TWILIO_ACCOUNT_SID='', TWILIO_AUTH_TOKEN=''), \
                patch('core.views.twilio_transporte.turno_sale_por_meta', return_value=False):
            envio_comun.enviar(self._ctx('Hola plano'))
        self.assertFalse(WhatsappLog.objects.filter(telefono=TEL, tipo='SENT').exists())

    def test_mensaje_simple_crea_whatsapp_log(self):
        from core.conversacion.estados import envio_comun

        mensaje = SimpleNamespace(sid='SM_ec_simple')
        with patch('core.views.twilio_transporte.turno_sale_por_meta', return_value=False), \
                patch('twilio.rest.Client') as cli_cls, \
                patch(
                    'core.conversacion.estados.envio_comun._enviar_mensaje_twilio_segmentado',
                    return_value=[(mensaje, 'Hola plano')],
                ) as segmentar:
            cli_cls.return_value = MagicMock()
            envio_comun.enviar(self._ctx('Hola plano'))
        segmentar.assert_called_once()
        self.assertEqual(
            list(WhatsappLog.objects.filter(telefono=TEL, tipo='SENT').values_list('mensaje', flat=True)),
            ['Hola plano'],
        )

    def test_plantilla_sola_llama_twilio_content_sin_segmentar(self):
        from core.conversacion.estados import envio_comun

        with patch('core.views.twilio_transporte.turno_sale_por_meta', return_value=False), \
                patch('twilio.rest.Client') as cli_cls, \
                patch('core.canal.whatsapp_service.enviar_template_twilio') as plantilla, \
                patch(
                    'core.conversacion.estados.envio_comun._enviar_mensaje_twilio_segmentado',
                ) as segmentar:
            cli_cls.return_value = MagicMock()
            envio_comun.enviar(self._ctx('[SEND_TEMPLATE:HXdeadbeef]'))
        plantilla.assert_called_once_with(TEL, 'HXdeadbeef')
        segmentar.assert_not_called()

    def test_multi_mensaje_delega_en_enviar_marcado(self):
        from core.conversacion.estados import envio_comun

        texto = '[MULTI_MSG]Uno[SEP]Dos'
        with patch('core.views.twilio_transporte.turno_sale_por_meta', return_value=False), \
                patch('twilio.rest.Client') as cli_cls, \
                patch('core.lineas.entrega.enviar_marcado') as marcado:
            cli_cls.return_value = MagicMock()
            envio_comun.enviar(self._ctx(texto))
        marcado.assert_called_once_with(
            f'whatsapp:+{TEL}', TEL, texto, registro='segmentos',
        )

    @override_settings(EKI_TURNO_META=True)
    def test_turno_meta_mensaje_simple_usa_salida_turno(self):
        from core.conversacion.estados import envio_comun

        with patch('core.views.twilio_transporte.turno_sale_por_meta', return_value=True), \
                patch('core.lineas.salida_turno.enviar_respuesta_turno') as turno, \
                patch('twilio.rest.Client') as cli_cls:
            envio_comun.enviar(self._ctx('Resp meta'))
        turno.assert_called_once_with(
            f'whatsapp:+{TEL}',
            'Resp meta',
            media_url=None,
            agente='curso',
        )
        cli_cls.assert_not_called()