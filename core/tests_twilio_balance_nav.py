from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, SimpleTestCase, TestCase, override_settings

from core.twilio_balance import twilio_balance_badge
from mvp_project.static_safe import static_safe
from mvp_project.unfold_admin import environment_callback


class StaticSafeTests(SimpleTestCase):
    def test_fallback_on_missing_manifest(self):
        with patch('mvp_project.static_safe.static', side_effect=ValueError('missing')):
            with patch(
                'mvp_project.static_safe.staticfiles_storage.url',
                side_effect=ValueError('missing'),
            ):
                self.assertEqual(
                    static_safe('favicons/admin-32.png'),
                    '/static/favicons/admin-32.png',
                )


class TwilioBalanceBadgeTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    @override_settings(TWILIO_ACCOUNT_SID='', TWILIO_AUTH_TOKEN='')
    def test_sin_creds(self):
        self.assertEqual(twilio_balance_badge(), ('Twilio sin credenciales', 'danger'))

    @override_settings(TWILIO_ACCOUNT_SID='ACxx', TWILIO_AUTH_TOKEN='tok')
    def test_saldo_usd(self):
        fake = MagicMock()
        fake.balance = '87.40'
        fake.currency = 'USD'
        usage = MagicMock()
        usage.price = '12.35'
        with patch('twilio.rest.Client') as mock_c:
            mock_c.return_value.api.v2010.balance.fetch.return_value = fake
            mock_c.return_value.usage.records.this_month.list.return_value = [usage]
            texto, tono = twilio_balance_badge()
        self.assertEqual(texto, 'Twilio $12.35 este mes · $87.40 queda')
        self.assertEqual(tono, 'info')

    @override_settings(TWILIO_ACCOUNT_SID='ACxx', TWILIO_AUTH_TOKEN='tok')
    def test_environment_callback(self):
        with patch(
            'core.twilio_balance.twilio_balance_badge',
            return_value=('Twilio $12', 'danger'),
        ):
            self.assertEqual(
                environment_callback(None),
                ['Twilio $12', 'danger'],
            )


@override_settings(SECURE_SSL_REDIRECT=False)
class TwilioNavHeaderTests(TestCase):
    def test_barra_tiene_chip_twilio(self):
        User.objects.create_user('navstaff', password='x', is_staff=True, is_superuser=True)
        c = Client()
        c.login(username='navstaff', password='x')
        with patch(
            'core.twilio_balance.twilio_balance_badge',
            return_value=('Twilio $9.00 este mes · $50.00 queda', 'info'),
        ):
            r = c.get('/admin/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'eki-twilio-nav')
        self.assertContains(r, 'Twilio $9.00 este mes')
