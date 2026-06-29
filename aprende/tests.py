"""Tests básicos del aula web /aprende/."""

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase

from aprende.models import EntregaTarea, TareaCurso

from core.models import Cliente, Curso, Estudiante, Modulo, ProgresoEstudiante
from portal.models import PortalUsuario


class AprendeWebTests(TestCase):
    def setUp(self):
        self.http = Client()
        self.cliente = Cliente.objects.create(
            nombre='Org Aprende',
            contacto_principal='A',
            email='ap@test.com',
            telefono='573009999001',
            activo=True,
        )
        self.curso = Curso.objects.create(nombre='Curso Web', cliente=self.cliente, activo=True)
        self.modulo = Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='Intro',
            descripcion='d',
            contenido='Hola desde la web',
        )
        self.est = Estudiante.objects.create(
            cedula='web1',
            nombre='Est Web',
            telefono='573009999002',
            cliente=self.cliente,
            activo=True,
        )
        ProgresoEstudiante.objects.create(estudiante=self.est, curso=self.curso, modulo_actual=self.modulo)
        self.user = User.objects.create_user('prof_ap', 'p@t.com', 'pass')
        PortalUsuario.objects.create(user=self.user, organizacion=self.cliente, rol='profesor')

    def test_inicio_carga(self):
        r = self.http.get('/aprende/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Estudiante')
        self.assertContains(r, 'Aula virtual')

    def test_estudiante_login_y_ve_modulo(self):
        r = self.http.post('/aprende/estudiante/login/', {
            'cedula': 'web1',
            'telefono': '573009999002',
        })
        self.assertEqual(r.status_code, 302)
        r2 = self.http.get(f'/aprende/estudiante/modulo/{self.modulo.id}/')
        self.assertEqual(r2.status_code, 200)
        self.assertContains(r2, 'Hola desde la web')

    def test_estudiante_login_telefono_sin_57(self):
        r = self.http.post('/aprende/estudiante/login/', {
            'cedula': 'web1',
            'telefono': '3009999002',
        })
        self.assertEqual(r.status_code, 302)

    def test_profesor_ve_cursos(self):
        self.http.post('/aprende/profesor/login/', {'username': 'prof_ap', 'password': 'pass'})
        r = self.http.get('/aprende/profesor/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Curso Web')

    def test_subdominio_aprende_redirige_raiz(self):
        r = self.http.get('/', HTTP_HOST='aprende.eki.technology')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, '/aprende/')

    def test_subdominio_aula_redirige_raiz(self):
        r = self.http.get('/', HTTP_HOST='aula.eki.technology')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, '/aprende/')

    def test_catalogo_e_inscripcion(self):
        curso2 = Curso.objects.create(
            nombre='Curso Catálogo',
            descripcion='Para elegir',
            cliente=self.cliente,
            activo=True,
            visible_en_aula=True,
        )
        Modulo.objects.create(
            curso=curso2, numero=1, titulo='L1', descripcion='', contenido='x',
        )
        est2 = Estudiante.objects.create(
            cedula='web2',
            nombre='Est Cat',
            telefono='573009999003',
            cliente=self.cliente,
            activo=True,
        )
        self.http.post('/aprende/estudiante/login/', {
            'cedula': 'web2',
            'telefono': '3009999003',
        })
        r = self.http.get('/aprende/estudiante/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Catálogo')
        self.assertContains(r, 'Curso Catálogo')
        r2 = self.http.post(f'/aprende/estudiante/inscribir/{curso2.id}/')
        self.assertEqual(r2.status_code, 302)
        self.assertTrue(
            ProgresoEstudiante.objects.filter(estudiante=est2, curso=curso2).exists()
        )

    def test_no_inscribir_curso_de_otra_org(self):
        otra = Cliente.objects.create(
            nombre='Otra Org',
            contacto_principal='B',
            email='b@t.com',
            telefono='573009999004',
            activo=True,
        )
        ajeno = Curso.objects.create(
            nombre='Curso Ajeno',
            descripcion='x',
            cliente=otra,
            activo=True,
            visible_en_aula=True,
        )
        self.http.post('/aprende/estudiante/login/', {
            'cedula': 'web1',
            'telefono': '3009999002',
        })
        r = self.http.post(f'/aprende/estudiante/inscribir/{ajeno.id}/')
        self.assertEqual(r.status_code, 302)
        self.assertFalse(
            ProgresoEstudiante.objects.filter(estudiante=self.est, curso=ajeno).exists()
        )

    def test_curso_general_en_catalogo(self):
        general = Curso.objects.create(
            nombre='Curso General',
            descripcion='Para todos',
            cliente=None,
            activo=True,
            visible_en_aula=True,
        )
        est2 = Estudiante.objects.create(
            cedula='web3',
            nombre='Est Gen',
            telefono='573009999005',
            cliente=self.cliente,
            activo=True,
        )
        self.http.post('/aprende/estudiante/login/', {
            'cedula': 'web3',
            'telefono': '3009999005',
        })
        r = self.http.get('/aprende/estudiante/')
        self.assertContains(r, 'Curso General')

    def test_profesor_crea_tarea_y_estudiante_entrega(self):
        self.http.post('/aprende/profesor/login/', {'username': 'prof_ap', 'password': 'pass'})
        r = self.http.post(f'/aprende/profesor/curso/{self.curso.id}/tarea/nueva/', {
            'titulo': 'Informe final',
            'instrucciones': 'Sube PDF',
        })
        self.assertEqual(r.status_code, 302)
        tarea = TareaCurso.objects.get(titulo='Informe final')
        self.http.post('/aprende/estudiante/login/', {
            'cedula': 'web1',
            'telefono': '3009999002',
        })
        archivo = SimpleUploadedFile('tarea.pdf', b'%PDF-1.4 test', content_type='application/pdf')
        r2 = self.http.post(f'/aprende/estudiante/tarea/{tarea.id}/', {
            'archivo': archivo,
            'comentario': 'Listo profe',
        })
        self.assertEqual(r2.status_code, 302)
        self.assertTrue(EntregaTarea.objects.filter(tarea=tarea, estudiante=self.est).exists())

    def test_profesor_califica_entrega(self):
        tarea = TareaCurso.objects.create(curso=self.curso, titulo='T1', instrucciones='x')
        archivo = SimpleUploadedFile('t.pdf', b'%PDF', content_type='application/pdf')
        entrega = EntregaTarea.objects.create(
            tarea=tarea, estudiante=self.est, archivo=archivo, nombre_archivo='t.pdf',
        )
        self.http.post('/aprende/profesor/login/', {'username': 'prof_ap', 'password': 'pass'})
        r = self.http.post(f'/aprende/profesor/tarea/{tarea.id}/entregas/', {
            'entrega_id': entrega.id,
            'nota': '4',
            'comentario_profesor': 'Buen trabajo',
        })
        self.assertEqual(r.status_code, 302)
        entrega.refresh_from_db()
        self.assertEqual(entrega.nota, 4)
        self.assertEqual(entrega.comentario_profesor, 'Buen trabajo')

    def test_aula_solo_modulos_habilitados_por_admin(self):
        from datetime import timedelta

        from django.utils import timezone

        from core.models import HabilitacionModuloEstudiante

        self.cliente.drip_modulos_solo_estudiantes_listados = True
        self.cliente.save(update_fields=['drip_modulos_solo_estudiantes_listados'])
        m2 = Modulo.objects.create(
            curso=self.curso, numero=2, titulo='Modulo 2', descripcion='', contenido='Secreto',
        )
        HabilitacionModuloEstudiante.objects.create(
            estudiante=self.est,
            curso=self.curso,
            modulo=self.modulo,
            habilitado_desde=timezone.now() - timedelta(hours=1),
        )
        self.http.post('/aprende/estudiante/login/', {
            'cedula': 'web1',
            'telefono': '3009999002',
        })
        r = self.http.get(f'/aprende/estudiante/curso/{self.curso.id}/')
        self.assertContains(r, 'Intro')
        self.assertNotContains(r, 'Modulo 2')
        r2 = self.http.get(f'/aprende/estudiante/modulo/{m2.id}/')
        self.assertEqual(r2.status_code, 302)

    def test_aula_sin_lista_solo_hasta_modulo_actual(self):
        m2 = Modulo.objects.create(
            curso=self.curso, numero=2, titulo='Futuro', descripcion='', contenido='No aún',
        )
        self.http.post('/aprende/estudiante/login/', {
            'cedula': 'web1',
            'telefono': '3009999002',
        })
        r = self.http.get(f'/aprende/estudiante/curso/{self.curso.id}/')
        self.assertContains(r, 'Intro')
        self.assertNotContains(r, 'Futuro')
        r2 = self.http.get(f'/aprende/estudiante/modulo/{m2.id}/')
        self.assertEqual(r2.status_code, 302)

    def test_biblioteca_muestra_archivos_modulo_liberado(self):
        from core.models_extras import ArchivoModulo

        ArchivoModulo.objects.create(
            modulo=self.modulo,
            tipo='pdf',
            titulo='Guía WA',
            activo=True,
        )
        self.http.post('/aprende/estudiante/login/', {
            'cedula': 'web1',
            'telefono': '3009999002',
        })
        r = self.http.get('/aprende/estudiante/biblioteca/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Biblioteca de recursos')
        self.assertContains(r, 'Guía WA')
        self.assertContains(r, self.curso.nombre)

    def test_modulo_muestra_secciones_y_media_solo_consulta(self):
        from core.models import PasoModulo, SeccionModulo

        sec = SeccionModulo.objects.create(
            modulo=self.modulo, orden=1, titulo='Fundamentos',
        )
        PasoModulo.objects.create(
            modulo=self.modulo,
            seccion=sec,
            orden=1,
            tipo=PasoModulo.TIPO_CONTENIDO,
            contenido='Contenido del micro paso.',
            media_url='https://www.youtube.com/watch?v=dQw4w9WgXcQ',
        )
        self.http.post('/aprende/estudiante/login/', {
            'cedula': 'web1',
            'telefono': '3009999002',
        })
        r = self.http.get(f'/aprende/estudiante/modulo/{self.modulo.id}/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Fundamentos')
        self.assertContains(r, 'Contenido del micro paso')
        self.assertContains(r, 'youtube.com/embed/')
        self.assertContains(r, 'consulta en línea')
        self.assertNotContains(r, 'Descargar documento')

    def test_aula_oculta_modulo_con_drip_tras_completar_anterior(self):
        from datetime import timedelta

        from django.utils import timezone

        from core.models import ModuloCompletado

        m2 = Modulo.objects.create(
            curso=self.curso, numero=2, titulo='Bloqueado drip', descripcion='', contenido='Espera',
        )
        m2.habilitado_desde = timezone.now() + timedelta(days=5)
        m2.save(update_fields=['habilitado_desde'])
        progreso = ProgresoEstudiante.objects.get(estudiante=self.est, curso=self.curso)
        ModuloCompletado.objects.create(progreso=progreso, modulo=self.modulo)
        progreso.modulo_actual = m2
        progreso.fecha_ultimo_avance = timezone.now()
        progreso.save(update_fields=['modulo_actual', 'fecha_ultimo_avance'])

        self.http.post('/aprende/estudiante/login/', {
            'cedula': 'web1',
            'telefono': '3009999002',
        })
        r = self.http.get(f'/aprende/estudiante/curso/{self.curso.id}/')
        self.assertContains(r, 'Intro')
        self.assertNotContains(r, 'Bloqueado drip')
        r2 = self.http.get(f'/aprende/estudiante/modulo/{m2.id}/')
        self.assertEqual(r2.status_code, 302)

    def test_estudiante_perfil_y_puntos(self):
        from core.gamificacion import PerfilGamificacion

        perfil, _ = PerfilGamificacion.objects.get_or_create(estudiante=self.est)
        perfil.puntos_totales = 120
        perfil.nivel = 3
        perfil.save(update_fields=['puntos_totales', 'nivel'])
        self.http.post('/aprende/estudiante/login/', {
            'cedula': 'web1',
            'telefono': '3009999002',
        })
        r = self.http.get('/aprende/estudiante/perfil/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, '120')
        self.assertContains(r, 'Mi perfil')

        r2 = self.http.post('/aprende/estudiante/perfil/', {
            'accion': 'perfil',
            'nombre': 'Est Web Actualizado',
            'municipio': 'Medellín',
            'departamento': 'Antioquia',
            'genero': 'M',
            'edad': '28',
        })
        self.assertEqual(r2.status_code, 302)
        self.est.refresh_from_db()
        self.assertEqual(self.est.nombre, 'Est Web Actualizado')
        self.assertEqual(self.est.municipio, 'Medellín')

    def test_estudiante_sube_documento_en_modulo(self):
        from aprende.models import DocumentoEstudianteAula

        self.http.post('/aprende/estudiante/login/', {
            'cedula': 'web1',
            'telefono': '3009999002',
        })
        archivo = SimpleUploadedFile('evidencia.pdf', b'%PDF-1.4 test', content_type='application/pdf')
        r = self.http.post(f'/aprende/estudiante/modulo/{self.modulo.id}/', {
            'accion': 'subir_documento',
            'titulo': 'Mi evidencia',
            'descripcion': 'Prueba',
            'archivo': archivo,
        })
        self.assertEqual(r.status_code, 302)
        self.assertTrue(
            DocumentoEstudianteAula.objects.filter(
                estudiante=self.est, modulo=self.modulo, titulo='Mi evidencia',
            ).exists()
        )
