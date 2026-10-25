"""Listado CRM de Estudiantes: cifras, organización y consultas constantes."""
import uuid
from pathlib import Path
from datetime import timedelta

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.cache import cache
from django.db import connection
from django.db.models.signals import post_save
from django.test import Client, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from core.admin.estudiantes import EstudianteAdmin
from core.admin.estudiantes_crm import clasificar_estado, texto_actividad
from core.models import (
    Cliente,
    Curso,
    Estudiante,
    Modulo,
    ModuloCompletado,
    NotaEstudiante,
    ProgresoEstudiante,
    WhatsappLog,
)
from core.signals_conocimientos import curso_actualizado, modulo_actualizado


def _consultas(cliente, url, params=None):
    with CaptureQueriesContext(connection) as ctx:
        respuesta = cliente.get(url, params or {})
    return respuesta, len(ctx.captured_queries)


@override_settings(SECURE_SSL_REDIRECT=False)
class EstudiantesCrmTests(TestCase):
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
        cache.clear()
        self.tag = uuid.uuid4().hex[:8]
        self.nro = int(self.tag, 16) % 1_000_000
        self.org = Cliente.objects.create(
            nombre=f'Fedepanela {self.tag}',
            contacto_principal='a',
            email=f'crm-{self.tag}@example.com',
            telefono=f'57310{self.tag[:7]}',
        )
        self.otra = Cliente.objects.create(
            nombre=f'Cenipalma {self.tag}',
            contacto_principal='b',
            email=f'crm2-{self.tag}@example.com',
            telefono=f'57312{self.tag[:7]}',
        )
        self.curso = Curso.objects.create(
            nombre=f'Cania {self.tag}',
            descripcion='d',
            cliente=self.org,
            activo=True,
        )
        for numero in (1, 2):
            Modulo.objects.create(
                curso=self.curso,
                numero=numero,
                titulo=f'M{numero}',
                descripcion='d',
                contenido='x',
            )
        ahora = timezone.now()
        self.al_dia = self._est('Marta Crm', f'A{self.tag}', self._tel(1), self.org, 'ACTIVO')
        prog = ProgresoEstudiante.objects.create(
            estudiante=self.al_dia,
            curso=self.curso,
            modulo_actual=Modulo.objects.get(curso=self.curso, numero=2),
            fecha_ultimo_avance=ahora,
        )
        ModuloCompletado.objects.create(
            progreso=prog,
            modulo=Modulo.objects.get(curso=self.curso, numero=1),
        )
        log = WhatsappLog.objects.create(
            telefono=self.al_dia.telefono,
            estudiante=self.al_dia,
            tipo='INCOMING',
            mensaje='listo',
        )
        WhatsappLog.objects.filter(pk=log.pk).update(fecha=ahora - timedelta(days=3))
        self.habeas = self._est('Luis Crm', f'B{self.tag}', self._tel(2), self.org, 'ESPERANDO_HABEAS_DATA')
        self.quieto = self._est('Ana Crm', f'C{self.tag}', self._tel(3), self.otra, 'ACTIVO')
        ProgresoEstudiante.objects.create(
            estudiante=self.quieto,
            curso=self.curso,
            fecha_ultimo_avance=ahora - timedelta(days=20),
        )
        self.suelto = self._est('Otto Crm', f'D{self.tag}', self._tel(4), None, 'ACTIVO')
        self.user = get_user_model().objects.create_superuser(
            f'crm_{self.tag}', f'crm-{self.tag}@x.co', 'pass12345',
        )
        self.http = Client()
        self.http.force_login(self.user)
        self.url = reverse('admin:core_estudiante_changelist')

    def _tel(self, slot):
        return f'57{slot}{self.nro:06d}{slot:02d}'

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

    def test_columnas_no_rompen_sin_curso_ni_mensaje(self):
        admin = EstudianteAdmin(Estudiante, AdminSite())
        request = self.http.request()
        request.user = self.user
        request.GET = {}
        est = admin.get_queryset(request).get(pk=self.suelto.pk)
        self.assertIn('Sin curso', str(admin.crm_curso(est)))
        self.assertIn('nunca escribió', str(admin.crm_actividad(est)))
        self.assertIn('Otto', str(admin.crm_estudiante(est)))
        self.assertIn('Sin organización', str(admin.crm_organizacion(est)))

    def test_kpis_cuadran_con_el_calculo(self):
        respuesta = self.http.get(self.url, {'q': 'CRM'})
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'data-kpi="avance">10%<')
        self.assertContains(respuesta, 'data-kpi="completaron">0<')
        self.assertContains(respuesta, 'data-kpi="habeas">1<')
        self.assertContains(respuesta, 'data-kpi="sin-actividad">1<')
        self.assertContains(respuesta, 'Mód. 1/2')
        self.assertContains(respuesta, 'hace 3 días')
        self.assertContains(respuesta, 'Habeas pendiente')
        self.assertContains(respuesta, 'Sin actividad')
        self.assertNotContains(respuesta, 'Sin respuesta')

    def test_organizacion_conserva_la_busqueda(self):
        respuesta = self.http.get(self.url, {
            'q': 'CRM',
            'cliente__id__exact': self.org.pk,
            'o': '2',
        })
        self.assertContains(respuesta, 'Marta Crm')
        self.assertContains(respuesta, 'Luis Crm')
        self.assertNotContains(respuesta, 'Ana Crm')
        self.assertNotContains(respuesta, 'Otto Crm')
        self.assertContains(respuesta, 'o=2')
        self.assertContains(respuesta, f'cliente__id__exact={self.org.pk}')

    def test_sin_organizacion_es_quien_no_tiene_cliente(self):
        respuesta = self.http.get(self.url, {'cliente__isnull': 'True', 'q': 'CRM'})
        self.assertContains(respuesta, 'Otto Crm')
        self.assertNotContains(respuesta, 'Marta Crm')
        self.assertNotContains(respuesta, 'Ana Crm')

    def test_sufijo_de_telefono(self):
        cola = self.al_dia.telefono[-4:]
        respuesta = self.http.get(self.url, {'q': cola})
        self.assertContains(respuesta, 'Marta Crm')
        self.assertNotContains(respuesta, 'Luis Crm')

    def test_chip_de_estado_localiza_en_la_tabla(self):
        base = self.http.get(self.url, {'q': 'CRM'})
        self.assertContains(base, 'eki_crm_estado=habeas')
        self.assertContains(base, 'eki_crm_estado=activo')

        habeas = self.http.get(self.url, {'q': 'CRM', 'eki_crm_estado': 'habeas'})
        self.assertContains(habeas, 'Luis Crm')
        self.assertNotContains(habeas, 'Marta Crm')
        self.assertNotContains(habeas, 'Ana Crm')
        self.assertNotContains(habeas, 'Otto Crm')
        self.assertContains(habeas, 'data-kpi="sin-actividad">1<')
        self.assertContains(habeas, 'eki-crm-chip--habeas is-on')

        activo = self.http.get(self.url, {'q': 'CRM', 'eki_crm_estado': 'activo'})
        self.assertContains(activo, 'Marta Crm')
        self.assertNotContains(activo, 'Luis Crm')
        self.assertNotContains(activo, 'Ana Crm')
        self.assertNotContains(activo, 'Otto Crm')

        quietos = self.http.get(self.url, {'q': 'CRM', 'eki_crm_estado': 'sin_actividad'})
        self.assertContains(quietos, 'Ana Crm')
        self.assertNotContains(quietos, 'Marta Crm')
        self.assertNotContains(quietos, 'Otto Crm')

        sin_iniciar = self.http.get(self.url, {'q': 'CRM', 'eki_crm_estado': 'sin_iniciar'})
        self.assertContains(sin_iniciar, 'Otto Crm')
        self.assertNotContains(sin_iniciar, 'Marta Crm')
        self.assertNotContains(sin_iniciar, 'Luis Crm')

    def test_ver_sin_avanzar_filtra(self):
        respuesta = self.http.get(self.url, {'q': 'CRM', 'eki_sin_avanzar': '1'})
        self.assertContains(respuesta, 'Ana Crm')
        self.assertNotContains(respuesta, 'Otto Crm')
        self.assertNotContains(respuesta, 'Luis Crm')
        self.assertNotContains(respuesta, 'Marta Crm')

    def test_staff_sin_permiso_no_ve_el_selector(self):
        alguien = get_user_model().objects.create_user(
            f'sin_{self.tag}', f'sin-{self.tag}@x.co', 'pass12345', is_staff=True,
        )
        cliente = Client()
        cliente.force_login(alguien)
        self.assertEqual(cliente.get(self.url).status_code, 403)
        permiso = Permission.objects.get(codename='view_estudiante')
        alguien.user_permissions.add(permiso)
        cliente2 = Client()
        cliente2.force_login(alguien)
        visto = cliente2.get(self.url, {'q': self.tag})
        self.assertEqual(visto.status_code, 200)
        self.assertContains(visto, self.org.nombre)
        self.assertContains(visto, self.otra.nombre)
        self.assertContains(visto, 'Sin organización')

    def test_diagnosticar_no_cambia_el_chat(self):
        antes = self.habeas.estado_chat
        url = reverse('admin:core_estudiante_crm_diagnosticar', args=[self.habeas.pk])
        respuesta = self.http.get(url)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'ESPERANDO_HABEAS_DATA')
        self.habeas.refresh_from_db()
        self.assertEqual(self.habeas.estado_chat, antes)

    def test_consultas_no_crecen_con_las_filas(self):
        vacio, n0 = _consultas(self.http, self.url, {'q': f'nadie-{self.tag}'})
        self.assertEqual(vacio.status_code, 200)
        cache.clear()
        uno, n1 = _consultas(self.http, self.url, {'q': 'Marta CRM'})
        self.assertEqual(uno.status_code, 200)
        Estudiante.objects.bulk_create([
            Estudiante(
                tipo_documento='CC',
                cedula=f'Z{self.tag}{i:04d}',
                nombre=f'Lote CRM {i}',
                telefono=f'579{i:03d}{self.nro:06d}',
                activo=True,
                estado_chat='ACTIVO',
                cliente=self.org,
            )
            for i in range(80)
        ])
        cache.clear()
        lote, n80 = _consultas(self.http, self.url, {'q': 'Lote CRM'})
        self.assertEqual(lote.status_code, 200)
        self.assertEqual(n1, n80)
        self.assertLessEqual(n80 - n0, 8)

    def test_buscar_no_cambia_los_kpi_ni_esconde_al_resto_de_la_org(self):
        respuesta = self.http.get(self.url, {'q': 'Marta'})
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Marta Crm')
        self.assertNotContains(respuesta, 'Luis Crm')
        self.assertContains(respuesta, 'data-kpi="avance">10%<')
        self.assertContains(respuesta, 'data-kpi="habeas">1<')
        self.assertNotContains(respuesta, 'Estado del chat')

    def test_el_boton_de_filtros_abre_el_panel(self):
        respuesta = self.http.get(self.url, {'q': 'CRM'})
        self.assertContains(respuesta, 'id="changelist-filter"')
        self.assertContains(respuesta, 'filterOpen = true')
        self.assertContains(respuesta, 'Curso inscrito')
        css = Path(__file__).resolve().parents[2].joinpath('static', 'admin', 'estudiantes_crm.css')
        texto = css.read_text(encoding='utf-8')
        self.assertNotIn('#changelist-filter', texto)
        self.assertNotIn('filter-open-button', texto)
        por_curso = self.http.get(self.url, {'curso': self.curso.pk, 'q': 'CRM'})
        self.assertContains(por_curso, 'Marta Crm')
        self.assertContains(por_curso, 'Ana Crm')
        self.assertNotContains(por_curso, 'Otto Crm')
        self.assertNotContains(por_curso, 'Luis Crm')

    def test_la_nota_queda_en_la_fila(self):
        self.user.first_name = 'Julian'
        self.user.last_name = 'Mesa'
        self.user.save(update_fields=['first_name', 'last_name'])
        url = reverse('admin:core_estudiante_crm_anadir_nota', args=[self.al_dia.pk])
        dialogo = self.http.get(url)
        self.assertEqual(dialogo.status_code, 200)
        self.assertContains(dialogo, 'Nota del equipo')
        antes = WhatsappLog.objects.count()
        respuesta = self.http.post(url, {
            'texto': 'nota vieja unica',
            '_form_submitted': 'True',
        })
        self.assertEqual(respuesta.status_code, 302)
        self.http.post(url, {
            'texto': 'Llamar el martes por la cosecha',
            '_form_submitted': 'True',
        })
        self.assertEqual(NotaEstudiante.objects.filter(estudiante=self.al_dia).count(), 2)
        self.assertEqual(WhatsappLog.objects.count(), antes)
        cache.clear()
        lista = self.http.get(self.url, {'q': 'Marta'})
        self.assertContains(lista, 'Llamar el martes por la cosecha')
        self.assertContains(lista, 'Julian Mesa')
        self.assertNotContains(lista, 'nota vieja unica')

    def test_texto_de_actividad_y_prioridad_de_habeas(self):
        self.assertEqual(texto_actividad(None), 'nunca escribió')
        slug, texto = clasificar_estado(
            estado_chat='ESPERANDO_HABEAS_DATA',
            ultima_entrada=None,
            completo=True,
            fecha_avance=None,
            n_completados=2,
        )
        self.assertEqual((slug, texto), ('completado', 'Completado'))
