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
        for label in (
            'Uso de plataforma', 'Desarrollo de habilidades', 'Retención', 'Impacto',
            'Cobertura', 'Métricas detalladas', 'Reportes',
        ):
            self.assertIn(label, html)
        sub = html.split('id="analitica-sub"', 1)[1].split('</div>', 1)[0]
        self.assertLess(sub.find('Impacto'), sub.find('Cobertura'))
        self.assertNotIn('href="/portal/timeline/"', html)
        uso = html.split('id="ana-uso"', 1)[1].split('id="ana-habilidades"', 1)[0]
        hab = html.split('id="ana-habilidades"', 1)[1].split('id="ana-retencion"', 1)[0]
        self.assertNotIn('/portal/gamificacion/', uso)
        self.assertNotIn('/portal/certificados/', uso)
        self.assertNotIn('/portal/cobertura/', uso)
        self.assertIn('/portal/certificados/', hab)
        self.assertLess(hab.find('/portal/certificados/'), hab.find('/portal/gamificacion/'))
        self.assertIn('id="analitica-sub"', html)
        self.assertIn('analitica-toggle', html)

    def test_fabrica_abre_la_ficha_del_programa(self):
        self._login()
        r = self.http.get('/portal/cursos/')
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn('https://www.eki.com.co/programas/emprendimiento-agro-rural', html)
        self.assertIn('https://www.eki.com.co/programas/maquinaria-herramientas-agro', html)
        self.assertIn('https://www.eki.com.co/programas/comercializacion-ventas', html)
        self.assertIn('https://www.eki.com.co/programas/agricultura-digital-ia', html)
        self.assertIn('https://www.eki.com.co/programas/modelo-negocio-rural-sostenible', html)
        self.assertIn('https://www.eki.com.co/programas/comercializacion-y-ventas', html)
        self.assertIn('https://www.eki.com.co/programas/gestion-costos-agropecuarios', html)
        self.assertIn('https://www.eki.com.co/programas/tome-las-riendas', html)
        self.assertIn('https://www.eki.com.co/cursos/capital-humano-10x', html)
        self.assertIn('https://www.eki.com.co/cursos/coaching-productividad-liderazgo-campo', html)
        self.assertNotIn('course-engine', html)
        self.assertNotIn('Nuevo curso', html)
        self.assertNotIn(f'/portal/cursos/{self.curso.pk}/flujo/', html)

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
        self.assertFalse(nuevo.publicado_wa)
        self.assertTrue(nuevo.secciones.exists())
        self.assertTrue(nuevo.pasos.exists())
        self.assertFalse(nuevo.pasos.filter(activo=True).exists())
