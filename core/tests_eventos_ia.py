"""Tests Parte 2A — EventoIA y evaluación auditable de checkpoint."""

from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from core.eventos_ia import (
    emit_checkpoint_evaluado,
    emit_evento,
    emit_intent_detectado,
    emit_mensaje_enviado,
    emit_rag_query_executed,
    emit_webhook_recibido,
    get_or_create_trace_id,
    set_trace_id,
)
from core.helpers_examenes import evaluar_checkpoint_reto_ia
from core.models import EventoIA, Modulo


class CheckpointDecisionTests(TestCase):
    def _mod(self, numero, pref=Modulo.FACILITADOR_CP_AUTO):
        return SimpleNamespace(numero=numero, facilitador_checkpoint=pref)

    def test_auto_m1_no_reto(self):
        d = evaluar_checkpoint_reto_ia(self._mod(1), 5, True)
        self.assertFalse(d.es_reto)
        self.assertEqual(d.regla_aplicada, 'auto_sin_match')

    def test_override_si_m1_si_reto(self):
        d = evaluar_checkpoint_reto_ia(self._mod(1, Modulo.FACILITADOR_CP_SI), 5, True)
        self.assertTrue(d.es_reto)
        self.assertEqual(d.regla_aplicada, 'override_si')

    def test_override_no_m3_no_reto(self):
        d = evaluar_checkpoint_reto_ia(self._mod(3, Modulo.FACILITADOR_CP_NO), 5, True)
        self.assertFalse(d.es_reto)
        self.assertEqual(d.regla_aplicada, 'override_no')

    def test_auto_m3_reto(self):
        d = evaluar_checkpoint_reto_ia(self._mod(3), 5, True)
        self.assertTrue(d.es_reto)
        self.assertEqual(d.regla_aplicada, 'auto_regla_m3')

    def test_modulo_ya_completado_anula(self):
        d = evaluar_checkpoint_reto_ia(self._mod(3), 5, True, modulo_ya_completado=True)
        self.assertFalse(d.es_reto)
        self.assertEqual(d.regla_aplicada, 'anulado_modulo_ya_completado')
        self.assertTrue(d.modulo_ya_completado_anulo)


class EventoIATests(TestCase):
    def test_emit_evento_persiste(self):
        tid = set_trace_id()
        ev = emit_evento(
            EventoIA.TIPO_CHECKPOINT_EVALUADO,
            facilitador_checkpoint='auto',
            regla_aplicada='auto_regla_m3',
            es_reto=True,
        )
        self.assertIsNotNone(ev)
        self.assertEqual(str(ev.trace_id), tid)
        self.assertEqual(EventoIA.objects.count(), 1)

    def test_emit_checkpoint_desde_decision(self):
        mod = SimpleNamespace(numero=3, facilitador_checkpoint=Modulo.FACILITADOR_CP_AUTO)
        decision = evaluar_checkpoint_reto_ia(mod, 5, True)
        emit_checkpoint_evaluado(decision, estudiante=None, curso=None, modulo=None, origen='test')
        ev = EventoIA.objects.get()
        self.assertEqual(ev.tipo, EventoIA.TIPO_CHECKPOINT_EVALUADO)
        self.assertEqual(ev.regla_aplicada, 'auto_regla_m3')
        self.assertTrue(ev.es_reto)

    def test_emit_webhook_e_intent(self):
        emit_webhook_recibido(mensaje='hola', telefono='573001234567')
        emit_intent_detectado(intent='saludo', mensaje='hola')
        tipos = set(EventoIA.objects.values_list('tipo', flat=True))
        self.assertIn(EventoIA.TIPO_WEBHOOK_RECIBIDO, tipos)
        self.assertIn(EventoIA.TIPO_INTENT_DETECTADO, tipos)

    def test_emit_mensaje_enviado(self):
        emit_mensaje_enviado(telefono='573009999888', texto='respuesta test', mensaje_id='SM123')
        ev = EventoIA.objects.get(tipo=EventoIA.TIPO_MENSAJE_ENVIADO)
        self.assertEqual(ev.metadata.get('twilio_sid'), 'SM123')

    def test_trace_id_reutilizable_en_mismo_contexto(self):
        a = get_or_create_trace_id()
        b = get_or_create_trace_id()
        self.assertEqual(a, b)

    def test_rag_evento_guarda_chunks(self):
        emit_rag_query_executed(
            pregunta='precio urea',
            chunks=[{'fuente': 'lista.xlsx', 'cliente_id': 1, 'similitud': 0.9}],
            chunks_count=1,
            contexto_chars=100,
        )
        ev = EventoIA.objects.get(tipo=EventoIA.TIPO_RAG_QUERY_EXECUTED)
        self.assertEqual(len(ev.metadata.get('chunks', [])), 1)


class AiCapabilitiesTests(TestCase):
    def test_registry_checkpoint_default_on(self):
        from core.ai_capabilities import resolver_ai_capability

        self.assertTrue(resolver_ai_capability('checkpoint_dario'))

    def test_registry_unknown_off(self):
        from core.ai_capabilities import resolver_ai_capability

        self.assertFalse(resolver_ai_capability('inventado'))


class AiOpsRoutesTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.staff = user_model.objects.create_user(
            username='staff-aiops',
            password='test-pass-123',
            is_staff=True,
        )
        self.client = Client()
        self.client.force_login(self.staff)

    def test_ruta_eventos_200(self):
        resp = self.client.get(reverse('ai_ops_eventos'))
        self.assertEqual(resp.status_code, 200)

    def test_api_eventos_json(self):
        emit_evento(EventoIA.TIPO_IA_AGENT_TRIGGERED, agente='nati', output_preview='hola')
        resp = self.client.get(reverse('api_eventos_ia'))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['schema'], 'eventos_ia_v1')
        self.assertEqual(len(data['eventos']), 1)

    def test_replay_trace(self):
        tid = set_trace_id()
        emit_evento(EventoIA.TIPO_RAG_QUERY_EXECUTED, agente='nati', input_preview='consulta')
        resp = self.client.get(reverse('ai_ops_replay', kwargs={'trace_id': tid}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, tid)
