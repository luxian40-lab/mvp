"""Tests pantalla push por estudiantes."""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from core.models import Cliente, Curso, Estudiante, ProgresoEstudiante
from core.models_extras import GrupoEstudiantes, MensajePush


class PushEstudiantesAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('admin_push', 'p@c.com', 'pass')
        self.cliente = Cliente.objects.create(
            nombre='Org Push', contacto_principal='X', email='push@test.com',
            telefono='573007777771', activo=True,
        )
        self.curso = Curso.objects.create(nombre='C Push', cliente=self.cliente, activo=True)
        self.est = Estudiante.objects.create(
            cedula='99', nombre='Marta', telefono='573007777772',
            cliente=self.cliente, activo=True,
        )
        ProgresoEstudiante.objects.create(estudiante=self.est, curso=self.curso, completado=False)
        self.mensaje = MensajePush.objects.create(
            nombre='Recordatorio test',
            cliente=self.cliente,
            curso=self.curso,
            tipo='personalizado',
            cuerpo_fallback='Hola {nombre}, sigue con {curso}.',
            activo=True,
        )
        self.http = Client()

    @override_settings(
        STORAGES={
            'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
        },
    )
    def test_pagina_carga(self):
        self.http.login(username='admin_push', password='pass')
        r = self.http.get(f'/admin/push-estudiantes/?cliente={self.cliente.id}')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Push recordatorios')
        self.assertContains(r, 'Marta')

    @override_settings(
        STORAGES={
            'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
        },
    )
    @patch('core.mensajes_push.enviar_mensaje_push_a_estudiante', return_value={'success': True})
    def test_enviar_a_seleccionados(self, mock_push):
        self.http.login(username='admin_push', password='pass')
        r = self.http.post('/admin/push-estudiantes/', {
            'action': 'enviar',
            'cliente': str(self.cliente.id),
            'mensaje_push': str(self.mensaje.id),
            'estudiantes': [str(self.est.id)],
        })
        self.assertEqual(r.status_code, 302)
        mock_push.assert_called_once()

    @override_settings(
        STORAGES={
            'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
        },
    )
    def test_filtro_grupo_en_pagina(self):
        grupo = GrupoEstudiantes.objects.create(
            nombre='Grupo A', cliente=self.cliente, activo=True,
        )
        grupo.estudiantes.add(self.est)
        self.http.login(username='admin_push', password='pass')
        r = self.http.get(
            f'/admin/push-estudiantes/?cliente={self.cliente.id}&grupo={grupo.id}',
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Grupo A')
        self.assertContains(r, 'Enviar a los marcados')
        self.assertContains(r, 'Marcar grupo')

    @override_settings(
        STORAGES={
            'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
        },
    )
    @patch('core.mensajes_push.enviar_mensaje_push_a_estudiante', return_value={'success': True})
    def test_enviar_todo_grupo(self, mock_push):
        grupo = GrupoEstudiantes.objects.create(
            nombre='G Push', cliente=self.cliente, activo=True,
        )
        grupo.estudiantes.add(self.est)
        self.http.login(username='admin_push', password='pass')
        r = self.http.post('/admin/push-estudiantes/', {
            'action': 'enviar',
            'cliente': str(self.cliente.id),
            'grupo': str(grupo.id),
            'mensaje_push': str(self.mensaje.id),
            'enviar_todo_grupo': '1',
        })
        self.assertEqual(r.status_code, 302)
        mock_push.assert_called_once()

    @override_settings(
        STORAGES={
            'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
        },
    )
    @patch('core.mensajes_push.enviar_mensaje_push_a_estudiante', return_value={'success': True})
    def test_enviar_solo_individuales_marcados(self, mock_push):
        otro = Estudiante.objects.create(
            cedula='88', nombre='Otro', telefono='573007777773',
            cliente=self.cliente, activo=True,
        )
        grupo = GrupoEstudiantes.objects.create(
            nombre='G2', cliente=self.cliente, activo=True,
        )
        grupo.estudiantes.add(self.est, otro)
        self.http.login(username='admin_push', password='pass')
        r = self.http.post('/admin/push-estudiantes/', {
            'action': 'enviar',
            'cliente': str(self.cliente.id),
            'grupo': str(grupo.id),
            'mensaje_push': str(self.mensaje.id),
            'estudiantes': [str(self.est.id)],
        })
        self.assertEqual(r.status_code, 302)
        mock_push.assert_called_once()
        self.assertEqual(mock_push.call_args[0][1].id, self.est.id)
