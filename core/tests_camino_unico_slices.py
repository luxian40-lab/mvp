"""Slices 1–6: un camino para subir cursos (Clase) sin verse roto."""
from types import SimpleNamespace

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.course_engine.adjuntar_pasos import adjuntar_assets_ce_a_modulo
from core.models import Cliente, Curso, Modulo, PasoModulo, SeccionModulo
from core.module_steps import texto_legacy_whatsapp
from core.modulo_publicacion import evaluar_checklist_publicacion_detalle, publicar_modulo_wa


@override_settings(
    SECURE_SSL_REDIRECT=False,
    EKI_MODULE_BUILDER_BETA=True,
    EKI_MODULE_BUILDER_CURSOS='*',
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
)
class CaminoUnicoAdminClaseTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('cu_staff', 'cu@t.com', 'pass12345')
        self.cliente = Cliente.objects.create(
            nombre='Org Camino',
            contacto_principal='Ana',
            email='cu@test.com',
            telefono='573001110099',
            activo=True,
            fecha_fin_suscripcion='2099-12-31',
        )
        self.curso = Curso.objects.create(
            nombre='Curso Camino',
            descripcion='d',
            cliente=self.cliente,
            activo=True,
        )
        self.mod = Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='Primero',
            descripcion='d',
            contenido='LEGACY_NO_DEBE_SALIR',
            modo_entrega=Modulo.MODO_ENTREGA_PASOS,
            publicado_wa=False,
        )
        self.http = Client()
        self.http.force_login(self.user)

    def test_ficha_clase_es_opt_in_builder_y_conserva_drip_en_dom(self):
        r = self.http.get(
            reverse('admin:core_modulo_change', args=[self.mod.pk]) + '?modo=clase'
        )
        self.assertEqual(r.status_code, 200)
        body = r.content.decode('utf-8')
        self.assertIn('Modo: clase rápida', body)
        self.assertIn('Armar por partes', body)
        self.assertIn('Avanzado (drip, examen, video IA)', body)
        self.assertIn('name="habilitado_desde"', body)
        self.assertIn('name="publicado_wa"', body)
        self.assertNotIn('camino recomendado', body)
        self.assertNotIn('pestañas Estructura + Materiales', body)

    def test_ficha_no_redirige_sola_al_builder(self):
        r = self.http.get(
            reverse('admin:core_modulo_change', args=[self.mod.pk]) + '?modo=clase'
        )
        self.assertEqual(r.status_code, 200)
        self.assertFalse(getattr(r, 'url', None))


class AdjuntarAssetsCeTests(TestCase):
    def setUp(self):
        self.curso = Curso.objects.create(nombre='CE adj', descripcion='d')
        self.mod = Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='M CE',
            descripcion='d',
            contenido='',
            publicado_wa=False,
        )

    def test_crea_pasos_inactivos_sin_publicar(self):
        assets = [
            SimpleNamespace(url='https://s3.example/a.mp4', label='Video CE', tipo='video'),
            SimpleNamespace(url='https://s3.example/b.mp3', label='Audio CE', tipo='podcast'),
        ]
        n = adjuntar_assets_ce_a_modulo(self.mod, assets, activo=False)
        self.assertEqual(n, 2)
        self.mod.refresh_from_db()
        self.assertFalse(self.mod.publicado_wa)
        pasos = list(PasoModulo.objects.filter(modulo=self.mod).order_by('orden'))
        self.assertEqual(len(pasos), 2)
        self.assertTrue(all(not p.activo for p in pasos))
        self.assertEqual(pasos[0].media_url, 'https://s3.example/a.mp4')

    def test_no_duplica_misma_media_url(self):
        asset = SimpleNamespace(url='https://s3.example/dup.mp4', label='V', tipo='video')
        self.assertEqual(adjuntar_assets_ce_a_modulo(self.mod, [asset]), 1)
        self.assertEqual(adjuntar_assets_ce_a_modulo(self.mod, [asset]), 0)
        self.assertEqual(PasoModulo.objects.filter(modulo=self.mod).count(), 1)

    def test_sin_url_no_crea(self):
        n = adjuntar_assets_ce_a_modulo(
            self.mod,
            [SimpleNamespace(url='', label='vacío', tipo='video')],
        )
        self.assertEqual(n, 0)
        self.assertFalse(PasoModulo.objects.filter(modulo=self.mod).exists())


class RuntimeLegacyVsPasosTests(TestCase):
    def test_checklist_ok_con_paso_activo(self):
        curso = Curso.objects.create(nombre='chk ok', descripcion='d')
        mod = Modulo.objects.create(
            curso=curso,
            numero=1,
            titulo='M',
            descripcion='d',
            contenido='',
            modo_entrega=Modulo.MODO_ENTREGA_PASOS,
            publicado_wa=False,
        )
        sec = SeccionModulo.objects.create(modulo=mod, orden=1, titulo='S')
        PasoModulo.objects.create(
            modulo=mod, seccion=sec, orden=1, titulo='P', contenido='micro', activo=True,
        )
        self.assertEqual(texto_legacy_whatsapp(mod), '')
        chk = evaluar_checklist_publicacion_detalle(mod)
        self.assertTrue(chk.ok, chk.errores)
        ok, errs = publicar_modulo_wa(mod)
        self.assertTrue(ok, errs)
        mod.refresh_from_db()
        self.assertTrue(mod.publicado_wa)
