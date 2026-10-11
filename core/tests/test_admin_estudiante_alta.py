"""Alta de estudiante en el admin: mismos datos, cursos permitidos e importación."""
from __future__ import annotations

from io import BytesIO, StringIO

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse
from openpyxl import Workbook

from core.admin.estudiante_alta import (
    CAMPOS_EXCLUIDOS,
    EstudianteAdminFormV2,
    campos_del_alta,
)
from core.admin.estudiantes import EstudianteAdmin, EstudianteAdminForm
from core.admin.clientes import HabilitacionModuloEstudianteInline
from core.cursos_permitidos import cursos_permitidos, parece_nombre_de_prueba
from core.models import Cliente, Curso, Estudiante, Modulo, ProgresoEstudiante
from core.models_extras import GrupoEstudiantes
from core.planes_linea import PLAN_CURSO_ASESOR
from core.utils_telefono import normalizar_telefono

CAMPOS_VIEJOS = {
    'tipo_documento', 'cedula', 'nombre', 'telefono', 'cliente', 'activo',
    'cursos_a_inscribir', 'mostrar_cursos_inscritos',
    'municipio', 'departamento', 'ubicacion_detalle', 'genero', 'edad', 'rango_edad',
    'rural_disperso', 'pdet', 'consentimiento_impacto', 'consentimiento_impacto_en',
    'consentimiento_impacto_acudiente', 'area_unidad_ha',
}


def _org(nombre, tel, **extra):
    return Cliente.objects.create(
        nombre=nombre,
        contacto_principal='a',
        email=f'{tel}@eki.test',
        telefono=tel,
        **extra,
    )


def _curso(nombre, cliente, **extra):
    return Curso.objects.create(
        nombre=nombre,
        descripcion='d',
        cliente=cliente,
        activo=True,
        **extra,
    )


def _xlsx(filas):
    wb = Workbook()
    ws = wb.active
    for fila in filas:
        ws.append(list(fila))
    buf = BytesIO()
    wb.save(buf)
    return SimpleUploadedFile(
        'estudiantes.xlsx',
        buf.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )


