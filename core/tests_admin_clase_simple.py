"""Clase simple: form módulo → sección + 1er paso."""
from types import SimpleNamespace

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, TestCase

from core.admin.cursos import (
    CursoAdmin,
    ModuloAdminForm,
    aplicar_clase_simple_desde_form,
    asegurar_seccion_y_primer_paso,
    sembrar_plantilla_modulo,
)
from core.models import Curso, Modulo, PasoModulo, SeccionModulo


class ClaseSimpleAdminTests(TestCase):
    def setUp(self):
        self.curso = Curso.objects.create(
            nombre='Curso clases QA',
            descripcion='d',
            dias_espera_entre_modulos=0,
            modo_aula=Curso.MODO_AULA_CLASES,
        )
        self.mod = Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='Clase 1',
            descripcion='d',
            contenido='',
            duracion_dias=7,
        )

    def _form_data(self, **overrides):
        data = {
            'curso': str(self.curso.pk),
            'numero': '1',
            'titulo': 'Clase 1',
            'descripcion': 'd',
            'contenido': 'legacy ok',
            'modo_entrega': Modulo.MODO_ENTREGA_LEGACY,
            'duracion_dias': '7',
            'video_resolucion': '360p',
            'puntaje_minimo_aprobacion': '70',
            'secciones_por_listo': '1',
            'facilitador_checkpoint': 'auto',
            'clase_texto': '',
            'clase_url': '',
        }
        data.update(overrides)
        return data

    def test_sembrar_modo_clases_un_paso(self):
        created = sembrar_plantilla_modulo(self.mod)
        self.assertTrue(created['seccion'] or SeccionModulo.objects.filter(modulo=self.mod).exists())
        self.assertEqual(PasoModulo.objects.filter(modulo=self.mod).count(), 1)
        paso = PasoModulo.objects.get(modulo=self.mod)
        self.assertFalse(paso.requiere_listo_para_avanzar)

    def test_aplicar_clase_simple_texto_y_url(self):
        fake = SimpleNamespace(
            instance=self.mod,
            cleaned_data={
                'clase_texto': 'Hola clase',
                'clase_url': 'https://eki-produccion.s3.us-east-2.amazonaws.com/media/x.mp4',
                'clase_activo': True,
                'titulo': 'Clase 1 - bienvenida',
            },
            _clase_pending_media_url=None,
        )
        self.mod.titulo = 'Clase 1 - bienvenida'
        self.mod.save(update_fields=['titulo'])
        paso = aplicar_clase_simple_desde_form(fake)
        self.assertIsNotNone(paso)
        paso.refresh_from_db()
        self.assertEqual(paso.contenido, 'Hola clase')
        self.assertTrue(paso.activo)
        self.assertIn('https://', paso.media_url)
        self.assertEqual(PasoModulo.objects.filter(modulo=self.mod).count(), 1)

    def test_aplicar_no_borra_pasos_extra(self):
        sec, p1 = asegurar_seccion_y_primer_paso(self.mod)
        PasoModulo.objects.create(
            modulo=self.mod,
            seccion=sec,
            orden=2,
            titulo='Extra WA',
            contenido='segundo',
            activo=True,
        )
        fake = SimpleNamespace(
            instance=self.mod,
            cleaned_data={
                'clase_texto': 'solo primero',
                'clase_url': '',
                'clase_activo': True,
                'titulo': 'Clase 1',
            },
            _clase_pending_media_url=None,
        )
        aplicar_clase_simple_desde_form(fake)
        self.assertEqual(PasoModulo.objects.filter(modulo=self.mod).count(), 2)
        p1.refresh_from_db()
        self.assertEqual(p1.contenido, 'solo primero')

    def test_clase_url_nombre_archivo_invalido(self):
        form = ModuloAdminForm(data=self._form_data(clase_url='video.mp4'), instance=self.mod)
        self.assertFalse(form.is_valid())
        self.assertIn('clase_url', form.errors)

    def test_añadir_clase_rapida_action(self):
        User = get_user_model()
        user = User.objects.create_superuser('ops', 'o@test.com', 'pass')
        factory = RequestFactory()
        request = factory.post('/admin/')
        request.user = user
        setattr(request, 'session', {})
        setattr(request, '_messages', FallbackStorage(request))

        admin = CursoAdmin(Curso, AdminSite())
        resp = admin.añadir_clase_rapida(request, Curso.objects.filter(pk=self.curso.pk))
        self.assertEqual(resp.status_code, 302)
        mods = list(Modulo.objects.filter(curso=self.curso).order_by('numero'))
        self.assertGreaterEqual(len(mods), 2)
        nuevo = mods[-1]
        self.assertEqual(nuevo.pasos.count(), 1)
        self.assertTrue(nuevo.secciones.exists())

    def test_form_clase_sin_legacy_pasa_model_clean(self):
        """P0: form OK con contenido vacío + Clase; Modulo.clean no choca."""
        form = ModuloAdminForm(
            data=self._form_data(
                contenido='',
                clase_texto='Material de clase',
                clase_activo='on',
            ),
            instance=self.mod,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertTrue(getattr(form.instance, '_eki_skip_contenido_model_clean', False))
        form.instance.contenido = ''
        form.instance.full_clean()  # no debe exigir contenido legacy

    def test_widget_archivo_es_unfold(self):
        from unfold.widgets import UnfoldAdminFileFieldWidget

        form = ModuloAdminForm(instance=self.mod)
        self.assertIsInstance(form.fields['clase_archivo'].widget, UnfoldAdminFileFieldWidget)
        from core.admin.cursos import PasoModuloForm

        self.assertIsInstance(
            PasoModuloForm().fields['media_file_upload'].widget,
            UnfoldAdminFileFieldWidget,
        )

    def test_aplicar_sin_tocar_clase_no_pisa_materiales(self):
        """P1: Guardar sin tocar Clase no sobrescribe el 1er paso de Materiales."""
        sec, p1 = asegurar_seccion_y_primer_paso(self.mod)
        p1.contenido = 'Texto desde Materiales'
        p1.media_url = 'https://eki-produccion.s3.us-east-2.amazonaws.com/media/a.mp4'
        p1.activo = True
        p1.save()
        fake = SimpleNamespace(
            instance=self.mod,
            cleaned_data={
                'clase_texto': '',
                'clase_url': '',
                'clase_activo': False,
                'titulo': 'Clase 1',
            },
            changed_data=['descripcion'],
            _clase_pending_media_url=None,
        )
        result = aplicar_clase_simple_desde_form(fake)
        self.assertIsNone(result)
        p1.refresh_from_db()
        self.assertEqual(p1.contenido, 'Texto desde Materiales')
        self.assertTrue(p1.activo)

    def test_materiales_contenido_no_lo_pisa_clase_vacia(self):
        """Regresión Agrosavia: texto en Materiales no se borra por Clase al Guardar."""
        from types import SimpleNamespace
        from core.admin.cursos import aplicar_clase_simple_desde_form

        sec, p1 = asegurar_seccion_y_primer_paso(self.mod)
        p1.contenido = 'Texto largo Materiales bienvenida'
        p1.save(update_fields=['contenido'])

        class _FakePasoForm:
            instance = p1
            changed_data = ['contenido']
            cleaned_data = {'contenido': 'Texto largo Materiales bienvenida', 'DELETE': False}

            def has_changed(self):
                return True

        class _FakeFS:
            model = PasoModulo
            forms = [_FakePasoForm()]

        form = SimpleNamespace(
            instance=self.mod,
            cleaned_data={
                'clase_texto': '',
                'clase_url': '',
                'clase_activo': True,
                'titulo': 'Clase 1',
            },
            changed_data=['clase_activo'],
            _clase_pending_media_url=None,
        )
        aplicar_clase_simple_desde_form(form, formsets=[_FakeFS()])
        p1.refresh_from_db()
        self.assertEqual(p1.contenido, 'Texto largo Materiales bienvenida')

    def test_clase_no_sube_s3_si_ya_hay_errores(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from unittest.mock import patch

        png = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
            b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00'
            b'\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        data = self._form_data(clase_url='video.mp4')  # inválida → error
        files = {
            'clase_archivo': SimpleUploadedFile('x.png', png, content_type='image/png'),
        }
        with patch('core.admin.cursos.guardar_upload_admin_media') as mock_up:
            form = ModuloAdminForm(data=data, files=files, instance=self.mod)
            self.assertFalse(form.is_valid())
            mock_up.assert_not_called()
            self.assertIsNone(getattr(form, '_clase_pending_media_url', None))
