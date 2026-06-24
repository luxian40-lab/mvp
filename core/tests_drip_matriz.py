"""Tests asignación masiva de acceso a módulos (matriz)."""

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from core.drip_matriz_service import filas_matriz_modulo, sincronizar_habilitaciones_modulo
from core.drip_schedule import estudiante_autorizado_en_modulo, modulo_disponible_por_calendario
from core.models import (
    Cliente,
    Curso,
    Estudiante,
    HabilitacionModuloEstudiante,
    Modulo,
)


class DripMatrizServiceTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            nombre='Coop Matriz',
            contacto_principal='A',
            email='matriz@test.com',
            telefono='573001111111',
            activo=True,
            drip_modulos_solo_estudiantes_listados=True,
        )
        self.curso = Curso.objects.create(nombre='Curso M', cliente=self.cliente, activo=True)
        self.m2 = Modulo.objects.create(
            curso=self.curso,
            numero=2,
            titulo='Módulo 2',
            descripcion='d',
            contenido='c',
        )
        self.ana = Estudiante.objects.create(
            cedula='100', nombre='Ana', telefono='573001111112', cliente=self.cliente, activo=True,
        )
        self.luis = Estudiante.objects.create(
            cedula='200', nombre='Luis', telefono='573001111113', cliente=self.cliente, activo=True,
        )
        self.pedro = Estudiante.objects.create(
            cedula='300', nombre='Pedro', telefono='573001111114', cliente=self.cliente, activo=True,
        )

    def test_filas_matriz_refleja_habilitados(self):
        HabilitacionModuloEstudiante.objects.create(
            estudiante=self.ana, curso=self.curso, modulo=self.m2, activo=True,
        )
        filas = filas_matriz_modulo(self.cliente, self.curso, self.m2)
        por_id = {f['estudiante'].id: f['habilitado'] for f in filas}
        self.assertTrue(por_id[self.ana.id])
        self.assertFalse(por_id[self.luis.id])
        self.assertFalse(por_id[self.pedro.id])

    def test_sincronizar_varios_estudiantes(self):
        habilitados, desactivados = sincronizar_habilitaciones_modulo(
            self.cliente,
            self.curso,
            self.m2,
            {self.ana.id, self.luis.id},
        )
        self.assertEqual(habilitados, 2)
        self.assertEqual(desactivados, 0)
        self.assertEqual(
            HabilitacionModuloEstudiante.objects.filter(
                curso=self.curso, modulo=self.m2, activo=True,
            ).count(),
            2,
        )
        self.assertTrue(estudiante_autorizado_en_modulo(self.ana, self.m2))
        self.assertTrue(estudiante_autorizado_en_modulo(self.luis, self.m2))
        self.assertFalse(estudiante_autorizado_en_modulo(self.pedro, self.m2))

    def test_sincronizar_quita_acceso_previo(self):
        HabilitacionModuloEstudiante.objects.create(
            estudiante=self.ana, curso=self.curso, modulo=self.m2, activo=True,
        )
        HabilitacionModuloEstudiante.objects.create(
            estudiante=self.luis, curso=self.curso, modulo=self.m2, activo=True,
        )
        habilitados, desactivados = sincronizar_habilitaciones_modulo(
            self.cliente,
            self.curso,
            self.m2,
            {self.pedro.id},
        )
        self.assertEqual(habilitados, 1)
        self.assertEqual(desactivados, 2)
        self.assertFalse(estudiante_autorizado_en_modulo(self.ana, self.m2))
        self.assertTrue(estudiante_autorizado_en_modulo(self.pedro, self.m2))
        self.assertTrue(modulo_disponible_por_calendario(self.pedro, self.m2))
        self.assertFalse(modulo_disponible_por_calendario(self.ana, self.m2))

    def test_sincronizar_reactiva_fila_inactiva(self):
        fila = HabilitacionModuloEstudiante.objects.create(
            estudiante=self.ana, curso=self.curso, modulo=self.m2, activo=False,
        )
        sincronizar_habilitaciones_modulo(
            self.cliente, self.curso, self.m2, {self.ana.id},
        )
        fila.refresh_from_db()
        self.assertTrue(fila.activo)


class DripMatrizAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('admin_matriz', 'm@c.com', 'pass')
        self.cliente = Cliente.objects.create(
            nombre='Org Matriz',
            contacto_principal='B',
            email='org@test.com',
            telefono='573002222221',
            activo=True,
            drip_modulos_solo_estudiantes_listados=True,
        )
        self.curso = Curso.objects.create(nombre='C', cliente=self.cliente, activo=True)
        self.modulo = Modulo.objects.create(
            curso=self.curso, numero=1, titulo='Intro', descripcion='d', contenido='c',
        )
        self.e1 = Estudiante.objects.create(
            cedula='11', nombre='Uno', telefono='573002222222', cliente=self.cliente, activo=True,
        )
        self.e2 = Estudiante.objects.create(
            cedula='22', nombre='Dos', telefono='573002222223', cliente=self.cliente, activo=True,
        )
        self.http = Client()

    @override_settings(
        STORAGES={
            'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
        },
    )
    def test_matriz_visible_con_curso_y_modulo(self):
        self.http.login(username='admin_matriz', password='pass')
        url = (
            f'/admin/drip-estudiantes/?cliente={self.cliente.id}'
            f'&curso={self.curso.id}&modulo={self.modulo.id}'
        )
        r = self.http.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Asignación rápida')
        self.assertContains(r, 'Uno')
        self.assertContains(r, 'Dos')

    @override_settings(
        STORAGES={
            'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
        },
    )
    def test_guardar_matriz_habilita_seleccionados(self):
        self.http.login(username='admin_matriz', password='pass')
        url = '/admin/drip-estudiantes/'
        data = {
            'action': 'guardar_matriz',
            'cliente': str(self.cliente.id),
            'curso': str(self.curso.id),
            'modulo': str(self.modulo.id),
            'estudiantes_habilitados': [str(self.e1.id), str(self.e2.id)],
        }
        r = self.http.post(url, data)
        self.assertEqual(r.status_code, 302)
        self.assertIn('guardado=1', r.url)
        self.assertEqual(
            HabilitacionModuloEstudiante.objects.filter(
                modulo=self.modulo, activo=True,
            ).count(),
            2,
        )
        r2 = self.http.get(r.url)
        self.assertContains(r2, 'Habilitaciones guardadas')
        self.assertContains(r2, 'Uno')
        self.assertContains(r2, 'Dos')

    @override_settings(
        STORAGES={
            'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
        },
    )
    def test_guardar_tabla_avanzada_habilitado_desde(self):
        HabilitacionModuloEstudiante.objects.create(
            estudiante=self.e1, curso=self.curso, modulo=self.modulo, activo=True,
        )
        self.http.login(username='admin_matriz', password='pass')
        dt = timezone.now().replace(microsecond=0)
        dt_str = timezone.localtime(dt).strftime('%Y-%m-%dT%H:%M')
        data = {
            'action': 'guardar',
            'avanzado': '1',
            'cliente': str(self.cliente.id),
            'curso': str(self.curso.id),
            'modulo': str(self.modulo.id),
            'form-TOTAL_FORMS': '1',
            'form-INITIAL_FORMS': '1',
            'form-MIN_NUM_FORMS': '0',
            'form-MAX_NUM_FORMS': '1000',
            'form-0-id': str(HabilitacionModuloEstudiante.objects.get(estudiante=self.e1).id),
            'form-0-estudiante': str(self.e1.id),
            'form-0-curso': str(self.curso.id),
            'form-0-modulo': str(self.modulo.id),
            'form-0-habilitado_desde': dt_str,
            'form-0-activo': 'on',
            'form-0-notas': 'fecha test',
        }
        r = self.http.post('/admin/drip-estudiantes/', data)
        self.assertEqual(r.status_code, 302)
        self.assertIn('avanzado=1', r.url)
        fila = HabilitacionModuloEstudiante.objects.get(estudiante=self.e1, modulo=self.modulo)
        self.assertIsNotNone(fila.habilitado_desde)
        self.assertEqual(fila.notas, 'fecha test')
