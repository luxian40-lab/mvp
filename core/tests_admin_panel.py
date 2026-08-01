"""Tests del Panel ejecutivo (/admin/panel/)."""

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
        self.assertIn("atajos", snap)
        self.assertIn("cobertura", snap)

    def test_panel_requires_staff(self):
        anon = Client(HTTP_HOST="admin.eki.technology")
        r = anon.get("/admin/panel/", follow=True)
        # login redirect o forbidden
        if r.status_code == 200:
            self.assertTrue(any("/login" in u for u, _ in r.redirect_chain) or b"login" in r.content.lower())
        else:
            self.assertIn(r.status_code, (302, 403))

    def test_panel_renders(self):
        r = self.client.get("/admin/panel/", follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Actividad en el territorio")
        self.assertContains(r, "Accesos rápidos por área")
