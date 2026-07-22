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

    def test_snapshot_tiene_claves(self):
        snap = snapshot_infra(force=True)
        self.assertIn('poll_hint_seconds', snap)
        self.assertEqual(snap['poll_hint_seconds'], 30)
        self.assertIn('playbooks', snap)
        self.assertIn('overall', snap)
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
