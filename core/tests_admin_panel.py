"""Tests del Panel ejecutivo en Inicio (/admin/)."""

from django.contrib.auth import get_user_model
from django.test import Client, SimpleTestCase, TestCase, override_settings

from core.views_admin_panel import _build_ecosistema, _pct_delta, build_panel_snapshot


class PanelSnapshotHelpersTests(SimpleTestCase):
    def test_pct_delta_basico(self):
        self.assertEqual(_pct_delta(120, 100), 20)
        self.assertEqual(_pct_delta(0, 0), None)
        self.assertEqual(_pct_delta(5, 0), 100)

    def test_ecosistema_studio_no_conecta_aprende(self):
        eco = _build_ecosistema(
            cursos_activos=2,
            est_activos=10,
            activos_7d=4,
            empresas=3,
            campanas_enviadas=1,
            campanas_7d=1,
            certs=2,
            avance=40.0,
            eventos_ia=2,
            eventos_ia_total=9,
            sin_progreso=0,
        )
        ids = {n['id'] for n in eco['nodos']}
        self.assertIn('campo', ids)
        self.assertIn('studio', ids)
        self.assertIn('aprende', ids)
        pairs = {(e['from'], e['to']) for e in eco['aristas']}
        self.assertNotIn(('studio', 'aprende'), pairs)
        self.assertNotIn(('aprende', 'studio'), pairs)
        for a, b in pairs:
            self.assertNotEqual(a, 'studio')
            self.assertNotEqual(b, 'studio')
        studio = next(n for n in eco['nodos'] if n['id'] == 'studio')
        self.assertTrue(studio.get('island'))
        self.assertIn('proxy', studio['metric_label'].lower())
        campo = next(n for n in eco['nodos'] if n['id'] == 'campo')
        self.assertTrue(campo.get('anchor'))


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
        snap = build_panel_snapshot(force=True)
        self.assertIn("kpis", snap)
        self.assertEqual(len(snap["kpis"]), 5)
        self.assertIn("espacios", snap)
        self.assertEqual(len(snap["espacios"]), 2)
        self.assertEqual(snap.get("atajos"), [])
        self.assertTrue(snap.get("acciones"))
        self.assertTrue(all("delta_dir" in k for k in snap["kpis"]))
        self.assertIn("mapa", snap)
        self.assertIn("activos_7d", snap)
        self.assertIn("atajos", snap)
        self.assertIn("ecosistema", snap)
        self.assertIn("actualizado", snap)
        eco = snap["ecosistema"]
        self.assertEqual(len(eco["nodos"]), 7)
        self.assertTrue(eco["aristas"])
        ids = {n["id"] for n in eco["nodos"]}
        self.assertEqual(
            ids,
            {"studio", "aprende", "campo", "empresas", "campanas", "ia", "impacto"},
        )
        pairs = {(e["from"], e["to"]) for e in eco["aristas"]}
        self.assertNotIn(("studio", "aprende"), pairs)

    def test_panel_redirige_a_inicio(self):
        r = self.client.get("/admin/panel/", follow=False)
        self.assertIn(r.status_code, (301, 302))
        self.assertTrue(r["Location"].endswith("/admin/") or "/admin/" in r["Location"])

    def test_inicio_es_panel_ejecutivo(self):
        r = self.client.get("/admin/", follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Actividad en el territorio")
        self.assertContains(r, "mapa-panel-inicio")
        self.assertContains(r, "Más espacios")
        self.assertContains(r, "Ecosistema eki")
        self.assertContains(r, "eki-panel-eco--lux")
        self.assertContains(r, "data-eki-eco-graph")
        self.assertContains(r, "data-eco-id")
        self.assertContains(r, "eki_eco_graph.js")
        self.assertContains(r, "Studio es independiente de Aprende")
        self.assertContains(r, "global=1")
        self.assertContains(r, "force=1")

    def test_unfold_dashboard_callback_inyecta_snap(self):
        from core.views_admin_panel import unfold_dashboard_callback

        ctx = unfold_dashboard_callback(None, {})
        self.assertIn("snap", ctx)
        self.assertIn("kpis", ctx["snap"])
        self.assertIn("conversaciones_url", ctx)
        self.assertIn("dashboard_url", ctx)

    def test_cobertura_api_global(self):
        r = self.client.get("/admin/cobertura/datos.json?global=1&force=1", follow=True)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("por_municipio_clave", data)
        self.assertEqual(data.get("filtro"), "global_todos_estudiantes")
        self.assertIn("generated_at", data)
