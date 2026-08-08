from django.contrib.auth.models import User
from django.test import Client, SimpleTestCase, TestCase, override_settings

from core.infra_monitor import _human_bytes, snapshot_infra


class InfraMonitorHelpersTests(SimpleTestCase):
    def test_human_bytes(self):
        self.assertEqual(_human_bytes(500), '500 B')
        self.assertIn('KB', _human_bytes(2048))
        self.assertIn('GB', _human_bytes(2 * 1024 ** 3))


@override_settings(SECURE_SSL_REDIRECT=False)
class InfraMonitorAdminTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user('infra_staff', 'i@t.com', 'pass', is_staff=True)
        self.http = Client()

    def test_requiere_staff(self):
        r = self.http.get('/admin/infra/')
        self.assertIn(r.status_code, (302, 301))

    def test_staff_ve_panel_y_api(self):
        self.http.login(username='infra_staff', password='pass')
        r = self.http.get('/admin/infra/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Monitoreo infra')
        api = self.http.get('/admin/infra/api/')
        self.assertEqual(api.status_code, 200)
        data = api.json()
        self.assertIn('redis', data)
        self.assertIn('db', data)
        self.assertIn('s3', data)
        self.assertIn('playbooks', data)
        self.assertIn('overall', data)
        self.assertIn('advisor', data)
        self.assertIn('items', data['advisor'])
        self.assertIn('summary', data['advisor'])

    def test_snapshot_tiene_claves(self):
        snap = snapshot_infra(force=True)
        self.assertIn('poll_hint_seconds', snap)
        self.assertEqual(snap['poll_hint_seconds'], 30)
        self.assertIn('playbooks', snap)
        self.assertIn('overall', snap)
        self.assertIn('advisor', snap)
        self.assertEqual(snap['advisor']['kind'], 'rules')
        self.assertIn(snap['advisor']['level'], ('ok', 'watch', 'act'))
        ids = {p['id'] for p in snap['playbooks']}
        self.assertTrue({'rds', 'redis', 's3', 'eb', 'chroma'}.issubset(ids))
        for pb in snap['playbooks']:
            self.assertIn('verdict', pb)
            self.assertIn('actions', pb)
            self.assertTrue(pb['actions'])
            for a in pb['actions']:
                self.assertIn('action_type', a)
                self.assertIn('when', a)
                self.assertIn('do', a)
                self.assertIn('specs', a)

    def test_advisor_recomienda_si_redis_cae(self):
        from core.infra_monitor import build_infra_advisor

        playbooks = [{
            'id': 'redis',
            'title': 'Redis',
            'verdict': {'status': 'act', 'label': 'ACTUAR', 'reasons': ['down']},
            'actions': [
                {'action_type': 'NO_HACER_NADA', 'do': 'nada', 'when': '', 'how': '', 'approx_cost': ''},
                {'action_type': 'REINICIAR_LOCAL', 'do': 'restart', 'when': 'fail', 'how': 'ssh', 'approx_cost': '0'},
            ],
        }]
        adv = build_infra_advisor(playbooks, 'act')
        self.assertTrue(adv['needs_action'])
        self.assertEqual(len(adv['items']), 1)
        self.assertEqual(adv['items'][0]['next']['action_type'], 'REINICIAR_LOCAL')

    def test_header_health_strip_tiene_chips(self):
        from core.infra_monitor import header_health_strip

        chips = header_health_strip(force=True)
        labels = [c['label'] for c in chips]
        self.assertEqual(
            labels,
            ['WhatsApp', 'Celery', 'Redis', 'S3', 'PostgreSQL'],
        )
        for c in chips:
            self.assertIn('ok', c)
            self.assertIn('hint', c)

    def test_admin_index_muestra_saludo(self):
        self.staff.first_name = 'Andreina'
        self.staff.save(update_fields=['first_name'])
        self.http.login(username='infra_staff', password='pass')
        r = self.http.get('/admin/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'julian')
        self.assertContains(r, 'eki-panel-exec__hello')
        self.assertContains(r, 'eki-health')
