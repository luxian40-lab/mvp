"""Tests del Panel ejecutivo en Inicio (/admin/)."""

from django.contrib.auth import get_user_model
from django.test import Client, SimpleTestCase, TestCase, override_settings

from core.views_admin_panel import _pct_delta, build_panel_snapshot


class PanelSnapshotHelpersTests(SimpleTestCase):
    def test_pct_delta_basico(self):
        self.assertEqual(_pct_delta(120, 100), 20)
        self.assertEqual(_pct_delta(0, 0), None)
        self.assertEqual(_pct_delta(5, 0), 100)


@override_settings(
    ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1", "admin.eki.technology"],
)
class PanelViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.user = User.objects.create_superuser(
            username="panel_smoke",
            email="panel@eki.test",
            password="PanelSmoke2026!",
        )

    def setUp(self):
        self.client = Client(HTTP_HOST="admin.eki.technology")
        assert self.client.login(username="panel_smoke", password="PanelSmoke2026!")

    def test_build_panel_snapshot_keys(self):
        snap = build_panel_snapshot()
        self.assertIn("kpis", snap)
        self.assertEqual(len(snap["kpis"]), 5)
        self.assertIn("espacios", snap)
        self.assertIn("mapa", snap)
        self.assertIn("activos_7d", snap)
        self.assertIn("atajos", snap)

    def test_panel_redirige_a_inicio(self):
        r = self.client.get("/admin/panel/", follow=False)
        self.assertIn(r.status_code, (301, 302))
        self.assertTrue(r["Location"].endswith("/admin/") or "/admin/" in r["Location"])

    def test_inicio_es_panel_ejecutivo(self):
        r = self.client.get("/admin/", follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Actividad en el territorio")
        self.assertContains(r, "mapa-panel-inicio")
        self.assertContains(r, "Espacios de trabajo")
        self.assertContains(r, "global=1")
        self.assertContains(r, "force=1")

    def test_cobertura_api_global(self):
        r = self.client.get("/admin/cobertura/datos.json?global=1&force=1", follow=True)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("por_municipio_clave", data)
        self.assertEqual(data.get("filtro"), "global_todos_estudiantes")
        self.assertIn("generated_at", data)
