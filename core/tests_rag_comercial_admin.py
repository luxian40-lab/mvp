"""Admin RAG comercial: URLs proxy agents_commercial."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from agents_commercial.models import DocumentoRAGComercial


class DocumentoRAGComercialAdminUrlTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser(
            username='admin_rag',
            email='admin@eki.test',
            password='testpass123',
        )
        self.client = Client()
        self.client.force_login(self.admin)

    def test_changelist_no_reverse_error(self):
        url = reverse('admin:agents_commercial_documentoragcomercial_changelist')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Subida masiva')

    def test_subida_masiva_url_registered(self):
        url = reverse('admin:agents_commercial_documentoragcomercial_subida_masiva')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Subida masiva')

    def test_core_url_not_registered(self):
        with self.assertRaises(Exception):
            reverse('admin:core_documentoragcomercial_subida_masiva')
