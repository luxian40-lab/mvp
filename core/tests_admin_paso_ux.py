"""QA/regresión: formset Microcontenidos (filas vacías, URL, upload)."""
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase

from core.admin._common import guardar_upload_admin_media
from core.admin.cursos import PasoModuloInline
from core.models import Curso, Modulo, PasoModulo, SeccionModulo
from django.core.exceptions import ValidationError


class PasoModuloAdminUxTests(TestCase):
    def setUp(self):
        self.curso = Curso.objects.create(
            nombre='QA admin UX micros',
            descripcion='d',
            dias_espera_entre_modulos=0,
        )
        self.mod = Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='Clase 1',
            descripcion='d',
            contenido='Bienvenidos',
            duracion_dias=7,
        )
        self.sec = SeccionModulo.objects.create(
            modulo=self.mod, orden=1, titulo='Clase 1', activa=True
        )
        self.paso = PasoModulo.objects.create(
            modulo=self.mod,
            seccion=self.sec,
            orden=1,
            titulo='Bienvenida',
            tipo=PasoModulo.TIPO_CONTENIDO,
            contenido='hola',
            activo=False,
        )
        User = get_user_model()
        self.user = User.objects.create_superuser('qa_ux', 'qa@test.com', 'pass')
        self.request = RequestFactory().get('/')
        self.request.user = self.user
        inline = PasoModuloInline(Modulo, AdminSite())
        self.FormSet = inline.get_formset(request=self.request, obj=self.mod)
        self.prefix = self.FormSet.get_default_prefix()

    def _base(self):
        p = self.prefix
        return {
            'contenido': 'Bienvenidos',
            f'{p}-TOTAL_FORMS': '1',
            f'{p}-INITIAL_FORMS': '1',
            f'{p}-MIN_NUM_FORMS': '0',
            f'{p}-MAX_NUM_FORMS': '1000',
            f'{p}-0-id': str(self.paso.pk),
            f'{p}-0-modulo': str(self.mod.pk),
            f'{p}-0-seccion': str(self.sec.pk),
            f'{p}-0-orden': '1',
            f'{p}-0-titulo': 'Bienvenida',
            f'{p}-0-tipo': PasoModulo.TIPO_CONTENIDO,
            f'{p}-0-contenido': 'hola',
            f'{p}-0-media_url': '',
        }

    def test_fila_extra_vacia_con_tipo_default_no_bloquea(self):
        """P0: «Agregar otro» vacío no debe exigir sección."""
        d = self._base()
        p = self.prefix
        d[f'{p}-TOTAL_FORMS'] = '2'
        d.update(
            {
                f'{p}-1-modulo': str(self.mod.pk),
                f'{p}-1-seccion': '',
                f'{p}-1-orden': '2',
                f'{p}-1-titulo': '',
                f'{p}-1-tipo': PasoModulo.TIPO_CONTENIDO,
                f'{p}-1-contenido': '',
                f'{p}-1-media_url': '',
            }
        )
        fs = self.FormSet(d, instance=self.mod)
        self.assertTrue(fs.is_valid(), fs.errors + list(fs.non_form_errors()))

    def test_sin_seccion_en_paso_lleno_falla_con_resumen(self):
        d = self._base()
        d[f'{self.prefix}-0-seccion'] = ''
        fs = self.FormSet(d, instance=self.mod)
        self.assertFalse(fs.is_valid())
        joined = ' '.join(str(e) for e in fs.non_form_errors())
        self.assertIn('sección', joined.lower())

    def test_media_url_nombre_archivo_mensaje_claro(self):
        d = self._base()
        d[f'{self.prefix}-0-media_url'] = 'archivo.mp4'
        fs = self.FormSet(d, instance=self.mod)
        self.assertFalse(fs.is_valid())
        joined = ' '.join(
            str(e)
            for form in fs.forms
            for errs in form.errors.values()
            for e in errs
        ) + ' '.join(str(e) for e in fs.non_form_errors())
        self.assertTrue(
            'URL' in joined or 'url' in joined.lower() or 'archivo' in joined.lower(),
            joined,
        )

    def test_https_ok(self):
        d = self._base()
        d[f'{self.prefix}-0-media_url'] = (
            'https://eki-produccion.s3.us-east-2.amazonaws.com/media/x.mp4'
        )
        fs = self.FormSet(d, instance=self.mod)
        self.assertTrue(fs.is_valid(), fs.errors + list(fs.non_form_errors()))

    def test_mp4_corto_sin_ftyp_rechazado(self):
        with self.assertRaises(ValidationError):
            guardar_upload_admin_media(
                SimpleUploadedFile('roto.mp4', b'XXXX', content_type='video/mp4'),
                carpeta='modulos/pasos',
                prefix='test',
            )

    def test_paso_nuevo_sin_orden_en_post_es_valido(self):
        """Regresión Agrosavia: orden oculto vacío no debe bloquear guardado/upload."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.forms import inlineformset_factory
        from core.admin.cursos import PasoModuloForm, PasoModuloInlineFormSet

        PasoModulo.objects.filter(modulo=self.mod).delete()
        # Minimal PNG
        png = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
            b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00'
            b'\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        p = self.prefix
        data = {
            'contenido': 'Bienvenidos',
            f'{p}-TOTAL_FORMS': '1',
            f'{p}-INITIAL_FORMS': '0',
            f'{p}-MIN_NUM_FORMS': '0',
            f'{p}-MAX_NUM_FORMS': '1000',
            f'{p}-0-modulo': str(self.mod.pk),
            f'{p}-0-seccion': str(self.sec.pk),
            # orden INTENCIONALMENTE ausente (bug Unfold hide_ordering_field)
            f'{p}-0-titulo': 'microcontenido4',
            f'{p}-0-tipo': PasoModulo.TIPO_CONTENIDO,
            f'{p}-0-contenido': '',
            f'{p}-0-media_url': '',
            f'{p}-0-activo': 'on',
        }
        files = {
            f'{p}-0-media_file_upload': SimpleUploadedFile(
                'senales.png', png, content_type='image/png'
            ),
        }
        FormSet = inlineformset_factory(
            Modulo,
            PasoModulo,
            form=PasoModuloForm,
            formset=PasoModuloInlineFormSet,
            extra=0,
            can_delete=True,
            fk_name='modulo',
        )
        fs = FormSet(data, files, instance=self.mod, prefix=p)
        self.assertTrue(fs.is_valid(), list(fs.non_form_errors()) + [dict(f.errors) for f in fs.forms])
        objs = fs.save()
        self.assertEqual(len(objs), 1)
        self.assertTrue(objs[0].orden >= 1)
        self.assertTrue(
            (objs[0].media_url or '').startswith('http')
            or (objs[0].media_url or '').startswith('/')
        )

    def test_dos_nuevos_con_pasos_existentes_no_duplican_orden(self):
        """Regresión prod: «dato duplicado para orden» al agregar micros 4 y 5."""
        from django.db import transaction
        from django.forms import inlineformset_factory
        from core.admin.cursos import PasoModuloForm, PasoModuloInlineFormSet
        from core.orden_bloques import preparar_ordenes_temporales, renumerar_orden_1_based

        PasoModulo.objects.create(
            modulo=self.mod, seccion=self.sec, orden=2, titulo='p2',
            tipo=PasoModulo.TIPO_CONTENIDO, contenido='b', activo=True,
        )
        PasoModulo.objects.create(
            modulo=self.mod, seccion=self.sec, orden=3, titulo='p3',
            tipo=PasoModulo.TIPO_CONTENIDO, contenido='c', activo=True,
        )
        existing = list(PasoModulo.objects.filter(modulo=self.mod).order_by('orden', 'id'))
        p = self.prefix
        data = {
            'contenido': 'Bienvenidos',
            f'{p}-TOTAL_FORMS': '5',
            f'{p}-INITIAL_FORMS': '3',
            f'{p}-MIN_NUM_FORMS': '0',
            f'{p}-MAX_NUM_FORMS': '1000',
        }
        for i, paso in enumerate(existing):
            data.update({
                f'{p}-{i}-id': str(paso.pk),
                f'{p}-{i}-modulo': str(self.mod.pk),
                f'{p}-{i}-seccion': str(self.sec.pk),
                f'{p}-{i}-orden': str(paso.orden),
                f'{p}-{i}-titulo': paso.titulo,
                f'{p}-{i}-tipo': paso.tipo,
                f'{p}-{i}-contenido': paso.contenido,
                f'{p}-{i}-media_url': '',
                f'{p}-{i}-activo': 'on',
            })
        # Nuevos con orden DUPLICADO (como Unfold / idx+1 chocando con BD)
        for i, titulo in ((3, 'microcontenido4'), (4, 'microcontenido5')):
            data.update({
                f'{p}-{i}-modulo': str(self.mod.pk),
                f'{p}-{i}-seccion': str(self.sec.pk),
                f'{p}-{i}-orden': '1',
                f'{p}-{i}-titulo': titulo,
                f'{p}-{i}-tipo': PasoModulo.TIPO_CONTENIDO,
                f'{p}-{i}-contenido': 'img',
                f'{p}-{i}-media_url': '',
                f'{p}-{i}-activo': 'on',
            })
        FormSet = inlineformset_factory(
            Modulo, PasoModulo, form=PasoModuloForm, formset=PasoModuloInlineFormSet,
            extra=0, can_delete=True, fk_name='modulo',
        )
        fs = FormSet(data, instance=self.mod, prefix=p)
        self.assertTrue(
            fs.is_valid(),
            list(fs.non_form_errors()) + [dict(f.errors) for f in fs.forms],
        )
        with transaction.atomic():
            preparar_ordenes_temporales(PasoModulo, self.mod.pk)
            fs.save()
            renumerar_orden_1_based(PasoModulo, self.mod.pk)
        self.assertEqual(PasoModulo.objects.filter(modulo=self.mod).count(), 5)
        ordenes = list(
            PasoModulo.objects.filter(modulo=self.mod)
            .order_by('orden')
            .values_list('orden', flat=True)
        )
        self.assertEqual(ordenes, [1, 2, 3, 4, 5])
class SeccionModuloAdminUxTests(TestCase):
    """Regresión: bloques nuevos no guardaban (orden oculto / duplicado)."""

    def setUp(self):
        self.curso = Curso.objects.create(
            nombre='QA admin UX bloques',
            descripcion='d',
            dias_espera_entre_modulos=0,
        )
        self.mod = Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='Muestra',
            descripcion='d',
            contenido='ok',
            duracion_dias=7,
        )
        self.sec = SeccionModulo.objects.create(
            modulo=self.mod, orden=1, titulo='Tome la muestra correcta', activa=True
        )

    def test_bloque_nuevo_sin_orden_guarda(self):
        from django.db import transaction
        from django.forms import inlineformset_factory
        from core.admin.cursos import SeccionModuloForm, SeccionModuloInlineFormSet
        from core.orden_bloques import preparar_ordenes_temporales, renumerar_orden_1_based

        p = 'secciones'
        data = {
            f'{p}-TOTAL_FORMS': '2',
            f'{p}-INITIAL_FORMS': '1',
            f'{p}-MIN_NUM_FORMS': '0',
            f'{p}-MAX_NUM_FORMS': '1000',
            f'{p}-0-id': str(self.sec.pk),
            f'{p}-0-modulo': str(self.mod.pk),
            f'{p}-0-orden': '1',
            f'{p}-0-titulo': self.sec.titulo,
            f'{p}-0-activa': 'on',
            f'{p}-1-modulo': str(self.mod.pk),
            f'{p}-1-orden': '1',
            f'{p}-1-titulo': 'Los errores más comunes al tomar una muestra.',
            f'{p}-1-activa': 'on',
        }
        FormSet = inlineformset_factory(
            Modulo,
            SeccionModulo,
            form=SeccionModuloForm,
            formset=SeccionModuloInlineFormSet,
            extra=0,
            can_delete=True,
            fk_name='modulo',
        )
        fs = FormSet(data, instance=self.mod, prefix=p)
        self.assertTrue(
            fs.is_valid(),
            list(fs.non_form_errors()) + [dict(f.errors) for f in fs.forms],
        )
        with transaction.atomic():
            preparar_ordenes_temporales(SeccionModulo, self.mod.pk)
            fs.save()
            renumerar_orden_1_based(SeccionModulo, self.mod.pk)
        self.assertEqual(SeccionModulo.objects.filter(modulo=self.mod).count(), 2)
        ordenes = list(
            SeccionModulo.objects.filter(modulo=self.mod)
            .order_by('orden')
            .values_list('orden', flat=True)
        )
        self.assertEqual(ordenes, [1, 2])

    def test_fila_extra_bloque_vacia_no_bloquea(self):
        from django.forms import inlineformset_factory
        from core.admin.cursos import SeccionModuloForm, SeccionModuloInlineFormSet

        p = 'secciones'
        data = {
            f'{p}-TOTAL_FORMS': '2',
            f'{p}-INITIAL_FORMS': '1',
            f'{p}-MIN_NUM_FORMS': '0',
            f'{p}-MAX_NUM_FORMS': '1000',
            f'{p}-0-id': str(self.sec.pk),
            f'{p}-0-modulo': str(self.mod.pk),
            f'{p}-0-orden': '1',
            f'{p}-0-titulo': self.sec.titulo,
            f'{p}-0-activa': 'on',
            f'{p}-1-modulo': str(self.mod.pk),
            f'{p}-1-orden': '',
            f'{p}-1-titulo': '',
            f'{p}-1-activa': 'on',
        }
        FormSet = inlineformset_factory(
            Modulo,
            SeccionModulo,
            form=SeccionModuloForm,
            formset=SeccionModuloInlineFormSet,
            extra=0,
            can_delete=True,
            fk_name='modulo',
        )
        fs = FormSet(data, instance=self.mod, prefix=p)
        self.assertTrue(fs.is_valid(), list(fs.non_form_errors()) + [dict(f.errors) for f in fs.forms])
