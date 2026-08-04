"""Drag Unfold (ordering_field) + smoke: módulo, microcontenido y plantilla_test.jpg."""
from pathlib import Path

from django.contrib.admin.sites import site
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.test import TestCase, override_settings
from django.urls import reverse

from core.admin.cursos import (
    ArchivoModuloInline,
    ModuloAdmin,
    PasoModuloForm,
    PasoModuloInline,
    SeccionModuloInline,
    sembrar_plantilla_modulo,
)
from core.models import Cliente, Curso, Modulo, PasoModulo, SeccionModulo
from core.orden_bloques import (
    preparar_ordenes_temporales,
    renumerar_orden_1_based,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
PLANTILLA_TEST = REPO_ROOT / 'plantilla_test.jpg'


@override_settings(
    SECURE_SSL_REDIRECT=False,
    MEDIA_ROOT=REPO_ROOT / 'test_media_drag',
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
)
class ModuloDragOrdenTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            nombre='Org Drag',
            contacto_principal='Ana',
            email='drag@test.com',
            telefono='573001110022',
            activo=True,
            fecha_fin_suscripcion='2099-12-31',
        )
        self.curso = Curso.objects.create(
            nombre='Curso Drag',
            descripcion='d',
            cliente=self.cliente,
            activo=True,
        )
        self.admin = ModuloAdmin(Modulo, site)
        self.user = User.objects.create_superuser('drag_admin', 'd@t.com', 'pass12345')

    def test_inlines_tienen_ordering_field(self):
        for inline_cls in (SeccionModuloInline, PasoModuloInline, ArchivoModuloInline):
            self.assertEqual(inline_cls.ordering_field, 'orden')
            self.assertTrue(inline_cls.hide_ordering_field)

    def test_renumerar_tras_indices_0_based_estilo_unfold(self):
        """Unfold JS pone 0,1,2; nosotros persistimos 1,2,3 sin chocar UniqueConstraint."""
        mod = Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='Drag',
            descripcion='d',
            contenido='x',
            modo_entrega=Modulo.MODO_ENTREGA_PASOS,
        )
        s1 = SeccionModulo.objects.create(modulo=mod, orden=1, titulo='A')
        s2 = SeccionModulo.objects.create(modulo=mod, orden=2, titulo='B')
        s3 = SeccionModulo.objects.create(modulo=mod, orden=3, titulo='C')

        # Simula drag: C, A, B → índices Unfold 0,1,2
        with transaction.atomic():
            preparar_ordenes_temporales(SeccionModulo, mod.pk)
            SeccionModulo.objects.filter(pk=s3.pk).update(orden=0)
            SeccionModulo.objects.filter(pk=s1.pk).update(orden=1)
            SeccionModulo.objects.filter(pk=s2.pk).update(orden=2)
            renumerar_orden_1_based(SeccionModulo, mod.pk)

        s1.refresh_from_db()
        s2.refresh_from_db()
        s3.refresh_from_db()
        self.assertEqual(s3.orden, 1)
        self.assertEqual(s1.orden, 2)
        self.assertEqual(s2.orden, 3)

    def test_change_form_expone_drag_unfold(self):
        mod = Modulo.objects.create(
            curso=self.curso,
            numero=2,
            titulo='UI Drag',
            descripcion='d',
            contenido='Contenido suficiente para validación de módulo.',
            modo_entrega=Modulo.MODO_ENTREGA_PASOS,
        )
        sembrar_plantilla_modulo(mod)
        self.client.force_login(self.user)
        r = self.client.get(reverse('admin:core_modulo_change', args=[mod.pk]))
        self.assertEqual(r.status_code, 200)
        body = r.content.decode('utf-8')
        self.assertIn('data-ordering-field="orden"', body)
        self.assertIn('drag_indicator', body)

    def test_crear_modulo_microcontenido_con_plantilla_test_jpg(self):
        self.assertTrue(PLANTILLA_TEST.is_file(), f'Falta archivo de prueba: {PLANTILLA_TEST}')

        mod = Modulo.objects.create(
            curso=self.curso,
            numero=3,
            titulo='Modulo con media',
            descripcion='prueba drag+media',
            contenido='',
            modo_entrega=Modulo.MODO_ENTREGA_PASOS,
        )
        created = sembrar_plantilla_modulo(mod)
        self.assertEqual(created['pasos'], 3)
        paso = mod.pasos.order_by('orden').first()
        self.assertIsNotNone(paso)

        raw = PLANTILLA_TEST.read_bytes()
        upload = SimpleUploadedFile(
            'plantilla_test.jpg',
            raw,
            content_type='image/jpeg',
        )
        form = PasoModuloForm(
            data={
                'modulo': str(mod.pk),
                'seccion': str(paso.seccion_id),
                'orden': str(paso.orden),
                'titulo': 'Micro con imagen',
                'tipo': PasoModulo.TIPO_CONTENIDO,
                'contenido': 'Hola, este microcontenido usa la imagen de pruebas.',
                'media_url': '',
                'activo': True,
                'requiere_listo_para_avanzar': True,
                'eval_opcion_a': '',
                'eval_opcion_b': '',
                'eval_opcion_c': '',
                'eval_opcion_d': '',
                'respuesta_correcta': '',
                'feedback_correcto': '',
                'feedback_incorrecto': '',
                'opciones_json': '',
            },
            files={'media_file_upload': upload},
            instance=paso,
        )
        self.assertTrue(form.is_valid(), form.errors)
        saved = form.save()
        self.assertTrue((saved.media_url or '').strip())
        self.assertIn('plantilla_test', saved.media_url)
        saved.refresh_from_db()
        self.assertTrue(saved.activo)
        self.assertEqual(saved.titulo, 'Micro con imagen')

        # Reordenar pasos estilo Unfold (último al frente) sin UniqueConstraint error
        pasos = list(mod.pasos.order_by('orden', 'id'))
        self.assertEqual(len(pasos), 3)
        with transaction.atomic():
            preparar_ordenes_temporales(PasoModulo, mod.pk)
            # nuevo orden visual: p3, p1, p2 → 0,1,2
            PasoModulo.objects.filter(pk=pasos[2].pk).update(orden=0)
            PasoModulo.objects.filter(pk=pasos[0].pk).update(orden=1)
            PasoModulo.objects.filter(pk=pasos[1].pk).update(orden=2)
            renumerar_orden_1_based(PasoModulo, mod.pk)

        ordenes = list(
            mod.pasos.order_by('orden').values_list('pk', 'orden', 'titulo')
        )
        self.assertEqual([o[1] for o in ordenes], [1, 2, 3])
        self.assertEqual(ordenes[1][0], pasos[0].pk)  # el de la imagen quedó #2
