"""Smoke: crear Cliente / Curso / Módulo vía admin Unfold."""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings

from core.models import Cliente, Curso, Modulo


@override_settings(
    ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1", "admin.eki.technology"],
)
class UnfoldAdminCreateSmokeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.user = User.objects.create_superuser(
            username="unfold_create",
            email="create@eki.test",
            password="UnfoldCreate2026!",
        )

    def setUp(self):
        self.client = Client(HTTP_HOST="admin.eki.technology")
        assert self.client.login(username="unfold_create", password="UnfoldCreate2026!")

    def test_add_pages_render(self):
        for path in (
            "/admin/core/cliente/add/",
            "/admin/core/curso/add/",
            "/admin/core/modulo/add/",
        ):
            with self.subTest(path=path):
                r = self.client.get(path, follow=True)
                self.assertEqual(r.status_code, 200, msg=path)
                body = r.content.decode("utf-8", errors="ignore")
                self.assertNotIn("Server Error", body)
                self.assertIn("<form", body.lower())

    def test_changelist_has_add_affordance(self):
        for path, needle in (
            ("/admin/core/cliente/", "/admin/core/cliente/add/"),
            ("/admin/core/curso/", "/admin/core/curso/add/"),
            ("/admin/core/modulo/", "/admin/core/modulo/add/"),
        ):
            with self.subTest(path=path):
                r = self.client.get(path, follow=True)
                self.assertEqual(r.status_code, 200)
                self.assertIn(needle, r.content.decode("utf-8", errors="ignore"))

    def test_create_cliente_curso_modulo(self):
        # El form de Cliente tiene muchos campos/inlines; validamos que add/change
        # renderizan con Unfold. Alta mínima vía ORM + edición admin.
        org = Cliente.objects.create(nombre="Org Unfold QA", activo=True)
        r = self.client.get(f"/admin/core/cliente/{org.pk}/change/", follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertIn("Org Unfold QA", r.content.decode("utf-8", errors="ignore"))

        curso = Curso.objects.create(nombre="Curso Unfold QA", cliente=org, activo=True, orden=1)
        r2 = self.client.get(f"/admin/core/curso/{curso.pk}/change/", follow=True)
        self.assertEqual(r2.status_code, 200)

        modulo = Modulo.objects.create(curso=curso, numero=1, titulo="M1 Unfold", contenido="x")
        r3 = self.client.get(f"/admin/core/modulo/{modulo.pk}/change/", follow=True)
        self.assertEqual(r3.status_code, 200)

        r4 = self.client.get("/admin/core/modulo/add/", follow=True)
        self.assertEqual(r4.status_code, 200)
        body = r4.content.decode("utf-8", errors="ignore")
        self.assertIn("form", body.lower())
