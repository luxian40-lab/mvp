"""Tests menú sandbox: Agentes (submenú) | Cursos Riendas + correlador territorial."""

from django.test import TestCase, override_settings
from django.utils import timezone
from unittest.mock import patch

from core.event_engine import correlacionar_clusters, publicar_evento, registrar_senal_territorial
from core.models import AlertaTerritorial, EventOutbox, SandboxCanalSesion, SenalTerritorial
from core.sandbox_menu import (
    MODO_AGENTES,
    MODO_COACH,
    MODO_CURSOS,
    MODO_IA_CAMPO,
    MODO_MENU,
    MODO_NAT,
    TEXTO_AGENTES,
    dispatch_sandbox_menu,
    es_destino_sandbox,
    memoria_corte_nat,
    resolver_ruta_sandbox,
)


@override_settings(
    SANDBOX_MENU_ENABLED=True,
    BOT_COMERCIAL_SANDBOX_NUMBER='14155238886',
    BOT_COMERCIAL_WHATSAPP_NUMBER='573001111111',
    EKI_DEMO_RIENDAS_CURSO_ID='36',
)
class SandboxMenuTests(TestCase):
    def test_solo_sandbox_es_destino(self):
        self.assertTrue(es_destino_sandbox({'To': 'whatsapp:+14155238886'}))
        self.assertFalse(es_destino_sandbox({'To': 'whatsapp:+573001111111'}))

    def test_primer_mensaje_muestra_menu(self):
        d = resolver_ruta_sandbox({
            'From': 'whatsapp:+573001234567',
            'To': 'whatsapp:+14155238886',
            'Body': 'hola',
        })
        self.assertEqual(d.action, 'show_menu')
        self.assertEqual(
            SandboxCanalSesion.objects.get(telefono='573001234567').modo,
            MODO_MENU,
        )

    def test_elige_agentes_muestra_submenu(self):
        base = {
            'From': 'whatsapp:+573001234568',
            'To': 'whatsapp:+14155238886',
        }
        d1 = resolver_ruta_sandbox({**base, 'Body': '1'})
        self.assertEqual(d1.action, 'show_agentes')
        self.assertEqual(
            SandboxCanalSesion.objects.get(telefono='573001234568').modo,
            MODO_AGENTES,
        )

    def test_submenu_agronomo_continua_sin_reset(self):
        base = {
            'From': 'whatsapp:+573001234571',
            'To': 'whatsapp:+14155238886',
        }
        resolver_ruta_sandbox({**base, 'Body': '1'})
        d = resolver_ruta_sandbox({**base, 'Body': '1'})
        self.assertEqual(d.action, 'nat')
        self.assertFalse(d.reset_nat)
        self.assertTrue(d.saludo_entrada)
        ses = SandboxCanalSesion.objects.get(telefono='573001234571')
        self.assertEqual(ses.modo, MODO_NAT)
        self.assertIsNone(ses.memoria_corte_en)

    def test_reiniciar_corta_memoria_en_agente(self):
        base = {
            'From': 'whatsapp:+573001234580',
            'To': 'whatsapp:+14155238886',
        }
        resolver_ruta_sandbox({**base, 'Body': '1'})
        resolver_ruta_sandbox({**base, 'Body': '2'})  # coach
        d = resolver_ruta_sandbox({**base, 'Body': 'reiniciar'})
        self.assertEqual(d.action, MODO_COACH)
        self.assertTrue(d.reset_nat)

    def test_submenu_coach_y_ia_campo(self):
        base = {
            'From': 'whatsapp:+573001234572',
            'To': 'whatsapp:+14155238886',
        }
        resolver_ruta_sandbox({**base, 'Body': '1'})
        d2 = resolver_ruta_sandbox({**base, 'Body': '2'})
        self.assertEqual(d2.action, 'coach')
        self.assertTrue(d2.saludo_entrada)
        self.assertEqual(
            SandboxCanalSesion.objects.get(telefono='573001234572').modo,
            MODO_COACH,
        )
        resolver_ruta_sandbox({**base, 'Body': 'menu'})
        resolver_ruta_sandbox({**base, 'Body': '1'})
        d3 = resolver_ruta_sandbox({**base, 'Body': '3'})
        self.assertEqual(d3.action, 'ia_campo')
        self.assertTrue(d3.saludo_entrada)
        self.assertEqual(
            SandboxCanalSesion.objects.get(telefono='573001234572').modo,
            MODO_IA_CAMPO,
        )

    def test_elige_cursos_bootstrap(self):
        base = {
            'From': 'whatsapp:+573001234569',
            'To': 'whatsapp:+14155238886',
        }
        self.assertEqual(
            resolver_ruta_sandbox({**base, 'Body': '2'}).action,
            'cursos_bootstrap',
        )
        self.assertEqual(
            SandboxCanalSesion.objects.get(telefono='573001234569').modo,
            MODO_CURSOS,
        )
        self.assertEqual(resolver_ruta_sandbox({**base, 'Body': 'listo'}).action, 'cursos')
        self.assertEqual(resolver_ruta_sandbox({**base, 'Body': 'menu'}).action, 'show_menu')

    def test_hola_desde_cursos_vuelve_al_menu(self):
        base = {
            'From': 'whatsapp:+573001234581',
            'To': 'whatsapp:+14155238886',
        }
        resolver_ruta_sandbox({**base, 'Body': '2'})
        d = resolver_ruta_sandbox({**base, 'Body': 'hola'})
        self.assertEqual(d.action, 'show_menu')
        self.assertEqual(
            SandboxCanalSesion.objects.get(telefono='573001234581').modo,
            MODO_MENU,
        )

    def test_audio_en_coach_usa_transcripcion(self):
        tel_from = 'whatsapp:+573001234582'
        to = 'whatsapp:+14155238886'
        resolver_ruta_sandbox({'From': tel_from, 'To': to, 'Body': '1'})
        resolver_ruta_sandbox({'From': tel_from, 'To': to, 'Body': '2'})
        audio_payload = {
            'From': tel_from,
            'To': to,
            'Body': '',
            'NumMedia': '1',
            'MediaUrl0': 'https://api.twilio.com/audio.ogg',
            'MediaContentType0': 'audio/ogg',
        }
        with patch(
            'core.views._transcribir_audio_twilio',
            return_value='me cuesta organizar el tiempo',
        ):
            d = resolver_ruta_sandbox(audio_payload)
        self.assertEqual(d.action, 'coach')
        self.assertFalse(d.saludo_entrada)

    def test_dispatch_agentes_handled(self):
        with patch('core.sandbox_menu.enviar_menu_agentes', return_value={'success': True}):
            self.assertEqual(
                dispatch_sandbox_menu({
                    'From': 'whatsapp:+573001234570',
                    'To': 'whatsapp:+14155238886',
                    'Body': '1',
                }),
                'handled',
            )

    def test_dispatch_nat_entrada_no_resetea(self):
        base = {
            'From': 'whatsapp:+573001234573',
            'To': 'whatsapp:+14155238886',
        }
        with patch('core.sandbox_menu.enviar_menu_agentes', return_value={'success': True}):
            dispatch_sandbox_menu({**base, 'Body': '1'})
        with patch('core.sandbox_menu.enviar_texto_sandbox', return_value={'success': True}) as send:
            out = dispatch_sandbox_menu({**base, 'Body': '1'})
        self.assertEqual(out, 'handled')
        self.assertTrue(send.called)
        self.assertIsNone(memoria_corte_nat('573001234573'))

    def test_dispatch_reiniciar_nat_marca_corte(self):
        base = {
            'From': 'whatsapp:+573001234576',
            'To': 'whatsapp:+14155238886',
        }
        with patch('core.sandbox_menu.enviar_menu_agentes', return_value={'success': True}):
            dispatch_sandbox_menu({**base, 'Body': '1'})
        with patch('core.sandbox_menu.enviar_texto_sandbox', return_value={'success': True}):
            dispatch_sandbox_menu({**base, 'Body': '1'})  # entra Nat sin corte
        with patch('core.sandbox_menu.enviar_texto_sandbox', return_value={'success': True}):
            out = dispatch_sandbox_menu({**base, 'Body': 'reiniciar'})
        self.assertEqual(out, 'handled')
        self.assertIsNotNone(memoria_corte_nat('573001234576'))

    def test_dispatch_cursos_bootstrap_riendas(self):
        with patch('core.sandbox_menu.bootstrap_cursos_sandbox', return_value=True) as boot:
            out = dispatch_sandbox_menu({
                'From': 'whatsapp:+573001234574',
                'To': 'whatsapp:+14155238886',
                'Body': '2',
            })
        self.assertEqual(out, 'handled')
        self.assertTrue(boot.called)

    def test_dispatch_coach_handled(self):
        base = {
            'From': 'whatsapp:+573001234575',
            'To': 'whatsapp:+14155238886',
        }
        with patch('core.sandbox_menu.enviar_menu_agentes', return_value={'success': True}):
            dispatch_sandbox_menu({**base, 'Body': '1'})
        with patch('core.sandbox_menu.enviar_texto_sandbox', return_value={'success': True}):
            self.assertEqual(dispatch_sandbox_menu({**base, 'Body': '2'}), 'handled')

    def test_texto_agentes_menciona_tres(self):
        self.assertIn('Agrónomo', TEXTO_AGENTES)
        self.assertIn('Coach', TEXTO_AGENTES)
        self.assertIn('Profe IA', TEXTO_AGENTES)
        self.assertIn('reiniciar', TEXTO_AGENTES)


