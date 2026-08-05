"""Admin Estudiante: inscripción manual a curso al guardar."""
from __future__ import annotations

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from core.admin.estudiantes import EstudianteAdmin, EstudianteAdminForm
from core.models import Cliente, Curso, Estudiante, Modulo, ProgresoEstudiante


class EstudianteAdminInscripcionManualTests(TestCase):
    def setUp(self):
        self.cli = Cliente.objects.create(
            nombre='Org Manual',
            contacto_principal='a',
            email='manual@example.com',
            telefono='573009990001',
        )
        self.curso = Curso.objects.create(
            nombre='Curso Manual Clases',
            descripcion='d',
            cliente=self.cli,
            modo_aula=Curso.MODO_AULA_CLASES,
            activo=True,
        )
        Modulo.objects.create(curso=self.curso, numero=1, titulo='C1', contenido='x')
        self.admin = EstudianteAdmin(Estudiante, AdminSite())
        self.user = get_user_model().objects.create_superuser(
            'admin_insc', 'a@x.co', 'pass12345',
        )
        self.rf = RequestFactory()

    def test_form_lista_cursos_del_cliente(self):
        form = EstudianteAdminForm(
            data={
                'tipo_documento': 'CC',
                'cedula': 'MANUAL01',
                'nombre': 'Ana Manual',
                'telefono': '573009990002',
                'cliente': str(self.cli.pk),
                'activo': True,
                'cursos_a_inscribir': [str(self.curso.pk)],
            },
        )
        self.assertIn(self.curso, form.fields['cursos_a_inscribir'].queryset)

    def test_save_model_inscribe(self):
        est = Estudiante.objects.create(
            tipo_documento='CC',
            cedula='MANUAL02',
            nombre='Luis Manual',
            telefono='573009990003',
            cliente=self.cli,
            activo=True,
        )
        form = EstudianteAdminForm(
            data={
                'tipo_documento': 'CC',
                'cedula': est.cedula,
                'nombre': est.nombre,
                'telefono': est.telefono,
                'cliente': str(self.cli.pk),
                'activo': True,
                'cursos_a_inscribir': [str(self.curso.pk)],
            },
            instance=est,
        )
        self.assertTrue(form.is_valid(), form.errors)
        request = self.rf.post('/admin/')
        request.user = self.user
        setattr(request, 'session', {})
        from django.contrib.messages.storage.fallback import FallbackStorage
        setattr(request, '_messages', FallbackStorage(request))
        self.admin.save_model(request, est, form, change=True)
        self.assertTrue(
            ProgresoEstudiante.objects.filter(estudiante=est, curso=self.curso).exists()
        )
