"""Tests ajuste de avance por estudiante/curso."""

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from core.avance_reset_service import (
    ajustar_avance_hasta_modulo,
    ajustar_avance_estudiantes,
    reiniciar_avance_curso,
    resumen_avance,
)
from core.drip_schedule import modulo_disponible_por_calendario
from core.models import (
    Cliente,
    Curso,
    Estudiante,
    Modulo,
    ModuloCompletado,
    PasoModulo,
    ProgresoEstudiante,
    SeccionModulo,
)
from core.models_certificados import Certificado


class AvanceResetServiceTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            nombre='Coop Avance',
            contacto_principal='A',
            email='av@test.com',
            telefono='573003333331',
            activo=True,
        )
        self.curso = Curso.objects.create(nombre='Curso Av', cliente=self.cliente, activo=True)
        self.m1 = Modulo.objects.create(
            curso=self.curso, numero=1, titulo='M1', descripcion='d', contenido='c',
        )
        self.m2 = Modulo.objects.create(
            curso=self.curso, numero=2, titulo='M2', descripcion='d', contenido='c',
        )
        self.m3 = Modulo.objects.create(
            curso=self.curso, numero=3, titulo='M3', descripcion='d', contenido='c',
        )
        self.est = Estudiante.objects.create(
            cedula='900', nombre='Carlos', telefono='573003333332',
            cliente=self.cliente, activo=True,
            estado_chat='ACTIVO', estado_onboarding='completado',
        )
        self.progreso = ProgresoEstudiante.objects.create(
            estudiante=self.est,
            curso=self.curso,
            modulo_actual=self.m3,
            completado=True,
            fecha_completado=timezone.now(),
        )
        for mod in (self.m1, self.m2, self.m3):
            ModuloCompletado.objects.create(progreso=self.progreso, modulo=mod)

    def test_resumen_muestra_estado(self):
        r = resumen_avance(self.est, self.curso)
        self.assertTrue(r['tiene_progreso'])
        self.assertTrue(r['completado'])
        self.assertEqual(r['modulos_completados'], 3)

    def test_ajustar_hasta_modulo_2(self):
        resultado = ajustar_avance_hasta_modulo(self.est, self.curso, self.m2)
        self.progreso.refresh_from_db()
        self.assertEqual(self.progreso.modulo_actual_id, self.m2.id)
        self.assertFalse(self.progreso.completado)
        self.assertIsNone(self.progreso.fecha_completado)
        self.assertEqual(self.progreso.modulos_completados.count(), 1)
        self.assertTrue(
            self.progreso.modulos_completados.filter(modulo=self.m1).exists()
        )
        self.assertEqual(resultado['completados_eliminados'], 2)

    def test_reiniciar_desde_cero(self):
        reiniciar_avance_curso(self.est, self.curso)
        self.progreso.refresh_from_db()
        self.assertEqual(self.progreso.modulo_actual_id, self.m1.id)
        self.assertEqual(self.progreso.modulos_completados.count(), 0)
        self.assertFalse(self.progreso.completado)

    def test_quita_certificado(self):
        Certificado.objects.create(
            estudiante=self.est,
            curso=self.curso,
            calificacion_final=90,
            fecha_inicio=timezone.now().date(),
            emitido=True,
        )
        ajustar_avance_hasta_modulo(self.est, self.curso, self.m2)
        self.assertFalse(Certificado.objects.filter(estudiante=self.est, curso=self.curso).exists())

    def test_ajuste_masivo_dos_estudiantes(self):
        est2 = Estudiante.objects.create(
            cedula='901', nombre='Diana', telefono='573003333333',
            cliente=self.cliente, activo=True,
        )
        prog2 = ProgresoEstudiante.objects.create(
            estudiante=est2, curso=self.curso, modulo_actual=self.m3, completado=True,
        )
        ModuloCompletado.objects.create(progreso=prog2, modulo=self.m1)
        ModuloCompletado.objects.create(progreso=prog2, modulo=self.m2)

        resultados = ajustar_avance_estudiantes(
            {self.est.id, est2.id}, self.curso, self.m2,
        )
        self.assertEqual(len(resultados), 2)
        prog2.refresh_from_db()
        self.assertEqual(prog2.modulo_actual_id, self.m2.id)
        self.assertEqual(prog2.modulos_completados.count(), 1)

    def test_ajustar_hasta_microcontenido(self):
        sec1 = SeccionModulo.objects.create(modulo=self.m2, orden=1, titulo='Intro')
        sec2 = SeccionModulo.objects.create(modulo=self.m2, orden=2, titulo='Práctica')
        PasoModulo.objects.create(
            modulo=self.m2, seccion=sec1, orden=1, titulo='Micro A',
            contenido='Texto A', tipo=PasoModulo.TIPO_CONTENIDO,
        )
        p2 = PasoModulo.objects.create(
            modulo=self.m2, seccion=sec2, orden=2, titulo='Micro B',
            contenido='Texto B', tipo=PasoModulo.TIPO_CONTENIDO,
        )
        resultado = ajustar_avance_hasta_modulo(
            self.est, self.curso, self.m2, paso_destino=p2,
        )
        self.progreso.refresh_from_db()
        self.assertEqual(self.progreso.modulo_actual_id, self.m2.id)
        self.assertEqual(self.progreso.paso_actual_modulo, 2)
        self.assertFalse(self.progreso.esperando_respuesta_evaluacion_paso)
        self.assertEqual(resultado['paso_actual_modulo'], 2)
        from core.avance_reset_service import etiqueta_paso_actual
        label = etiqueta_paso_actual(self.progreso)
        self.assertIn('Sec.2', label)
        self.assertIn('Micro B', label)


class AvanceResetAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('admin_av', 'a@v.com', 'pass')
        self.cliente = Cliente.objects.create(
            nombre='Org Av',
            contacto_principal='B',
            email='orgav@test.com',
            telefono='573004444441',
            activo=True,
        )
        self.curso = Curso.objects.create(nombre='C Av', cliente=self.cliente, activo=True)
        self.m1 = Modulo.objects.create(
            curso=self.curso, numero=1, titulo='Intro', descripcion='d', contenido='c',
        )
        self.est = Estudiante.objects.create(
            cedula='50', nombre='Elena', telefono='573004444442',
            cliente=self.cliente, activo=True,
        )
        self.progreso = ProgresoEstudiante.objects.create(
            estudiante=self.est, curso=self.curso, modulo_actual=self.m1, completado=True,
        )
        ModuloCompletado.objects.create(progreso=self.progreso, modulo=self.m1)
        self.http = Client()

    @override_settings(
        SECURE_SSL_REDIRECT=False,
        STORAGES={
            'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
        },
    )
    def test_pagina_muestra_avance(self):
        self.http.login(username='admin_av', password='pass')
        url = f'/admin/ajustar-avance/?cliente={self.cliente.id}&curso={self.curso.id}'
        r = self.http.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Elena')
        self.assertContains(r, 'Curso completo')

    @override_settings(
        SECURE_SSL_REDIRECT=False,
        STORAGES={
            'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
        },
    )
    def test_post_ajusta_avance(self):
        self.http.login(username='admin_av', password='pass')
        r = self.http.post('/admin/ajustar-avance/', {
            'action': 'ajustar',
            'cliente': str(self.cliente.id),
            'curso': str(self.curso.id),
            'modo': 'modulo',
            'modulo_destino': str(self.m1.id),
            'estudiantes': [str(self.est.id)],
            'quitar_certificado': 'on',
            'quitar_examen': 'on',
        })
        self.assertEqual(r.status_code, 302)
        self.progreso.refresh_from_db()
        self.assertFalse(self.progreso.completado)
        self.assertEqual(self.progreso.modulos_completados.count(), 0)
        self.assertTrue(modulo_disponible_por_calendario(self.est, self.m1))

    @override_settings(
        SECURE_SSL_REDIRECT=False,
        STORAGES={
            'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
        },
    )
    def test_post_ajusta_hasta_micro(self):
        sec = SeccionModulo.objects.create(modulo=self.m1, orden=1, titulo='Bloque')
        PasoModulo.objects.create(
            modulo=self.m1, seccion=sec, orden=1, titulo='Uno',
            contenido='c1', tipo=PasoModulo.TIPO_CONTENIDO,
        )
        p2 = PasoModulo.objects.create(
            modulo=self.m1, seccion=sec, orden=2, titulo='Dos',
            contenido='c2', tipo=PasoModulo.TIPO_CONTENIDO,
        )
        self.http.login(username='admin_av', password='pass')
        r = self.http.post('/admin/ajustar-avance/', {
            'action': 'ajustar',
            'cliente': str(self.cliente.id),
            'curso': str(self.curso.id),
            'modo': 'modulo',
            'modulo_destino': str(self.m1.id),
            'paso_destino': str(p2.id),
            'estudiantes': [str(self.est.id)],
            'quitar_certificado': 'on',
            'quitar_examen': 'on',
        })
        self.assertEqual(r.status_code, 302)
        self.progreso.refresh_from_db()
        self.assertEqual(self.progreso.paso_actual_modulo, 2)

    @override_settings(
        SECURE_SSL_REDIRECT=False,
        STORAGES={
            'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
        },
    )
    def test_pagina_muestra_selector_micro(self):
        sec = SeccionModulo.objects.create(modulo=self.m1, orden=1, titulo='Autocuidado')
        PasoModulo.objects.create(
            modulo=self.m1, seccion=sec, orden=1, titulo='Respiración',
            contenido='Texto', tipo=PasoModulo.TIPO_CONTENIDO,
        )
        self.progreso.paso_actual_modulo = 1
        self.progreso.save(update_fields=['paso_actual_modulo'])
        self.http.login(username='admin_av', password='pass')
        url = f'/admin/ajustar-avance/?cliente={self.cliente.id}&curso={self.curso.id}'
        r = self.http.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Sección / microcontenido')
        self.assertContains(r, 'Respiración')
        self.assertContains(r, 'paso_destino')
