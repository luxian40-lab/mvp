"""Filtro ops de fallos WhatsApp + smoke changelist admin."""

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory, TestCase, override_settings

from core.admin.campanas import CodigoTwilioWhatsappFilter, WhatsappLogAdmin
from core.models import WhatsappLog
from core.models_media_entrega import MediaPaqueteEntrega


@override_settings(
    ALLOWED_HOSTS=['testserver', 'localhost', '127.0.0.1', 'admin.eki.technology'],
)
class WhatsappFallosAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.user = User.objects.create_superuser(
            username='wa_fallos_admin',
            email='wa_fallos@eki.test',
            password='WaFallos2026!',
        )
        WhatsappLog.objects.create(
            telefono='573001111111',
            mensaje='ok',
            tipo='SENT',
            estado='DELIVERED',
            mensaje_id='SMok',
        )
        WhatsappLog.objects.create(
            telefono='573002222222',
            mensaje='[MEDIA:https://example.com/a.mp4]',
            tipo='SENT',
            estado='UNDELIVERED',
            mensaje_id='SMbad19',
            error_detalle='63019 Media failed to download',
        )
        WhatsappLog.objects.create(
            telefono='573003333333',
            mensaje='hola',
            tipo='SENT',
            estado='FAILED',
            mensaje_id='SMbad21',
            error_detalle='63021 Video format',
        )
        WhatsappLog.objects.create(
            telefono='573004444444',
            mensaje='x',
            tipo='SENT',
            estado='ERROR',
            mensaje_id='SMotro',
            error_detalle='timeout gateway',
        )
        MediaPaqueteEntrega.objects.create(
            telefono='573002222222',
            estado=MediaPaqueteEntrega.ESTADO_FALLIDO,
            error_code='63019',
            media_url='https://example.com/a.mp4',
            intentos=2,
        )

    def setUp(self):
        self.client = Client(HTTP_HOST='admin.eki.technology')
        assert self.client.login(username='wa_fallos_admin', password='WaFallos2026!')
        self.factory = RequestFactory()
        self.admin = WhatsappLogAdmin(WhatsappLog, admin.site)

    def _filter_qs(self, value):
        # Django 5.2 SimpleListFilter espera params[param] como lista (getlist).
        request = self.factory.get('/admin/core/whatsapplog/', {'codigo_twilio': value})
        f = CodigoTwilioWhatsappFilter(
            request, {'codigo_twilio': [value]}, WhatsappLog, self.admin
        )
        return f.queryset(request, WhatsappLog.objects.all())

    def test_filtro_63019(self):
        qs = self._filter_qs('63019')
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().mensaje_id, 'SMbad19')

    def test_filtro_fallos(self):
        qs = self._filter_qs('fallos')
        ids = set(qs.values_list('mensaje_id', flat=True))
        self.assertEqual(ids, {'SMbad19', 'SMbad21', 'SMotro'})

    def test_filtro_otro(self):
        qs = self._filter_qs('otro')
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().mensaje_id, 'SMotro')

    def test_changelist_whatsapplog_ok(self):
        r = self.client.get('/admin/core/whatsapplog/?codigo_twilio=fallos', follow=True)
        self.assertEqual(r.status_code, 200)
        body = r.content.decode('utf-8', errors='ignore')
        self.assertIn('63019', body)

    def test_changelist_media_paquete_ok(self):
        r = self.client.get(
            '/admin/core/mediapaqueteentrega/?estado__exact=fallido',
            follow=True,
        )
        self.assertEqual(r.status_code, 200)
        body = r.content.decode('utf-8', errors='ignore')
        self.assertIn('63019', body)

    def test_dashboard_ai_ops_tiene_atajos(self):
        r = self.client.get('/admin/dashboard/?tab=ai_ops', follow=True)
        self.assertEqual(r.status_code, 200)
        body = r.content.decode('utf-8', errors='ignore')
        self.assertIn('Fallos WhatsApp', body)
        self.assertIn('codigo_twilio=fallos', body)
