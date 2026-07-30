"""Smoke Unfold admin: login + rutas críticas (sin deploy)."""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings


@override_settings(
    ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1", "admin.eki.technology"],
)
class UnfoldAdminSmokeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.user = User.objects.create_superuser(
            username="unfold_smoke",
            email="unfold@eki.test",
            password="UnfoldSmoke2026!",
        )

    def setUp(self):
        self.client = Client(HTTP_HOST="admin.eki.technology")
        assert self.client.login(username="unfold_smoke", password="UnfoldSmoke2026!")

    def _get(self, path: str):
        return self.client.get(path, follow=True)

    def test_admin_index_ok(self):
        r = self._get("/admin/")
        self.assertEqual(r.status_code, 200)
        body = r.content.decode("utf-8", errors="ignore").lower()
        self.assertNotIn("jazzmin", body)
        self.assertTrue("unfold" in body or "eki" in body)

    def test_estudiante_changelist_ok(self):
        r = self._get("/admin/core/estudiante/")
        self.assertEqual(r.status_code, 200)

    def test_curso_changelist_ok(self):
        r = self._get("/admin/core/curso/")
        self.assertEqual(r.status_code, 200)

    def test_dashboard_custom_ok(self):
        r = self._get("/admin/dashboard/")
        self.assertEqual(r.status_code, 200)

    def test_cobertura_custom_ok(self):
        r = self._get("/admin/cobertura/")
        self.assertEqual(r.status_code, 200)

    def test_infra_custom_ok(self):
        r = self._get("/admin/infra/")
        self.assertEqual(r.status_code, 200)
