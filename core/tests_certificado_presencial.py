"""Tests certificados presenciales masivos."""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from core.certificado_presencial_service import crear_certificado_presencial, emitir_certificados_presenciales
from core.models import Cliente, Curso, Estudiante, Modulo, ProgresoEstudiante
from core.models_certificados import Certificado


class CertificadoPresencialServiceTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            nombre='Coop Pres',
            contacto_principal='A',
            email='p@test.com',
            telefono='573005555551',
            activo=True,
        )
        self.curso = Curso.objects.create(nombre='Taller Pres', cliente=self.cliente, activo=True)
        self.e1 = Estudiante.objects.create(
            cedula='10', nombre='Ana', telefono='573005555552', cliente=self.cliente, activo=True,
        )
        self.e2 = Estudiante.objects.create(
            cedula='20', nombre='Luis', telefono='573005555553', cliente=self.cliente, activo=True,
        )

    @patch('core.certificado_presencial_service.generar_y_guardar_certificado', return_value=True)
    def test_crear_sin_avance_whatsapp(self, _mock_gen):
        cert, estado = crear_certificado_presencial(self.e1, self.curso, calificacion=95)
        self.assertEqual(estado, 'creado')
        self.assertIsNotNone(cert)
        self.assertEqual(float(cert.calificacion_final), 95)
        self.assertTrue(cert.emitido)

    @patch('core.certificado_presencial_service.generar_y_guardar_certificado', return_value=True)
    def test_emitir_masivo(self, _mock_gen):
        resumen = emitir_certificados_presenciales({self.e1.id, self.e2.id}, self.curso, calificacion=100)
        self.assertEqual(resumen['creados'], 2)
        self.assertEqual(Certificado.objects.filter(curso=self.curso).count(), 2)

    @patch('core.certificado_presencial_service.generar_y_guardar_certificado', return_value=True)
    def test_no_duplica_sin_regenerar(self, _mock_gen):
        emitir_certificados_presenciales({self.e1.id}, self.curso)
        resumen = emitir_certificados_presenciales({self.e1.id}, self.curso)
        self.assertEqual(resumen['existentes'], 1)
        self.assertEqual(Certificado.objects.filter(estudiante=self.e1, curso=self.curso).count(), 1)


class CertificadoPresencialDualCursoTests(TestCase):
    """Presencial + digital en paralelo: dos certificados, sin tocar progreso."""

    def setUp(self):
        self.cliente = Cliente.objects.create(
            nombre='Cliente Dual',
            contacto_principal='A',
            email='dual@test.com',
            telefono='573008888881',
            activo=True,
        )
        self.curso_presencial = Curso.objects.create(
            nombre='Taller Presencial', cliente=self.cliente, activo=True,
        )
        self.curso_digital = Curso.objects.create(
            nombre='Programa Digital', cliente=self.cliente, activo=True,
        )
        self.m1 = Modulo.objects.create(
            curso=self.curso_digital, numero=1, titulo='M1', descripcion='d', contenido='c',
        )
        self.est = Estudiante.objects.create(
            cedula='dual1',
            nombre='María Dual',
            telefono='573008888882',
            cliente=self.cliente,
            activo=True,
            estado_chat='ACTIVO',
            estado_onboarding='completado',
        )
        self.progreso = ProgresoEstudiante.objects.create(
            estudiante=self.est,
            curso=self.curso_digital,
            modulo_actual=self.m1,
            completado=False,
        )

    @patch('core.certificado_presencial_service.generar_y_guardar_certificado', return_value=True)
    def test_presencial_no_toca_progreso_digital(self, _mock_gen):
        cert, estado = crear_certificado_presencial(self.est, self.curso_presencial)
        self.assertEqual(estado, 'creado')
        self.progreso.refresh_from_db()
        self.est.refresh_from_db()
        self.assertFalse(self.progreso.completado)
        self.assertEqual(self.est.estado_chat, 'ACTIVO')
        self.assertEqual(self.est.estado_onboarding, 'completado')
        self.assertEqual(cert.curso_id, self.curso_presencial.id)

    @patch('core.certificado_presencial_service.generar_y_guardar_certificado', return_value=True)
    def test_dos_certificados_cursos_distintos(self, _mock_gen):
        crear_certificado_presencial(self.est, self.curso_presencial)
        Certificado.objects.create(
            estudiante=self.est,
            curso=self.curso_digital,
            calificacion_final=88,
            fecha_inicio='2026-01-01',
            emitido=True,
        )
        self.assertEqual(Certificado.objects.filter(estudiante=self.est).count(), 2)
        self.assertEqual(
            set(Certificado.objects.filter(estudiante=self.est).values_list('curso_id', flat=True)),
            {self.curso_presencial.id, self.curso_digital.id},
        )

    @patch('core.certificado_presencial_service.generar_y_guardar_certificado', return_value=True)
    def test_emitir_presencial_con_digital_activo_cuenta_como_creado(self, _mock_gen):
        resumen = emitir_certificados_presenciales({self.est.id}, self.curso_presencial)
        self.assertEqual(resumen['creados'], 1)
        self.assertEqual(resumen['errores'], 0)
        self.progreso.refresh_from_db()
        self.assertFalse(self.progreso.completado)

    def test_filas_muestran_curso_digital_activo(self):
        from core.certificado_presencial_service import filas_estudiantes_certificado

        filas = filas_estudiantes_certificado(self.cliente, self.curso_presencial)
        fila = next(f for f in filas if f['estudiante'].id == self.est.id)
        self.assertIn('Programa Digital', fila['cursos_digitales_activos'])