@override_settings(ADMIN_ESTUDIANTE_ALTA_V2=True, SECURE_SSL_REDIRECT=False)
class AltaEstudianteTests(TestCase):
    def setUp(self):
        self.org = _org('Org A', '573001110001')
        self.otra = _org('Org B', '573001110002')
        self.general = _curso('General eki', None)
        self.propio = _curso('Curso A', self.org)
        self.ajeno = _curso('Curso B', self.otra)
        Modulo.objects.create(curso=self.propio, numero=1, titulo='M', descripcion='d', contenido='x')
        Modulo.objects.create(curso=self.general, numero=1, titulo='G', descripcion='d', contenido='x')
        self.admin = EstudianteAdmin(Estudiante, AdminSite())
        self.user = get_user_model().objects.create_superuser('alta', 'alta@x.co', 'pass12345')
        self.rf = RequestFactory()
        self.client = Client()
        self.client.login(username='alta', password='pass12345')

    def _form(self, **extra):
        data = {
            'tipo_documento': 'CC',
            'cedula': '100200300',
            'nombre': 'ana perez',
            'telefono': '3001112233',
            'cliente': str(self.org.pk),
            'activo': 'on',
        }
        data.update(extra)
        return EstudianteAdminFormV2(data=data)

    def _guardar(self, form, est=None):
        self.assertTrue(form.is_valid(), form.errors)
        if est is None:
            est = form.save(commit=False)
        request = self.rf.post('/admin/')
        request.user = self.user
        request.session = {}
        request._messages = FallbackStorage(request)
        self.admin.save_model(request, est, form, change=bool(est.pk))
        est.refresh_from_db()
        return est

    def test_cobertura_de_campos(self):
        presentes = campos_del_alta(True) | campos_del_alta(False)
        for campo in CAMPOS_VIEJOS:
            self.assertIn(campo, presentes, campo)
        for field in Estudiante._meta.fields:
            self.assertTrue(
                field.name in presentes or field.name in CAMPOS_EXCLUIDOS,
                field.name,
            )
        self.assertEqual(
            HabilitacionModuloEstudianteInline.fields,
            ('curso', 'modulo', 'habilitado_desde', 'activo', 'notas'),
        )

    def test_guardar_igual_que_el_formulario_viejo(self):
        viejo = EstudianteAdminForm(data={
            'tipo_documento': 'CC',
            'cedula': '100200301',
            'nombre': 'ana perez',
            'telefono': '+57 300 111 2234',
            'cliente': str(self.org.pk),
            'activo': 'on',
            'cursos_a_inscribir': [str(self.propio.pk)],
        })
        self.assertTrue(viejo.is_valid(), viejo.errors)
        est_viejo = viejo.save(commit=False)
        request = self.rf.post('/admin/')
        request.user = self.user
        request.session = {}
        request._messages = FallbackStorage(request)
        self.admin.save_model(request, est_viejo, viejo, change=False)
        est_viejo.refresh_from_db()
        nuevo = self._form(
            cedula='100200302',
            telefono='300-111-2235',
            cursos_a_inscribir=[str(self.propio.pk)],
        )
        est_nuevo = self._guardar(nuevo)
        self.assertEqual(est_nuevo.telefono, normalizar_telefono('+57 300 111 2235'))
        self.assertEqual(est_viejo.cliente_id, est_nuevo.cliente_id)
        self.assertTrue(est_viejo.activo and est_nuevo.activo)
        self.assertEqual(est_nuevo.nombre, 'Ana Perez')
        self.assertTrue(
            ProgresoEstudiante.objects.filter(estudiante=est_nuevo, curso=self.propio).exists()
        )
        self.assertEqual(est_nuevo.estado_chat, est_viejo.estado_chat)

    def test_cursos_de_la_organizacion_y_generales(self):
        form = self._form()
        ids = set(form.fields['cursos_a_inscribir'].queryset.values_list('pk', flat=True))
        self.assertEqual(ids, set(cursos_permitidos(self.org).values_list('pk', flat=True)))
        self.assertIn(self.propio.pk, ids)
        self.assertIn(self.general.pk, ids)
        self.assertNotIn(self.ajeno.pk, ids)
        sin = EstudianteAdminFormV2(data={
            'tipo_documento': 'CC', 'cedula': '1', 'nombre': 'Ana Perez',
            'telefono': '3001112299', 'activo': 'on',
        })
        sin_ids = set(sin.fields['cursos_a_inscribir'].queryset.values_list('pk', flat=True))
        self.assertEqual(sin_ids, {self.general.pk})
        self.assertIn('Sin organización: solo cursos generales', sin.fields['cursos_a_inscribir'].help_text)

    def test_post_de_otro_curso_falla(self):
        form = self._form(cursos_a_inscribir=[str(self.ajeno.pk)])
        self.assertFalse(form.is_valid())
        self.assertIn(
            'Ese curso no pertenece a la organización ni es general de eki.',
            str(form.errors),
        )

    def test_cambiar_de_organizacion_no_guarda_el_curso_ajeno(self):
        form = self._form(cliente=str(self.otra.pk), cursos_a_inscribir=[str(self.propio.pk)])
        self.assertFalse(form.is_valid())
        self.assertFalse(ProgresoEstudiante.objects.filter(curso=self.propio).exists())

    def test_documento_y_telefono_repetidos_bloquean(self):
        Estudiante.objects.create(
            tipo_documento='CC', cedula='555', nombre='Ya Existe',
            telefono='573001112244', cliente=self.org,
        )
        doc = self.client.get(reverse('admin:core_estudiante_alta_documento'), {'numero': '555'})
        self.assertTrue(doc.json()['existe'])
        self.assertEqual(doc.json()['nombre'], 'Ya Existe')
        self.assertIn('/admin/core/estudiante/', doc.json()['url'])
        tel = self.client.get(
            reverse('admin:core_estudiante_alta_telefono'),
            {'telefono': '+57 300 111 2244'},
        )
        self.assertTrue(tel.json()['existe'])
        form = self._form(cedula='555', telefono='3001112244')
        self.assertFalse(form.is_valid())

    def test_telefonos_distintos_se_guardan_igual(self):
        crudos = ['+57 300 111 2255', '57 300-111-2255', '300 111 2255']
        guardados = []
        for indice, crudo in enumerate(crudos, start=1):
            form = EstudianteAdminFormV2(data={
                'tipo_documento': 'CC',
                'cedula': f'2255{indice}',
                'nombre': 'Ana Perez',
                'telefono': crudo,
                'activo': 'on',
            })
            self.assertTrue(form.is_valid(), form.errors)
            guardados.append(form.instance.telefono)
        self.assertEqual(len(set(guardados)), 1)
        self.assertEqual(guardados[0], '573001112255')

    def test_drip_solo_con_el_modo(self):
        self.org.drip_modulos_solo_estudiantes_listados = True
        self.org.save(update_fields=['drip_modulos_solo_estudiantes_listados'])
        est = Estudiante.objects.create(
            tipo_documento='CC', cedula='777', nombre='Con Drip',
            telefono='573001112266', cliente=self.org,
        )
        con = self.client.get(reverse('admin:core_estudiante_change', args=[est.pk]))
        self.assertContains(con, 'Módulos habilitados (drip por lista)')
        self.assertContains(con, 'ekiDrip = "1"')
        otro = Estudiante.objects.create(
            tipo_documento='CC', cedula='778', nombre='Sin Drip',
            telefono='573001112267', cliente=self.otra,
        )
        sin = self.client.get(reverse('admin:core_estudiante_change', args=[otro.pk]))
        self.assertContains(sin, 'ekiDrip = "0"')

    def test_bienvenida_apagada_no_envia_y_el_fallo_no_borra(self):
        from core.models_campana_meta import PlantillaMeta
        PlantillaMeta.objects.create(
            nombre_interno='Bienvenida curso',
            meta_name='eki_bienvenida_curso',
            cuerpo='Hola',
            estado='APPROVED',
            activa=True,
        )
        pagina = self.client.get(reverse('admin:core_estudiante_add'))
        self.assertContains(pagina, 'Enviar bienvenida por WhatsApp')
        form = self._form(cedula='880', telefono='3001112277', enviar_bienvenida='')
        with self.settings():
            from unittest.mock import patch
            with patch('core.meta_waba._post') as post:
                est = self._guardar(form)
                post.assert_not_called()
        self.assertTrue(Estudiante.objects.filter(pk=est.pk).exists())
        form_falla = self._form(
            cedula='881', telefono='3001112278', enviar_bienvenida='on',
        )
        self.assertTrue(form_falla.is_valid(), form_falla.errors)
        from django.utils import timezone
        from unittest.mock import patch
        est2 = form_falla.save(commit=False)
        est2.wa_optin_fecha = timezone.now()
        with self.settings(WHATSAPP_PHONE_ID='15550001111'):
            with patch('core.meta_waba._post', return_value=(500, {})) as post:
                request = self.rf.post('/admin/')
                request.user = self.user
                request.session = {}
                request._messages = FallbackStorage(request)
                self.admin.save_model(request, est2, form_falla, change=False)
                self.assertGreaterEqual(post.call_count, 1)
        self.assertTrue(Estudiante.objects.filter(pk=est2.pk).exists())

    def test_prueba_y_archivado_no_salen_si_no_es_duena_ni_demo(self):
        demo = _org('Demo', '573001110009', es_demo=True)
        prueba = _curso('Pilotaje', demo)
        archivado = _curso('Viejo', self.org, activo=False)
        ids = set(cursos_permitidos(self.org).values_list('pk', flat=True))
        self.assertNotIn(prueba.pk, ids)
        self.assertNotIn(archivado.pk, ids)
        self.assertIn(prueba.pk, set(cursos_permitidos(demo).values_list('pk', flat=True)))
        self.assertIn(self.propio.pk, set(cursos_permitidos(self.org).values_list('pk', flat=True)))
        self.assertTrue(parece_nombre_de_prueba('Nuevo curso 7'))
        self.assertIn(
            _curso('Nuevo curso 7', self.org).pk,
            set(cursos_permitidos(self.org).values_list('pk', flat=True)),
        )

    def test_fuera_de_regla_se_conserva_y_la_auditoria_no_escribe(self):
        est = Estudiante.objects.create(
            tipo_documento='CC', cedula='999', nombre='Antiguo',
            telefono='573001112288', cliente=self.org,
        )
        ProgresoEstudiante.objects.create(estudiante=est, curso=self.ajeno)
        antes = ProgresoEstudiante.objects.count()
        form = EstudianteAdminFormV2(data={
            'tipo_documento': 'CC',
            'cedula': est.cedula,
            'nombre': est.nombre,
            'telefono': est.telefono,
            'cliente': str(self.org.pk),
            'activo': 'on',
        }, instance=est)
        self.assertTrue(form.fuera_de_regla)
        self.assertTrue(form.is_valid(), form.errors)
        self._guardar(form, est)
        self.assertTrue(
            ProgresoEstudiante.objects.filter(estudiante=est, curso=self.ajeno).exists()
        )
        salida = StringIO()
        call_command('auditar_inscripciones_fuera_de_regla', stdout=salida)
        self.assertIn(f'estudiante_id={est.pk}', salida.getvalue())
        self.assertIn('Curso B', salida.getvalue())
        self.assertEqual(ProgresoEstudiante.objects.count(), antes)
        pagina = self.client.get(reverse('admin:core_estudiante_change', args=[est.pk]))
        self.assertContains(pagina, 'Fuera de regla')
        self.assertNotContains(pagina, 'Ver todos')

    def test_grupo_asigna_el_plan(self):
        grupo = GrupoEstudiantes.objects.create(
            nombre='Norte', cliente=self.org, plan_linea_meta=PLAN_CURSO_ASESOR, activo=True,
        )
        form = self._form(cedula='321', telefono='3001112290', grupo=str(grupo.pk))
        est = self._guardar(form)
        self.assertTrue(est.grupos.filter(pk=grupo.pk).exists())
        pagina = self.client.get(reverse('admin:core_estudiante_add') + f'?cliente__id__exact={self.org.pk}')
        self.assertContains(pagina, 'OP1')
        self.assertContains(pagina, 'Así quedará')
        self.assertContains(pagina, '1. Organización')
        self.assertContains(pagina, 'Sin organización (B2C)')
        self.assertNotContains(pagina, 'Ir a sección')
        self.assertNotContains(pagina, 'Select value')

    def test_importacion_preview_idempotente_y_sin_mensaje(self):
        from unittest.mock import patch
        archivo = _xlsx([
            ['tipo_documento', 'documento', 'nombre', 'telefono', 'organización', 'curso'],
            ['CC', '4242', 'Ana Perez', '3001112300', 'Org A', 'Curso A'],
            ['CC', '', 'Sin Doc', '3001112301', 'Org A', 'Curso A'],
            ['CC', '4243', 'Luis Ruiz', '300', 'Org A', 'Curso A'],
            ['CC', '4244', 'Otra Org', '3001112302', 'Org A', 'Curso B'],
            ['CC', '4245', 'General', '3001112303', '', 'General eki'],
            ['CC', '4246', 'Nadie', '3001112304', 'No existe', 'General eki'],
        ])
        url = reverse('admin:core_estudiante_importar')
        with patch('core.meta_waba._post') as post:
            previo = self.client.post(url, {'paso': 'previsualizar', 'archivo_excel': archivo})
            self.assertContains(previo, 'el curso no corresponde a la organización')
            self.assertContains(previo, 'Documento vacío')
            self.client.post(url, {'paso': 'confirmar'})
            post.assert_not_called()
        self.assertTrue(Estudiante.objects.filter(cedula='4242').exists())
        self.assertTrue(Estudiante.objects.filter(cedula='4245', cliente__isnull=True).exists())
        self.assertFalse(Estudiante.objects.filter(cedula='4244').exists())
        self.assertFalse(Estudiante.objects.filter(cedula='4246').exists())
        otra = _xlsx([
            ['tipo_documento', 'documento', 'nombre', 'telefono', 'organización', 'curso'],
            ['CC', '4242', 'Ana Perez', '3001112300', 'Org A', 'Curso A'],
        ])
        self.client.post(url, {'paso': 'previsualizar', 'archivo_excel': otra})
        self.client.post(url, {'paso': 'confirmar'})
        self.assertEqual(Estudiante.objects.filter(cedula='4242').count(), 1)

    def test_importacion_respeta_el_tope(self):
        filas = [['tipo_documento', 'documento', 'nombre', 'telefono', 'organización', 'curso']]
        for n in range(3):
            filas.append(['CC', f'90{n}', 'Ana Perez Ruiz', f'30011124{n}0', 'Org A', ''])
        with self.settings(ADMIN_ESTUDIANTE_IMPORT_MAX=1):
            self.client.post(reverse('admin:core_estudiante_importar'), {
                'paso': 'previsualizar',
                'archivo_excel': _xlsx(filas),
            })
        cuerpo = self.client.get(reverse('admin:core_estudiante_importar') + '?errores=1')
        self.assertContains(cuerpo, 'máximo')


@override_settings(ADMIN_ESTUDIANTE_ALTA_V2=False, SECURE_SSL_REDIRECT=False)
class AltaApagadaTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser('off', 'off@x.co', 'pass12345')
        self.client = Client()
        self.client.login(username='off', password='pass12345')

    def test_el_formulario_anterior_sigue(self):
        pagina = self.client.get(reverse('admin:core_estudiante_add'))
        self.assertContains(pagina, 'Inscribir en curso(s)')
        self.assertNotContains(pagina, '1. Organización')


class NombresPruebaTests(TestCase):
    def test_el_comando_lista_y_no_desactiva(self):
        org = _org('Real', '573001119999')
        curso = _curso('Nuevo curso 8', org)
        salida = StringIO()
        call_command('proponer_cursos_prueba', stdout=salida)
        self.assertIn('Nuevo curso 8', salida.getvalue())
        curso.refresh_from_db()
        self.assertTrue(curso.activo)
