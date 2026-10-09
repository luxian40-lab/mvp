"""Filtro Tipo en Cursos y compras Studio en la ficha del estudiante."""
import uuid

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.models import Cliente, Curso, Estudiante
from core.signals_conocimientos import curso_actualizado
from studio.models import CuentaAula, OrdenItemStudio, OrdenStudio, PublicacionStudio


@override_settings(SECURE_SSL_REDIRECT=False)
class B2CAdminTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        post_save.disconnect(curso_actualizado, sender=Curso)

    @classmethod
    def tearDownClass(cls):
        post_save.connect(curso_actualizado, sender=Curso)
        super().tearDownClass()

    def setUp(self):
        self.tag = uuid.uuid4().hex[:8]
        self.cli = Cliente.objects.create(
            nombre=f'Org B2C {self.tag}',
            contacto_principal='a',
            email=f'b2c-{self.tag}@example.com',
            telefono=f'57315{self.tag[:7]}',
        )
        self.curso_org = Curso.objects.create(
            nombre=f'OrgCurso {self.tag}', descripcion='d', cliente=self.cli, activo=True,
        )
        self.curso_general = Curso.objects.create(
            nombre=f'GeneralCurso {self.tag}', descripcion='d', cliente=None, activo=True,
            catalogo_menu=True,
        )
        self.est = Estudiante.objects.create(
            nombre=f'Ana B2C {self.tag}',
            cedula=f'D{self.tag}',
            telefono=f'57316{self.tag[:7]}',
            cliente=None,
            activo=True,
        )
        self.user = get_user_model().objects.create_superuser(
            f'admin_b2c_{self.tag}', f'b2c-{self.tag}@x.co', 'pass12345',
        )
        self.http = Client()
        self.http.force_login(self.user)

    def test_filtro_tipo_separa_catalogo_general(self):
        url = reverse('admin:core_curso_changelist')
        general = self.http.get(url, {'q': self.tag, 'eki_tipo': 'general'})
        self.assertContains(general, self.curso_general.nombre)
        self.assertNotContains(general, self.curso_org.nombre)
        org = self.http.get(url, {'q': self.tag, 'eki_tipo': 'con_org'})
        self.assertContains(org, self.curso_org.nombre)
        self.assertNotContains(org, self.curso_general.nombre)

    def test_ficha_sin_cuenta_dice_sin_compra(self):
        url = reverse('admin:core_estudiante_change', args=[self.est.pk])
        pagina = self.http.get(url)
        self.assertContains(pagina, 'Sin compra Studio')
        self.assertContains(pagina, 'Compras Studio')

    def test_ficha_muestra_orden_sin_editarla(self):
        cuenta_user = get_user_model().objects.create_user(
            f'studio_{self.tag}', f'studio-{self.tag}@x.co', 'pass12345',
        )
        cuenta = CuentaAula.objects.create(user=cuenta_user, estudiante=self.est)
        pub = PublicacionStudio.objects.create(curso=self.curso_general, precio_cop=50000)
        orden = OrdenStudio.objects.create(
            cuenta=cuenta,
            estado=OrdenStudio.ESTADO_APROBADO,
            monto_cop=50000,
            wompi_referencia=f'wompi-{self.tag}',
        )
        OrdenItemStudio.objects.create(
            orden=orden,
            publicacion=pub,
            curso=self.curso_general,
            precio_cop=50000,
        )
        antes = OrdenStudio.objects.count()
        pagina = self.http.get(reverse('admin:core_estudiante_change', args=[self.est.pk]))
        self.assertContains(pagina, 'Aprobado')
        self.assertContains(pagina, f'wompi-{self.tag}')
        self.assertContains(pagina, '50.000')
        self.assertContains(pagina, self.curso_general.nombre)
        self.assertNotContains(pagina, 'Sin compra Studio')
        self.assertEqual(OrdenStudio.objects.count(), antes)
