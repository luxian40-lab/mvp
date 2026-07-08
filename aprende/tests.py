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
        ArchivoModulo.objects.create(
            modulo=self.modulo,
            tipo='imagen',
            titulo='Foto campo',
            url_externa='https://eki-produccion.s3.us-east-2.amazonaws.com/media/test.jpg',
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
        self.assertContains(r, 'Módulo 1')
        self.assertContains(r, self.curso.nombre)
        self.assertContains(r, 'eki-bib-grid')
        self.assertContains(r, 'eki-bib-thumb')
        self.assertContains(r, 'aria-label="Ver Foto campo"')
        self.assertContains(r, 'width="35" height="35"')
        self.assertContains(r, 'eki-bib-lightbox')
        self.assertContains(r, 'title="Guía WA"')

    def test_biblioteca_incluye_media_microcontenido(self):
        from core.models import PasoModulo, SeccionModulo

        sec = SeccionModulo.objects.create(
            modulo=self.modulo, orden=1, titulo='Fundamentos',
        )
        PasoModulo.objects.create(
            modulo=self.modulo,
            seccion=sec,
            orden=1,
            titulo='Video intro micro',
            tipo=PasoModulo.TIPO_CONTENIDO,
            contenido='Texto del paso.',
            media_url='https://www.youtube.com/watch?v=dQw4w9WgXcQ',
        )
        PasoModulo.objects.create(
            modulo=self.modulo,
            seccion=sec,
            orden=2,
            tipo=PasoModulo.TIPO_CONTENIDO,
            contenido='Solo texto, sin media.',
        )
        self.http.post('/aprende/estudiante/login/', {
            'cedula': 'web1',
            'telefono': '3009999002',
        })
        r = self.http.get('/aprende/estudiante/biblioteca/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Video intro micro')
        self.assertContains(r, 'aria-label="Ver Video intro micro"')
        self.assertContains(r, 'img.youtube.com/vi/dQw4w9WgXcQ/default.jpg')

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

    def test_estudiante_pagina_tareas_sin_subida_en_modulo(self):
        TareaCurso.objects.create(curso=self.curso, titulo='Entrega 1', instrucciones='Sube PDF')
        self.http.post('/aprende/estudiante/login/', {
            'cedula': 'web1',
            'telefono': '3009999002',
        })
        r = self.http.get('/aprende/estudiante/tareas/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Entrega 1')
        r2 = self.http.get(f'/aprende/estudiante/modulo/{self.modulo.id}/')
        self.assertEqual(r2.status_code, 200)
        self.assertNotContains(r2, 'Subir documento')

    def test_ranking_grupo_en_perfil(self):
        from core.gamificacion import PerfilGamificacion
        from core.models_extras import GrupoEstudiantes

        est2 = Estudiante.objects.create(
            cedula='web_rank',
            nombre='Compañero',
            telefono='573009999099',
            cliente=self.cliente,
            activo=True,
        )
        grupo = GrupoEstudiantes.objects.create(nombre='Grupo Norte', cliente=self.cliente, activo=True)
        grupo.estudiantes.add(self.est, est2)
        grupo.cursos.add(self.curso)
        p1, _ = PerfilGamificacion.objects.get_or_create(estudiante=self.est)
        p1.puntos_totales = 50
        p1.save(update_fields=['puntos_totales'])
        p2, _ = PerfilGamificacion.objects.get_or_create(estudiante=est2)
        p2.puntos_totales = 200
        p2.save(update_fields=['puntos_totales'])

        self.http.post('/aprende/estudiante/login/', {
            'cedula': 'web1',
            'telefono': '3009999002',
        })
        r = self.http.get('/aprende/estudiante/perfil/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Grupo Norte')
        self.assertContains(r, 'Compañero')
        self.assertContains(r, 'Tú')

    def test_curso_pestanas_modulos_y_tareas(self):
        TareaCurso.objects.create(curso=self.curso, titulo='Tarea curso', instrucciones='x')
        self.http.post('/aprende/estudiante/login/', {
            'cedula': 'web1',
            'telefono': '3009999002',
        })
        r = self.http.get(f'/aprende/estudiante/curso/{self.curso.id}/')
        self.assertContains(r, 'Módulos')
        self.assertContains(r, 'Tareas')
        self.assertContains(r, 'Ranking')
        r2 = self.http.get(f'/aprende/estudiante/curso/{self.curso.id}/tareas/')
        self.assertEqual(r2.status_code, 200)
        self.assertContains(r2, 'Tarea curso')

    def test_ranking_curso_por_grupo(self):
        from core.gamificacion import PerfilGamificacion
        from core.models_extras import GrupoEstudiantes

        est2 = Estudiante.objects.create(
            cedula='web_rank2',
            nombre='Líder grupo',
            telefono='573009999088',
            cliente=self.cliente,
            activo=True,
        )
        grupo = GrupoEstudiantes.objects.create(nombre='Grupo Curso', cliente=self.cliente, activo=True)
        grupo.estudiantes.add(self.est, est2)
        grupo.cursos.add(self.curso)

        p1, _ = PerfilGamificacion.objects.get_or_create(estudiante=self.est)
        p1.puntos_totales = 30
        p1.save(update_fields=['puntos_totales'])
        p2, _ = PerfilGamificacion.objects.get_or_create(estudiante=est2)
        p2.puntos_totales = 120
        p2.save(update_fields=['puntos_totales'])

        self.http.post('/aprende/estudiante/login/', {
            'cedula': 'web1',
            'telefono': '3009999002',
        })
        r = self.http.get(f'/aprende/estudiante/curso/{self.curso.id}/ranking/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Ranking del curso')
        self.assertContains(r, 'Grupo Curso')
        self.assertContains(r, 'Líder Grupo')
        self.assertContains(r, 'eki-leaderboard-score__num">120')
        self.assertContains(r, 'Tu puesto')
        self.assertContains(r, 'Te faltan')


class AprendeProfesorAuthTests(TestCase):
    """Portal B2B y aula docente comparten sesión; is_staff no debe bloquear."""

    def setUp(self):
        self.http = Client()
        self.cliente = Cliente.objects.create(
            nombre='Org Docente',
            contacto_principal='A',
            email='doc@test.com',
            telefono='573008888001',
            activo=True,
            fecha_fin_suscripcion='2099-12-31',
        )
        self.curso = Curso.objects.create(nombre='Curso Doc', cliente=self.cliente, activo=True)
        self.user_staff = User.objects.create_user('coord_admin', 'c@t.com', 'pass1234')
        self.user_staff.is_staff = True
        self.user_staff.save(update_fields=['is_staff'])
        PortalUsuario.objects.create(
            user=self.user_staff, organizacion=self.cliente, rol='admin',
        )
        self.viewer = User.objects.create_user('solo_ver', 'v@t.com', 'pass1234')
        PortalUsuario.objects.create(
            user=self.viewer, organizacion=self.cliente, rol='viewer',
        )

    def test_staff_admin_entra_aprende_profesor(self):
        r = self.http.post('/aprende/profesor/login/', {
            'username': 'coord_admin',
            'password': 'pass1234',
        })
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, '/aprende/profesor/')
        r2 = self.http.get('/aprende/profesor/')
        self.assertEqual(r2.status_code, 200)
        self.assertContains(r2, 'Curso Doc')

    def test_sesion_portal_abre_aula_sin_relogin(self):
        self.http.post('/portal/login/', {'username': 'coord_admin', 'password': 'pass1234'})
        r = self.http.get('/aprende/profesor/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Curso Doc')

    def test_viewer_no_entra_aula_docente(self):
        r = self.http.post('/aprende/profesor/login/', {
            'username': 'solo_ver',
            'password': 'pass1234',
        })
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Administrador o Profesor')