@override_settings(DATA_LAKE_ENABLED=False)
class EventEngineClusterTests(TestCase):
    def test_outbox_publicar(self):
        row = publicar_evento(
            event_type='aprendizaje.listo.recibido',
            payload={'ok': True},
            territory_id='05001',
            org_id=1,
        )
        self.assertTrue(EventOutbox.objects.filter(pk=row.pk).exists())
        self.assertIsNone(row.published_at)

    def test_cluster_density_v0(self):
        now = timezone.now()
        for i in range(3):
            registrar_senal_territorial(
                tipo='salud.sintoma.diarrea',
                territory_id='05001',
                confianza=0.8,
                occurred_at=now,
                metadata={'i': i},
            )
        registrar_senal_territorial(
            tipo='salud.sintoma.diarrea',
            territory_id='11001',
            confianza=0.8,
            occurred_at=now,
        )
        alertas = correlacionar_clusters(ventana_horas=72, min_k=3)
        self.assertEqual(len(alertas), 1)
        a = alertas[0]
        self.assertEqual(a.territory_id, '05001')
        self.assertEqual(a.conteo, 3)
        self.assertEqual(SenalTerritorial.objects.count(), 4)
        self.assertEqual(AlertaTerritorial.objects.filter(estado='detectada').count(), 1)
