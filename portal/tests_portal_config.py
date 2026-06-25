from django.contrib.auth.models import User
from django.test import Client, TestCase

from core.models import Cliente, Curso, Modulo
from formulario.models import FlujoPregunta, TipoFormulario
from portal.middleware import PORTAL_SESSION_KEY
from portal.models import PortalUsuario


class PortalGeiNatConfigTests(TestCase):
    def setUp(self):
        self.org_gei = Cliente.objects.create(
            nombre='Org GEI',
            contacto_principal='A',
            email='geiorg@test.com',
            telefono='573001100001',
            activo=True,
            tipo_proyecto='gei',
        )
        self.org_nat = Cliente.objects.create(
            nombre='Org Nat',
            contacto_principal='B',
            email='natorg@test.com',
            telefono='573001100002',
            activo=True,
            tipo_proyecto='nat',
        )
        curso = Curso.objects.create(cliente=self.org_gei, nombre='Curso GEI', activo=True)
        modulo = Modulo.objects.create(curso=curso, numero=4, titulo='Mod 4')
        self.formulario = TipoFormulario.objects.create(
            nombre='Inventario finca',
            curso=curso,
            modulo=modulo,
            cliente=self.org_gei,
            activo=True,
        )
        FlujoPregunta.objects.create(
            formulario=self.formulario,
            orden=1,
            campo_destino='nombre_finca',
            pregunta_texto='¿Cómo se llama su finca?',
            tipo_dato='text',
        )

        admin_gei = User.objects.create_user('admin_gei', password='x')
        admin_nat = User.objects.create_user('admin_nat', password='x')
        viewer = User.objects.create_user('viewer_gei', password='x')
        PortalUsuario.objects.create(user=admin_gei, organizacion=self.org_gei, rol='admin')
        PortalUsuario.objects.create(user=admin_nat, organizacion=self.org_nat, rol='admin')
        PortalUsuario.objects.create(user=viewer, organizacion=self.org_gei, rol='viewer')

        self.http_admin_gei = Client()
        self._login(self.http_admin_gei, admin_gei)
        self.http_viewer = Client()
        self._login(self.http_viewer, viewer)
        self.http_admin_nat = Client()
        self._login(self.http_admin_nat, admin_nat)

    def _login(self, http, user):
        session = http.session
        session[PORTAL_SESSION_KEY] = PortalUsuario.objects.get(user=user).pk
        session.save()

    def test_gei_formularios_admin(self):
        r = self.http_admin_gei.get('/portal/gei/formularios/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Inventario finca')

    def test_gei_formularios_viewer_puede_ver(self):
        r = self.http_viewer.get('/portal/gei/formularios/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Inventario finca')

    def test_gei_editar_pregunta(self):
        paso = self.formulario.flujo_pasos.first()
        r = self.http_admin_gei.post(
            f'/portal/gei/formularios/{self.formulario.pk}/',
            {f'paso_{paso.pk}_pregunta_texto': 'Nombre de la finca, por favor'},
        )
        self.assertEqual(r.status_code, 200)
        paso.refresh_from_db()
        self.assertEqual(paso.pregunta_texto, 'Nombre de la finca, por favor')

    def test_nat_documentos_pagina(self):
        r = self.http_admin_nat.get('/portal/nat/documentos/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Base de conocimiento Nat')

    def test_nat_sin_modulo_cursos_redirige(self):
        r = self.http_admin_nat.get('/portal/cursos/')
        self.assertEqual(r.status_code, 302)