class AprendeProfesorGestionTests(TestCase):
    """Tareas editar/borrar, asistencia y calificaciones en aula docente."""

    def setUp(self):
        self.http = Client()
        self.cliente = Cliente.objects.create(
            nombre='Org Gestión',
            contacto_principal='A',
            email='gest@test.com',
            telefono='573007777001',
            activo=True,
            modo_gamificacion='calificacion',
        )
        self.curso = Curso.objects.create(nombre='Curso Gest', cliente=self.cliente, activo=True)
        self.modulo = Modulo.objects.create(
            curso=self.curso, numero=1, titulo='M1', descripcion='', contenido='x',
        )
        self.est = Estudiante.objects.create(
            cedula='gest1', nombre='Est Gest', telefono='573007777002',
            cliente=self.cliente, activo=True,
        )
        ProgresoEstudiante.objects.create(estudiante=self.est, curso=self.curso, modulo_actual=self.modulo)
        self.user = User.objects.create_user('prof_gest', 'pg@t.com', 'pass')
        PortalUsuario.objects.create(user=self.user, organizacion=self.cliente, rol='profesor')
        self.http.post('/aprende/profesor/login/', {'username': 'prof_gest', 'password': 'pass'})

    def test_editar_y_desactivar_tarea(self):
        tarea = TareaCurso.objects.create(curso=self.curso, titulo='Original', instrucciones='a')
        archivo = SimpleUploadedFile('x.pdf', b'%PDF', content_type='application/pdf')
        EntregaTarea.objects.create(
            tarea=tarea, estudiante=self.est,
            archivo=archivo, nombre_archivo='x.pdf',
        )
        r = self.http.post(f'/aprende/profesor/tarea/{tarea.id}/editar/', {
            'titulo': 'Actualizada',
            'instrucciones': 'b',
            'activa': '',
        })
        self.assertEqual(r.status_code, 302)
        tarea.refresh_from_db()
        self.assertEqual(tarea.titulo, 'Actualizada')
        self.assertFalse(tarea.activa)

        r2 = self.http.post(f'/aprende/profesor/tarea/{tarea.id}/eliminar/')
        self.assertEqual(r2.status_code, 302)
        self.assertTrue(TareaCurso.objects.filter(pk=tarea.pk).exists())
        tarea.refresh_from_db()
        self.assertFalse(tarea.activa)

    def test_eliminar_tarea_sin_entregas(self):
        tarea = TareaCurso.objects.create(curso=self.curso, titulo='Borrar', instrucciones='x')
        r = self.http.post(f'/aprende/profesor/tarea/{tarea.id}/eliminar/')
        self.assertEqual(r.status_code, 302)
        self.assertFalse(TareaCurso.objects.filter(pk=tarea.pk).exists())

    def test_asistencia_y_calificacion(self):
        from core.gamificacion import EvaluacionNotaGamificacion

        r = self.http.post(f'/aprende/profesor/curso/{self.curso.id}/asistencia/', {
            'fecha': '2026-07-06',
            'presente': [str(self.est.pk)],
        })
        self.assertEqual(r.status_code, 302)
        self.assertTrue(
            EvaluacionNotaGamificacion.objects.filter(
                estudiante=self.est, curso=self.curso, tipo='asistencia',
            ).exists()
        )

        r2 = self.http.get(f'/aprende/profesor/curso/{self.curso.id}/calificaciones/')
        self.assertEqual(r2.status_code, 200)
        self.assertContains(r2, 'Est Gest')

        r3 = self.http.post(f'/aprende/profesor/curso/{self.curso.id}/calificaciones/', {
            'accion': 'nota_manual',
            'estudiante_id': str(self.est.pk),
            'nota': '4',
            'detalle': 'Participación',
        })
        self.assertEqual(r3.status_code, 302)
        self.assertTrue(
            EvaluacionNotaGamificacion.objects.filter(estudiante=self.est, tipo='manual').exists()
        )
