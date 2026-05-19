"""Tests Parte 4 — Knowledge Studio HITL."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from core.knowledge_studio import (
    calcular_salud_rag,
    crear_candidata_hitl,
    publicar_candidata_en_rag,
    revisar_candidata,
)
from core.models import Cliente, ConversacionRAGCandidata, SesionComercial


class KnowledgeStudioHitlTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='agronomo', password='test12345')
        self.cliente = Cliente.objects.create(
            nombre='Coop Agro',
            contacto_principal='Pedro',
            email='pedro@test.co',
            telefono='573009998877',
        )
        self.sesion = SesionComercial.objects.create(
            telefono='573009998877',
            cliente=self.cliente,
        )

    def test_crear_candidata_hitl(self):
        c = crear_candidata_hitl(
            cliente=self.cliente,
            sesion=self.sesion,
            telefono='573009998877',
            pregunta='¿Dosis de fungicida para roya en café?',
            respuesta_nati='Según ficha técnica, aplicar cuando humedad alta.',
            contexto_agro={'cultivo': 'café', 'problema': 'roya'},
            chunks_rag=[{'fuente': 'ficha.pdf', 'similitud': 0.89}],
        )
        self.assertIsNotNone(c)
        self.assertEqual(c.estado, ConversacionRAGCandidata.ESTADO_PENDIENTE)
        self.assertEqual(ConversacionRAGCandidata.objects.count(), 1)

    def test_no_duplica_pendiente_misma_pregunta(self):
        kwargs = dict(
            cliente=self.cliente,
            sesion=self.sesion,
            telefono='573009998877',
            pregunta='¿Cuánto N aplicar?',
            respuesta_nati='Depende del análisis de suelo.',
        )
        self.assertIsNotNone(crear_candidata_hitl(**kwargs))
        self.assertIsNone(crear_candidata_hitl(**kwargs))
        self.assertEqual(ConversacionRAGCandidata.objects.count(), 1)

    def test_revisar_aprobar(self):
        c = crear_candidata_hitl(
            cliente=self.cliente,
            sesion=self.sesion,
            telefono='573009998877',
            pregunta='¿Control de broca?',
            respuesta_nati='Monitoreo semanal y trampas.',
        )
        revisar_candidata(
            c,
            usuario=self.user,
            accion='aprobar',
            respuesta_revisada='Monitoreo semanal, trampas y aplicación focalizada.',
        )
        c.refresh_from_db()
        self.assertEqual(c.estado, ConversacionRAGCandidata.ESTADO_APROBADA)
        self.assertEqual(c.revisado_por_id, self.user.id)

    @patch('core.rag_comercial_manager.rag_comercial_manager')
    def test_publicar_candidata(self, mock_rag):
        mock_rag.disponible = True
        mock_rag.procesar_texto.return_value = 3
        c = crear_candidata_hitl(
            cliente=self.cliente,
            sesion=self.sesion,
            telefono='573009998877',
            pregunta='¿Fertilización foliar en floración?',
            respuesta_nati='Use microelementos según análisis.',
        )
        result = publicar_candidata_en_rag(c, usuario=self.user)
        self.assertTrue(result.get('ok'))
        c.refresh_from_db()
        self.assertEqual(c.estado, ConversacionRAGCandidata.ESTADO_PUBLICADA)

    def test_calcular_salud_rag(self):
        salud = calcular_salud_rag(self.cliente.id)
        self.assertIn('documentos_total', salud)
        self.assertIn('candidatas_pendientes', salud)


class KnowledgeStudioViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username='staff',
            password='test12345',
            is_staff=True,
        )
        self.client = Client()
        self.client.login(username='staff', password='test12345')

    def test_vista_knowledge_studio_200(self):
        resp = self.client.get('/admin/knowledge-studio/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Knowledge Studio')
