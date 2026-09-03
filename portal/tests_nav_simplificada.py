"""Navegación portal simplificada + estructura de curso."""

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from core.models import Cliente, Curso, Modulo
from portal.models import PortalUsuario


@override_settings(SECURE_SSL_REDIRECT=False)
class PortalNavSimplificadaTests(TestCase):
    def setUp(self):
        self.http = Client()
        self.org = Cliente.objects.create(
            nombre='Org Nav',
            contacto_principal='A',
            email='nav@test.com',
            telefono='573001112233',
            activo=True,
            portal_productos='cursos',
        )
        self.curso = Curso.objects.create(nombre='Curso Nav', cliente=self.org, activo=True)
        Modulo.objects.create(
            curso=self.curso, numero=1, titulo='Intro', descripcion='d', contenido='',
        )
        self.user = User.objects.create_user('nav_admin', 'n@t.com', 'pass')
        PortalUsuario.objects.create(user=self.user, organizacion=self.org, rol='admin')

    def _login(self):
        self.http.post('/portal/login/', {'username': 'nav_admin', 'password': 'pass'})

    def test_menu_cinco_items_y_sin_faq_ni_conocimiento(self):
        self._login()
        r = self.http.get('/portal/dashboard/')
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn('Fábrica de competencias', html)
        self.assertIn('Analítica', html)
        self.assertIn('Soporte', html)
        self.assertIn('Configuración', html)
        self.assertNotIn('>Conocimiento IA<', html)
        self.assertNotIn('>FAQ organización<', html)
        # Ya no van sueltos en el sidebar
        self.assertNotIn('>Centro de Éxito</span>', html)
        self.assertNotIn('>Métricas detalladas</span>', html)

    def test_hub_analitica_contiene_destinos(self):
        self._login()
        r = self.http.get('/portal/analitica/')
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        for label in ('Centro de Éxito', 'Cobertura', 'Métricas detalladas', 'Reportes', 'Actividad', 'Gamificación'):
            self.assertIn(label, html)

    def test_ver_curso_solo_estructura(self):
        self._login()
        r = self.http.get(f'/portal/cursos/{self.curso.pk}/flujo/')
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn('Intro', html)
        self.assertIn('¿Quieres agregar un módulo más?', html)
        self.assertNotIn('Inscritos', html)
        self.assertNotIn('Embudo por módulo', html)

    def test_agregar_modulo(self):
        self._login()
        r = self.http.post(f'/portal/cursos/{self.curso.pk}/modulos/agregar/')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Modulo.objects.filter(curso=self.curso).count(), 2)
        nuevo = Modulo.objects.filter(curso=self.curso).order_by('-numero').first()
        self.assertEqual(nuevo.numero, 2)
