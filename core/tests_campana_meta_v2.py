"""Claim, incierto y opt-in. El flag apagado no entra aquí."""
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from core.campana_meta_v2 import ejecutar_campana_meta_v2, marcar_enviando_viejos, reclamar
from core.meta_estados import aplicar_statuses
from core.models import Estudiante, WhatsappLog
from core.models_campana_meta import CampanaMeta, EnvioCampanaMeta, PlantillaMeta

PHONE = '495439026995771'


def _ok(wamid='wamid.1'):
    return 200, {'messages': [{'id': wamid}]}


@override_settings(
    META_CAMPANAS_V2_ENABLED=True,
    EKI_CAMPANA_META_ENABLED=True,
    WHATSAPP_TOKEN='tok',
    WHATSAPP_PHONE_ID=PHONE,
    WHATSAPP_API_VERSION='v21.0',
)
class CampanaMetaV2Tests(TestCase):
    def setUp(self):
        self.plantilla = PlantillaMeta.objects.create(
            nombre_interno='Aviso cafe',
            categoria='UTILITY',
            idioma='es',
            cuerpo='Tu curso abre mañana.',
            estado='APPROVED',
        )
        self.campana = CampanaMeta.objects.create(nombre='Cohorte', plantilla=self.plantilla)
        self.ana = self._est('573009992001', 'Ana')
        self.campana.destinatarios.add(self.ana)

    def _est(self, tel, nombre):
        est = Estudiante.objects.create(nombre=nombre, cedula=tel[-6:], telefono=tel)
        est.wa_optin_fecha = timezone.now()
        est.wa_optin_origen = 'habeas'
        est.save(update_fields=['wa_optin_fecha', 'wa_optin_origen'])
        return est

    @patch('core.campana_meta_v2._post', return_value=_ok())
    def test_reejecutar_no_duplica(self, post):
        ejecutar_campana_meta_v2(self.campana)
        ejecutar_campana_meta_v2(self.campana)
        self.assertEqual(post.call_count, 1)
        self.assertEqual(EnvioCampanaMeta.objects.filter(campana=self.campana).count(), 1)

    def test_el_segundo_claim_no_gana(self):
        envio = EnvioCampanaMeta.objects.create(
            campana=self.campana, estudiante=self.ana, estado='PENDIENTE',
        )
        self.assertIsNotNone(reclamar(envio.pk))
        self.assertIsNone(reclamar(envio.pk))

    @patch('core.campana_meta_v2._post', return_value=(0, {'error': {'code': 'TIMEOUT', 'message': 'Timeout'}}))
    def test_timeout_queda_incierto_y_no_se_reenvia(self, post):
        ejecutar_campana_meta_v2(self.campana)
        envio = EnvioCampanaMeta.objects.get(campana=self.campana)
        self.assertEqual(envio.estado, 'INCIERTO')
        ejecutar_campana_meta_v2(self.campana)
        self.assertEqual(post.call_count, 1)

    def test_enviando_viejo_pasa_a_incierto(self):
        EnvioCampanaMeta.objects.create(
            campana=self.campana,
            estudiante=self.ana,
            estado='ENVIANDO',
            claimed_at=timezone.now() - timedelta(minutes=11),
        )
        self.assertEqual(marcar_enviando_viejos(), 1)
        self.assertEqual(EnvioCampanaMeta.objects.get().estado, 'INCIERTO')

    def test_sin_optin_no_hay_plantilla(self):
        self.ana.wa_optin_fecha = None
        self.ana.save(update_fields=['wa_optin_fecha'])
        with patch('core.campana_meta_v2._post') as post:
            ejecutar_campana_meta_v2(self.campana)
        post.assert_not_called()
        self.assertEqual(EnvioCampanaMeta.objects.get().omitido_motivo, 'sin_optin')

    @patch('core.campana_meta_v2._post')
    def test_130429_no_corta_el_lote(self, post):
        luis = self._est('573009992002', 'Luis')
        self.campana.destinatarios.add(luis)
        post.side_effect = [
            (400, {'error': {'code': 130429, 'message': 'rate'}}),
            _ok('wamid.2'),
        ]
        ejecutar_campana_meta_v2(self.campana)
        self.assertEqual(post.call_count, 2)
        estados = set(EnvioCampanaMeta.objects.values_list('estado', flat=True))
        self.assertIn('ERROR_REINTENTABLE', estados)
        self.assertIn('ENVIADO', estados)

    @patch('core.campana_meta_v2._post')
    def test_190_detiene_el_resto(self, post):
        luis = self._est('573009992003', 'Luis')
        self.campana.destinatarios.add(luis)
        post.return_value = (401, {'error': {'code': 190, 'message': 'token'}})
        ejecutar_campana_meta_v2(self.campana)
        self.assertEqual(post.call_count, 1)
        self.assertEqual(
            EnvioCampanaMeta.objects.filter(omitido_motivo='token_invalido').count(),
            2,
        )

    def test_status_actualiza_envio_y_no_el_log(self):
        EnvioCampanaMeta.objects.create(
            campana=self.campana,
            estudiante=self.ana,
            estado='ENVIADO',
            wamid='wamid.entrega',
        )
        aplicar_statuses([{'id': 'wamid.entrega', 'status': 'delivered'}])
        envio = EnvioCampanaMeta.objects.get()
        self.assertEqual(envio.estado_entrega, 'delivered')
        self.assertIsNotNone(envio.entregado_en)
        self.assertFalse(WhatsappLog.objects.filter(mensaje_id='wamid.entrega').exists())

    def test_incierto_se_reconcilia_por_opaque(self):
        envio = EnvioCampanaMeta.objects.create(
            campana=self.campana, estudiante=self.ana, estado='INCIERTO',
        )
        aplicar_statuses([{
            'id': 'wamid.recon',
            'status': 'sent',
            'biz_opaque_callback_data': f'envio:{envio.pk}',
        }])
        envio.refresh_from_db()
        self.assertEqual(envio.estado, 'ENVIADO')
        self.assertEqual(envio.wamid, 'wamid.recon')