class CertificadoOtroClienteTests(TestCase):
    @patch('core.certificado_presencial_service.generar_y_guardar_certificado', return_value=True)
    def test_certificado_curso_evento_estudiante_otro_cliente(self, _mock_gen):
        org_evento = Cliente.objects.create(
            nombre='Evento', contacto_principal='A', email='ev@test.com',
            telefono='573008888881', activo=True,
        )
        org_otro = Cliente.objects.create(
            nombre='Coop Digital', contacto_principal='B', email='dig@test.com',
            telefono='573008888882', activo=True,
        )
        curso_pres = Curso.objects.create(nombre='Taller', cliente=org_evento, activo=True)
        est = Estudiante.objects.create(
            cedula='oc1', nombre='Cross Client', telefono='573008888883',
            cliente=org_otro, activo=True, estado_chat='ACTIVO',
        )
        cert, estado = crear_certificado_presencial(
            est, curso_pres, permitir_otro_cliente=True,
        )
        self.assertEqual(estado, 'creado')
        self.assertIsNotNone(cert)
        est.refresh_from_db()
        self.assertEqual(est.estado_chat, 'ACTIVO')


class CertificadoPresencialAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('admin_cp', 'cp@c.com', 'pass')
        self.cliente = Cliente.objects.create(
            nombre='Org CP', contacto_principal='B', email='ocp@test.com',
            telefono='573006666661', activo=True,
        )
        self.curso = Curso.objects.create(nombre='CP', cliente=self.cliente, activo=True)
        self.http = Client()

    @override_settings(
        STORAGES={
            'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
        },
    )
    def test_pagina_carga(self):
        self.http.login(username='admin_cp', password='pass')
        r = self.http.get(
            f'/admin/envio-certificados/?cliente={self.cliente.id}&curso={self.curso.id}'
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Envío certificados')

    @override_settings(
        STORAGES={
            'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
        },
    )
    def test_muestra_guia_marcadores(self):
        self.http.login(username='admin_cp', password='pass')
        r = self.http.get(
            f'/admin/envio-certificados/?cliente={self.cliente.id}&curso={self.curso.id}'
        )
        self.assertContains(r, 'Gris RGB')
        self.assertContains(r, 'Vista previa')

    @override_settings(
        STORAGES={
            'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
        },
    )
    @patch('core.certificado_admin_preview.generar_preview_certificado')
    def test_preview_devuelve_png(self, mock_preview):
        from io import BytesIO
        from core.models_certificados import PlantillaCertificado

        mock_preview.return_value = BytesIO(b'fakepng')
        PlantillaCertificado.objects.create(
            nombre='Preview',
            cliente=self.cliente,
            curso=self.curso,
            modo_plantilla='diseno_eki',
            activa=True,
            por_defecto=True,
        )
        Estudiante.objects.create(
            cedula='99', nombre='Preview Est', telefono='573006666662',
            cliente=self.cliente, activo=True,
        )
        self.http.login(username='admin_cp', password='pass')
        r = self.http.post(
            f'/admin/envio-certificados/?cliente={self.cliente.id}&curso={self.curso.id}',
            {
                'action': 'preview',
                'cliente': str(self.cliente.id),
                'curso': str(self.curso.id),
            },
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'image/png')
