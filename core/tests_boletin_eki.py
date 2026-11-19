"""Boletín eki: un solo publicado; URL fija staff."""
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from core.models import BoletinEki


class BoletinPublicadoTests(TestCase):
    def test_publicar_despublica_el_anterior(self):
        a = BoletinEki.objects.create(
            titulo='Uno', cuerpo='<p>a</p>', publicado=True,
        )
        b = BoletinEki.objects.create(
            titulo='Dos', cuerpo='<p>b</p>', publicado=True,
        )
        a.refresh_from_db()
        b.refresh_from_db()
        self.assertFalse(a.publicado)
        self.assertTrue(b.publicado)
        self.assertEqual(BoletinEki.objects.filter(publicado=True).count(), 1)

    def test_url_fija_muestra_publicado(self):
        BoletinEki.objects.create(
            titulo='Novedades <QA>',
            cuerpo='<p>Diploma por Meta</p>',
            publicado=True,
        )
        staff = User.objects.create_superuser('nov_admin', 'n@test.com', 'x')
        http = Client()
        http.force_login(staff)
        resp = http.get(reverse('novedades_eki'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Diploma por Meta')
        self.assertContains(resp, 'Novedades')
        self.assertContains(resp, '/admin/novedades-eki/')

    def test_url_sin_boletin_no_rompe(self):
        staff = User.objects.create_superuser('nov_empty', 'e@test.com', 'x')
        http = Client()
        http.force_login(staff)
        resp = http.get('/admin/novedades-eki/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Todavía no hay un boletín')
