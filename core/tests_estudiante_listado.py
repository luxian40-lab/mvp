"""Listado admin de Estudiantes: chat, un curso, totales filtrados."""
import uuid
from datetime import timedelta

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.test import Client, RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.signals_conocimientos import curso_actualizado, modulo_actualizado

from core.admin.estudiantes import (
    EstudianteAdmin,
    etiqueta_estado_chat,
)
from core.models import Cliente, Curso, Estudiante, Modulo, ProgresoEstudiante
from core.models_certificados import Certificado


class EtiquetaEstadoChatTests(SimpleTestCase):
    def test_habeas_no_es_curso_completado(self):
        etiqueta, slug = etiqueta_estado_chat('ESPERANDO_HABEAS_DATA')
        self.assertEqual(etiqueta, 'Habeas')
        self.assertEqual(slug, 'habeas')

    def test_chat_finalizado_es_la_maquina(self):
        etiqueta, slug = etiqueta_estado_chat('curso_finalizado')
        self.assertEqual((etiqueta, slug), ('Finalizado', 'finalizado'))
        etiqueta, slug = etiqueta_estado_chat('completado')
        self.assertEqual(slug, 'finalizado')

    def test_activo_y_onboarding(self):
        self.assertEqual(etiqueta_estado_chat('ACTIVO')[0], 'Activo')
        self.assertEqual(etiqueta_estado_chat('nuevo')[0], 'Onboarding')
        self.assertEqual(etiqueta_estado_chat('ESPERANDO_CEDULA')[0], 'Cédula')


