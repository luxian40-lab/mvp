"""Tests: reordenar bloques de módulo (↑↓) sin tocar S3."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.models import ArchivoModulo, Cliente, Curso, Modulo, PasoModulo, SeccionModulo
from core.orden_bloques import intercambiar_orden


User = get_user_model()


class OrdenBloquesUnitTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(nombre='C Orden')
        self.curso = Curso.objects.create(nombre='Curso Orden', cliente=self.cliente)
        self.modulo = Modulo.objects.create(
            curso=self.curso, numero=1, titulo='M1', contenido='x',
        )
        self.s1 = SeccionModulo.objects.create(modulo=self.modulo, orden=1, titulo='A')
        self.s2 = SeccionModulo.objects.create(modulo=self.modulo, orden=2, titulo='B')
        self.s3 = SeccionModulo.objects.create(modulo=self.modulo, orden=3, titulo='C')

    def test_bajar_seccion(self):
        ok = intercambiar_orden(self.s1, 'down')
        self.assertTrue(ok)
        self.s1.refresh_from_db()
        self.s2.refresh_from_db()
        self.assertEqual(self.s1.orden, 2)
        self.assertEqual(self.s2.orden, 1)

    def test_subir_en_extremo_no_cambia(self):
        self.assertFalse(intercambiar_orden(self.s1, 'up'))
        self.s1.refresh_from_db()
        self.assertEqual(self.s1.orden, 1)

    def test_intercambiar_pasos(self):
        p1 = PasoModulo.objects.create(
            modulo=self.modulo, seccion=self.s1, orden=1, titulo='p1', contenido='a',
        )
        p2 = PasoModulo.objects.create(
            modulo=self.modulo, seccion=self.s1, orden=2, titulo='p2', contenido='b',
        )
        self.assertTrue(intercambiar_orden(p2, 'up'))
        p1.refresh_from_db()
        p2.refresh_from_db()
        self.assertEqual(p2.orden, 1)
        self.assertEqual(p1.orden, 2)

    def test_intercambiar_archivos(self):
        a1 = ArchivoModulo.objects.create(
            modulo=self.modulo, tipo='imagen', titulo='img1', orden=0,
        )
        a2 = ArchivoModulo.objects.create(
            modulo=self.modulo, tipo='imagen', titulo='img2', orden=1,
        )
        self.assertTrue(intercambiar_orden(a1, 'down'))
        a1.refresh_from_db()
        a2.refresh_from_db()
        self.assertEqual(a1.orden, 1)
        self.assertEqual(a2.orden, 0)


@override_settings(
    ALLOWED_HOSTS=['testserver', 'localhost', '127.0.0.1', 'admin.eki.technology'],
)
class OrdenBloquesAdminViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('ordenadmin', 'o@e.co', 'pass')
        self.client = Client(HTTP_HOST='admin.eki.technology')
        assert self.client.login(username='ordenadmin', password='pass')
        self.cliente = Cliente.objects.create(nombre='C Admin Orden')
        self.curso = Curso.objects.create(nombre='Curso Admin Orden', cliente=self.cliente)
        self.modulo = Modulo.objects.create(
            curso=self.curso, numero=1, titulo='M1', contenido='x',
        )
        self.s1 = SeccionModulo.objects.create(modulo=self.modulo, orden=1, titulo='A')
        self.s2 = SeccionModulo.objects.create(modulo=self.modulo, orden=2, titulo='B')

    def test_mover_via_admin_url(self):
        url = reverse(
            'admin:core_modulo_mover_bloque',
            args=[self.modulo.pk, 'seccion', self.s1.pk, 'down'],
        )
        r = self.client.get(url, follow=True)
        self.assertEqual(r.status_code, 200)
        self.s1.refresh_from_db()
        self.s2.refresh_from_db()
        self.assertEqual(self.s1.orden, 2)
        self.assertEqual(self.s2.orden, 1)
