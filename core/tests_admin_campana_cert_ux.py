"""Admin UX: Campaña tabs + PlantillaCertificado link learning."""
from django.contrib.admin.sites import site
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from core.admin.campanas import CampanaAdmin
from core.admin.certificados import CertificadoAdmin, PlantillaCertificadoAdmin
from core.admin.plantillas import PlantillaDashboardAdmin
from core.models import Campana, Cliente, Curso, Estudiante, Plantilla
from core.models_certificados import Certificado, PlantillaCertificado


@override_settings(
    SECURE_SSL_REDIRECT=False,
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
)
class AdminCampanaCertTabsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('ux_admin', 'u@t.com', 'pass12345')
        self.cliente = Cliente.objects.create(
            nombre='Org UX',
            contacto_principal='Ana',
            email='ux@test.com',
            telefono='573001110033',
            activo=True,
            fecha_fin_suscripcion='2099-12-31',
        )
        self.curso = Curso.objects.create(
            nombre='Curso UX', descripcion='d', cliente=self.cliente, activo=True,
        )

    def _fieldset_titles(self, admin_cls, model):
        adm = admin_cls(model, site)
        return [fs[0] for fs in adm.fieldsets]

    def test_campana_fieldsets_tabs_sin_emoji(self):
        titles = self._fieldset_titles(CampanaAdmin, Campana)
        self.assertIn('Datos', titles)
        self.assertIn('Mensaje Twilio', titles)
        self.assertIn('Audiencia', titles)
        self.assertTrue(all('📝' not in (t or '') and '🚀' not in (t or '') for t in titles))
        for name, opts in CampanaAdmin.fieldsets:
            self.assertIn('tab', opts.get('classes', []))

    def test_plantilla_mensaje_fieldsets_tabs(self):
        titles = self._fieldset_titles(PlantillaDashboardAdmin, Plantilla)
        self.assertIn('Datos', titles)
        self.assertIn('Twilio', titles)
        for name, opts in PlantillaDashboardAdmin.fieldsets:
            self.assertIn('tab', opts.get('classes', []))

    def test_plantilla_certificado_fieldsets_por_modo(self):
        titles = self._fieldset_titles(PlantillaCertificadoAdmin, PlantillaCertificado)
        self.assertEqual(
            titles,
            ['Datos', 'Imagen (marcadores)', 'Diseno eki', 'PDF'],
        )
        for name, opts in PlantillaCertificadoAdmin.fieldsets:
            self.assertIn('tab', opts.get('classes', []))

    def test_plantilla_link_usa_learning(self):
        est = Estudiante.objects.create(
            nombre='Luxia Smoke',
            telefono='573026480629',
            cliente=self.cliente,
            activo=True,
        )
        cert = Certificado(
            estudiante=est,
            curso=self.curso,
            codigo_verificacion='TESTUX01',
        )
        adm = CertificadoAdmin(Certificado, site)
        html = adm.plantilla_link(cert)
        self.assertIn('/admin/learning/plantillacertificado/', str(html))
        self.assertNotIn('/admin/core/plantillacertificado/', str(html))

    def test_campana_change_form_200(self):
        camp = Campana.objects.create(
            nombre='Camp UX',
            cliente=self.cliente,
            template_twilio_id='HXtestfake000000000000000000000',
        )
        self.client.force_login(self.user)
        r = self.client.get(reverse('admin:core_campana_change', args=[camp.pk]))
        self.assertEqual(r.status_code, 200)
        body = r.content.decode('utf-8')
        self.assertIn('Mensaje Twilio', body)
        self.assertNotIn('📨 Template de Twilio', body)

    def test_plantilla_certificado_change_form_200(self):
        plant = PlantillaCertificado.objects.create(
            nombre='Plant UX',
            curso=self.curso,
            cliente=self.cliente,
            modo_plantilla='imagen',
            activa=True,
        )
        self.client.force_login(self.user)
        r = self.client.get(
            reverse('admin:learning_plantillacertificado_change', args=[plant.pk])
        )
        self.assertEqual(r.status_code, 200)
        body = r.content.decode('utf-8')
        self.assertIn('Imagen (marcadores)', body)
        self.assertIn('Vista previa', body)