@override_settings(SECURE_SSL_REDIRECT=False)
class EstudianteListadoAdminTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        post_save.disconnect(curso_actualizado, sender=Curso)
        post_save.disconnect(modulo_actualizado, sender=Modulo)

    @classmethod
    def tearDownClass(cls):
        post_save.connect(curso_actualizado, sender=Curso)
        post_save.connect(modulo_actualizado, sender=Modulo)
        super().tearDownClass()

    def setUp(self):
        self.tag = uuid.uuid4().hex[:8]
        self.cli = Cliente.objects.create(
            nombre=f'Org Listado {self.tag}',
            contacto_principal='a',
            email=f'listado-{self.tag}@example.com',
            telefono=f'57311{self.tag[:7]}',
        )
        self.curso_lid = self._curso('LiderazgoListadoQa', 5)
        self.curso_sue = self._curso('SuelosListadoQa', 4)
        self.curso_fin = self._curso('BuenasListadoQa', 2)
        self.admin = EstudianteAdmin(Estudiante, AdminSite())
        ahora = timezone.now()
        self.est_dos = self._est(
            f'EkiListadoQa Andreina {self.tag}', f'A{self.tag}', f'57321{self.tag[:7]}',
            self.cli, 'ACTIVO',
        )
        self._prog(
            self.est_dos, self.curso_lid, numero=3,
            cuando=ahora,
        )
        self._prog(
            self.est_dos, self.curso_sue, numero=1,
            cuando=ahora - timedelta(days=10),
        )
        self.est_habeas = self._est(
            f'EkiListadoQa Alexander {self.tag}', f'B{self.tag}', f'57322{self.tag[:7]}',
            self.cli, 'ESPERANDO_HABEAS_DATA',
        )
        prog_fin = self._prog(self.est_habeas, self.curso_fin, numero=1, cuando=ahora)
        prog_fin.completado = True
        prog_fin.save(update_fields=['completado'])
        self.cert = Certificado.objects.create(
            estudiante=self.est_habeas,
            curso=self.curso_fin,
            calificacion_final=90,
            fecha_inicio='2026-01-01',
            fecha_completado='2026-02-01',
            emitido=True,
            fecha_emision=ahora,
        )
        self.est_b2c = self._est(
            f'EkiListadoQa Juan {self.tag}', f'C{self.tag}', f'57323{self.tag[:7]}',
            None, 'ACTIVO',
        )
        self.user = get_user_model().objects.create_superuser(
            f'admin_listado_{self.tag}', f'listado-{self.tag}@x.co', 'pass12345',
        )
        self.http = Client()
        self.http.force_login(self.user)
        self.rf = RequestFactory()

    def _curso(self, nombre, n_mods):
        curso = Curso.objects.create(
            nombre=nombre,
            descripcion='d',
            cliente=self.cli,
            activo=True,
        )
        for i in range(1, n_mods + 1):
            Modulo.objects.create(
                curso=curso,
                numero=i,
                titulo=f'M{i}',
                descripcion='d',
                contenido='x',
            )
        return curso

    def _est(self, nombre, cedula, telefono, cliente, estado):
        return Estudiante.objects.create(
            tipo_documento='CC',
            cedula=cedula,
            nombre=nombre,
            telefono=telefono,
            cliente=cliente,
            activo=True,
            estado_chat=estado,
        )

    def _prog(self, est, curso, numero, cuando):
        modulo = Modulo.objects.get(curso=curso, numero=numero)
        return ProgresoEstudiante.objects.create(
            estudiante=est,
            curso=curso,
            modulo_actual=modulo,
            fecha_ultimo_avance=cuando,
        )

    def _qs(self):
        request = self.rf.get('/admin/core/estudiante/')
        request.user = self.user
        return self.admin.get_queryset(request)

    def test_curso_visible_es_el_mas_reciente_y_suma_el_resto(self):
        est = self._qs().get(pk=self.est_dos.pk)
        html = str(self.admin.curso_celda(est))
        self.assertIn('LiderazgoListadoQa · Mód. 3/5', html)
        self.assertIn('+1', html)
        self.assertNotIn('SuelosListadoQa', html)
        self.assertNotIn('Diploma', html)

    def test_filtro_de_curso_muestra_ese_curso(self):
        est = self._qs().get(pk=self.est_dos.pk)
        self.admin._eki_curso_filter = str(self.curso_sue.pk)
        html = str(self.admin.curso_celda(est))
        self.assertIn('SuelosListadoQa · Mód. 1/4', html)
        self.assertIn('+1', html)
        self.assertNotIn('LiderazgoListadoQa', html)

    def test_habeas_no_se_mezcla_con_curso_completado(self):
        est = self._qs().get(pk=self.est_habeas.pk)
        estado = str(self.admin.estado_chat_celda(est))
        curso = str(self.admin.curso_celda(est))
        self.assertIn('Habeas', estado)
        self.assertNotIn('Finalizado', estado)
        self.assertNotIn('Completado', estado)
        self.assertIn('BuenasListadoQa · Completado', curso)
        self.assertIn('Habeas', curso)
        self.assertIn('Diploma', curso)
        self.assertIn(
            reverse('admin:learning_certificado_change', args=[self.cert.pk]),
            curso,
        )

    def test_diploma_anulado_no_sale(self):
        self.cert.anulado = True
        self.cert.save(update_fields=['anulado'])
        est = self._qs().get(pk=self.est_habeas.pk)
        self.assertNotIn('Diploma', str(self.admin.curso_celda(est)))

    def test_b2c_sin_curso(self):
        est = self._qs().get(pk=self.est_b2c.pk)
        persona = str(self.admin.estudiante_celda(est))
        self.assertIn('B2C', persona)
        self.assertIn(f'+{est.telefono}', persona)
        self.assertNotIn('Chat', persona)
        self.assertIn(est.nombre, persona)
        curso = str(self.admin.curso_celda(est))
        self.assertIn('Sin curso', curso)
        self.assertIn('Chat', curso)
        self.assertIn('Activo', curso)

    def test_changelist_totales_siguen_busqueda_y_filtros(self):
        url = reverse('admin:core_estudiante_changelist')
        r = self.http.get(url, {'q': self.tag})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Buscar por nombre, cédula o WhatsApp')
        self.assertContains(r, 'respetan la búsqueda y los filtros')
        self.assertContains(r, '<strong>3</strong>')
        self.assertContains(r, '2 con organización')
        self.assertContains(r, '1 sin organización')
        self.assertContains(r, 'LiderazgoListadoQa · Mód. 3/5')
        self.assertContains(r, 'Habeas')
        self.assertContains(r, f'+{self.est_dos.telefono}')
        self.assertContains(r, self.cli.nombre)
        self.assertNotContains(r, self.est_dos.cedula)

        por_doc = self.http.get(url, {'q': self.est_dos.cedula})
        self.assertContains(por_doc, 'Andreina')
        self.assertNotContains(por_doc, 'Alexander')

        filtrado = self.http.get(url, {
            'q': self.tag,
            'eki_tipo': 'b2c',
        })
        self.assertContains(filtrado, '<strong>1</strong>')
        self.assertContains(filtrado, '0 con organización')
        self.assertContains(filtrado, '1 sin organización')

        org = self.http.get(url, {
            'q': self.tag,
            'cliente__id__exact': self.cli.pk,
        })
        self.assertContains(org, '<strong>2</strong>')
        self.assertContains(org, '2 con organización')
        self.assertContains(org, '0 sin organización')

        chat = self.http.get(url, {
            'q': self.tag,
            'eki_estado_chat': 'habeas',
        })
        self.assertContains(chat, '<strong>1</strong>')
        self.assertContains(chat, 'Alexander')
        self.assertNotContains(chat, 'Andreina')
