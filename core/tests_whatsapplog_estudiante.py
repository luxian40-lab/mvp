"""WhatsappLog: nombre de estudiante por teléfono (FK o resolución)."""

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.admin.campanas import WhatsappLogAdmin
from core.models import Cliente, Estudiante, WhatsappLog
from core.utils_telefono import resolver_estudiante_por_telefono


@override_settings(
    ALLOWED_HOSTS=['testserver', 'localhost', '127.0.0.1', 'admin.eki.technology'],
)
class WhatsappLogEstudianteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.user = User.objects.create_superuser(
            username='wa_log_est',
            email='wa_log_est@eki.test',
            password='WaLogEst2026!',
        )
        cls.cliente = Cliente.objects.create(
            nombre='Org WA Log',
            contacto_principal='Ops',
            email='ops@eki.test',
            telefono='3001112233',
            activo=True,
        )
        cls.est = Estudiante.objects.create(
            cedula='walog1',
            nombre='María Campo',
            telefono='573008887766',
            cliente=cls.cliente,
            activo=True,
        )

    def test_resolver_por_variante_sin_57(self):
        est = resolver_estudiante_por_telefono('3008887766')
        self.assertEqual(est.pk, self.est.pk)

    def test_save_autoasigna_estudiante(self):
        log = WhatsappLog.objects.create(
            telefono='3008887766',
            mensaje='hola',
            tipo='INCOMING',
            estado='RECIBIDO',
        )
        log.refresh_from_db()
        self.assertEqual(log.estudiante_id, self.est.pk)

    def test_changelist_muestra_nombre_sin_fk_previa(self):
        # Crear sin pasar por save auto: update forzar null tras create
        log = WhatsappLog.objects.create(
            telefono='573008887766',
            mensaje='ping',
            tipo='SENT',
            estado='SENT',
            estudiante=self.est,
        )
        WhatsappLog.objects.filter(pk=log.pk).update(estudiante=None)
        log.refresh_from_db()
        self.assertIsNone(log.estudiante_id)

        admin_obj = WhatsappLogAdmin(WhatsappLog, admin.site)
        nombre = admin_obj.estudiante_nombre(log)
        self.assertEqual(nombre, 'María Campo')

        client = Client(HTTP_HOST='admin.eki.technology')
        assert client.login(username='wa_log_est', password='WaLogEst2026!')
        r = client.get(reverse('admin:core_whatsapplog_changelist'), follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertIn('María Campo', r.content.decode('utf-8'))
