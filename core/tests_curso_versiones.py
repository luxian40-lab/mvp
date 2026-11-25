"""Bloque 4 — versiones de curso. Flag apagado: sin efecto en entrega."""
from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings

from core.cursos.autoria.contrato import (
    COHORTE_FIJA_A_VERSION_DE_INSCRIPCION,
    CONTINUEMOS_ENTREGA_UN_BLOQUE,
    PUBLICAR_CREA_VERSION_INMUTABLE,
)
from core.cursos.autoria.ensamblado import congelar_ensamblado
from core.cursos.autoria.servicio import (
    migrar_cohorte,
    publicar,
    version_de_progreso,
    versiones_activas,
)


class ContratoAutoriaTests(SimpleTestCase):
    def test_contrato_fija_reglas_del_bloque_4(self):
        self.assertTrue(CONTINUEMOS_ENTREGA_UN_BLOQUE)
        self.assertTrue(PUBLICAR_CREA_VERSION_INMUTABLE)
        self.assertTrue(COHORTE_FIJA_A_VERSION_DE_INSCRIPCION)

    def test_flag_default_apagado(self):
        self.assertFalse(settings.EKI_CURSO_VERSIONES)
        self.assertFalse(versiones_activas())


class VersionesServicioTests(TestCase):
    def test_flag_off_version_de_progreso_es_none(self):
        class Fake:
            curso_version_id = 99
            curso_version = object()

        with override_settings(EKI_CURSO_VERSIONES=False):
            self.assertIsNone(version_de_progreso(Fake()))

    @override_settings(EKI_CURSO_VERSIONES=True)
    def test_flag_on_lee_curso_version(self):
        sentinela = object()

        class Fake:
            curso_version_id = 1
            curso_version = sentinela

        self.assertIs(version_de_progreso(Fake()), sentinela)

    def test_crear_version_no_rompe_progreso_sin_fk(self):
        from core.models import Curso, CursoVersion, Estudiante, ProgresoEstudiante

        curso = Curso.objects.create(nombre='Curso versión test', descripcion='x')
        est = Estudiante.objects.create(
            nombre='QA Versiones',
            telefono='573009990044',
            cedula='CC990044',
            activo=True,
        )
        prog = ProgresoEstudiante.objects.create(estudiante=est, curso=curso)
        self.assertIsNone(prog.curso_version_id)
        self.assertIsNone(curso.version_publicada_id)

        v = CursoVersion.objects.create(curso=curso, numero=1, estado=CursoVersion.BORRADOR)
        self.assertEqual(v.numero, 1)
        prog.refresh_from_db()
        self.assertIsNone(prog.curso_version_id)
        with override_settings(EKI_CURSO_VERSIONES=False):
            self.assertIsNone(version_de_progreso(prog))

    def test_publicar_flag_off_no_escribe(self):
        from core.models import Curso, CursoVersion

        curso = Curso.objects.create(nombre='Curso no publica', descripcion='x')
        with override_settings(EKI_CURSO_VERSIONES=False):
            self.assertIsNone(publicar(curso, nota='no'))
        self.assertEqual(CursoVersion.objects.filter(curso=curso).count(), 0)
        curso.refresh_from_db()
        self.assertIsNone(curso.version_publicada_id)

    @override_settings(EKI_CURSO_VERSIONES=True)
    def test_publicar_congela_y_no_mueve_progreso(self):
        from core.models import (
            Curso,
            CursoVersion,
            Estudiante,
            Modulo,
            PasoModulo,
            ProgresoEstudiante,
            SeccionModulo,
        )

        curso = Curso.objects.create(nombre='Curso publica', descripcion='d')
        mod = Modulo.objects.create(
            curso=curso, numero=1, titulo='M1', descripcion='d', contenido='hola',
        )
        sec = SeccionModulo.objects.create(modulo=mod, orden=1, titulo='B1')
        PasoModulo.objects.create(
            modulo=mod, seccion=sec, orden=1, tipo=PasoModulo.TIPO_CONTENIDO,
            contenido='paso uno', activo=True,
        )
        est = Estudiante.objects.create(
            nombre='Cohorte fija', telefono='573009990055', cedula='CC990055', activo=True,
        )
        prog = ProgresoEstudiante.objects.create(estudiante=est, curso=curso)

        v1 = publicar(curso, nota='primera')
        self.assertIsNotNone(v1)
        self.assertEqual(v1.numero, 1)
        self.assertEqual(v1.estado, CursoVersion.PUBLICADO)
        self.assertEqual(v1.ensamblado.get('schema'), 1)
        self.assertEqual(len(v1.ensamblado.get('modulos') or []), 1)
        self.assertEqual(v1.ensamblado['modulos'][0]['secciones'][0]['pasos'][0]['contenido'], 'paso uno')
        curso.refresh_from_db()
        self.assertEqual(curso.version_publicada_id, v1.id)
        prog.refresh_from_db()
        self.assertIsNone(prog.curso_version_id)

        mod.titulo = 'M1 editado vivo'
        mod.save(update_fields=['titulo'])
        v2 = publicar(curso, nota='segunda')
        self.assertEqual(v2.numero, 2)
        v1.refresh_from_db()
        self.assertEqual(v1.estado, CursoVersion.ARCHIVADO)
        self.assertEqual(v1.ensamblado['modulos'][0]['titulo'], 'M1')
        self.assertEqual(v2.ensamblado['modulos'][0]['titulo'], 'M1 editado vivo')
        curso.refresh_from_db()
        self.assertEqual(curso.version_publicada_id, v2.id)
        prog.refresh_from_db()
        self.assertIsNone(prog.curso_version_id)

    def test_congelar_ensamblado_schema(self):
        from core.models import Curso, Modulo

        curso = Curso.objects.create(nombre='Snap', descripcion='d')
        Modulo.objects.create(curso=curso, numero=0, titulo='Intro', descripcion='', contenido='')
        snap = congelar_ensamblado(curso)
        self.assertEqual(snap['schema'], 1)
        self.assertEqual(snap['curso_id'], curso.id)
        self.assertEqual(snap['modulos'][0]['numero'], 0)

    def test_inscribir_flag_off_sin_version(self):
        from core.inscripcion_curso import inscribir_estudiante_en_curso
        from core.models import Curso, Estudiante, Modulo

        curso = Curso.objects.create(nombre='Insc off', descripcion='d')
        Modulo.objects.create(curso=curso, numero=1, titulo='M1', descripcion='', contenido='x')
        est = Estudiante.objects.create(
            nombre='Sin version', telefono='573009990066', cedula='CC990066', activo=True,
        )
        with override_settings(EKI_CURSO_VERSIONES=False):
            prog, creado = inscribir_estudiante_en_curso(est, curso)
        self.assertTrue(creado)
        self.assertIsNone(prog.curso_version_id)

    @override_settings(EKI_CURSO_VERSIONES=True)
    def test_inscribir_fija_version_publicada_sin_mover_viejos(self):
        from core.inscripcion_curso import inscribir_estudiante_en_curso
        from core.models import Curso, Estudiante, Modulo, ProgresoEstudiante

        curso = Curso.objects.create(nombre='Insc on', descripcion='d')
        Modulo.objects.create(curso=curso, numero=1, titulo='M1', descripcion='', contenido='x')
        viejo = Estudiante.objects.create(
            nombre='Ya inscrito', telefono='573009990077', cedula='CC990077', activo=True,
        )
        prog_viejo = ProgresoEstudiante.objects.create(estudiante=viejo, curso=curso)
        self.assertIsNone(prog_viejo.curso_version_id)

        publicada = publicar(curso, nota='v1')
        self.assertIsNotNone(publicada)
        prog_viejo.refresh_from_db()
        self.assertIsNone(prog_viejo.curso_version_id)

        nuevo = Estudiante.objects.create(
            nombre='Nuevo', telefono='573009990088', cedula='CC990088', activo=True,
        )
        prog_nuevo, creado = inscribir_estudiante_en_curso(nuevo, curso)
        self.assertTrue(creado)
        self.assertEqual(prog_nuevo.curso_version_id, publicada.id)

    def test_migrar_cohorte_flag_off_cero(self):
        from core.models import Curso

        curso = Curso.objects.create(nombre='Mig off', descripcion='d')
        with override_settings(EKI_CURSO_VERSIONES=False):
            self.assertEqual(migrar_cohorte(curso), 0)

    @override_settings(EKI_CURSO_VERSIONES=True)
    def test_migrar_cohorte_ancla_activos_sin_tocar_completados(self):
        from core.models import Curso, Estudiante, Modulo, ProgresoEstudiante

        curso = Curso.objects.create(nombre='Mig on', descripcion='d')
        Modulo.objects.create(curso=curso, numero=1, titulo='M1', descripcion='', contenido='x')
        v1 = publicar(curso, nota='v1')
        activo = Estudiante.objects.create(
            nombre='Activo', telefono='573009990099', cedula='CC990099', activo=True,
        )
        hecho = Estudiante.objects.create(
            nombre='Hecho', telefono='573009990100', cedula='CC990100', activo=True,
        )
        prog_a = ProgresoEstudiante.objects.create(estudiante=activo, curso=curso)
        prog_h = ProgresoEstudiante.objects.create(
            estudiante=hecho, curso=curso, completado=True,
        )
        self.assertIsNone(prog_a.curso_version_id)
        n = migrar_cohorte(curso)
        self.assertEqual(n, 1)
        prog_a.refresh_from_db()
        prog_h.refresh_from_db()
        self.assertEqual(prog_a.curso_version_id, v1.id)
        self.assertIsNone(prog_h.curso_version_id)

        v2 = publicar(curso, nota='v2')
        n2 = migrar_cohorte(curso)
        self.assertEqual(n2, 1)
        prog_a.refresh_from_db()
        self.assertEqual(prog_a.curso_version_id, v2.id)


class PublicarVersionAdminTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.user = User.objects.create_superuser(
            username='qa_versiones',
            email='qa_versiones@example.com',
            password='test-pass-versiones',
        )
        self.client.force_login(self.user)

    def _post_action(self, curso_id, *, post_yes=False, nota=''):
        from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
        from django.urls import reverse

        data = {
            'action': 'publicar_version_accion',
            ACTION_CHECKBOX_NAME: str(curso_id),
        }
        if post_yes:
            data['post'] = 'yes'
            data['nota'] = nota
        return self.client.post(reverse('admin:core_curso_changelist'), data)

    def test_admin_publicar_flag_off_no_escribe(self):
        from core.models import Curso, CursoVersion

        curso = Curso.objects.create(nombre='Admin off', descripcion='d')
        with override_settings(EKI_CURSO_VERSIONES=False):
            resp = self._post_action(curso.id, post_yes=True, nota='x')
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(CursoVersion.objects.filter(curso=curso).count(), 0)

    @override_settings(EKI_CURSO_VERSIONES=True)
    def test_admin_publicar_confirm_luego_congela_sin_mover(self):
        from core.models import Curso, CursoVersion, Estudiante, Modulo, ProgresoEstudiante

        curso = Curso.objects.create(nombre='Admin on', descripcion='d')
        Modulo.objects.create(
            curso=curso, numero=1, titulo='M1', descripcion='', contenido='hola',
        )
        est = Estudiante.objects.create(
            nombre='Admin cohorte', telefono='573009990111', cedula='CC990111', activo=True,
        )
        prog = ProgresoEstudiante.objects.create(estudiante=est, curso=curso)

        confirm = self._post_action(curso.id)
        self.assertEqual(confirm.status_code, 200)
        self.assertContains(confirm, 'Publicar versión')
        self.assertEqual(CursoVersion.objects.filter(curso=curso).count(), 0)

        done = self._post_action(curso.id, post_yes=True, nota='desde admin')
        self.assertEqual(done.status_code, 302)
        v = CursoVersion.objects.get(curso=curso)
        self.assertEqual(v.numero, 1)
        self.assertEqual(v.nota, 'desde admin')
        curso.refresh_from_db()
        self.assertEqual(curso.version_publicada_id, v.id)
        prog.refresh_from_db()
        self.assertIsNone(prog.curso_version_id)


class LecturaEntregaVersionadaTests(TestCase):
    """Residual B4 commit 1: helpers leen snap; flag off = árbol vivo."""

    def test_congelar_incluye_modo_entrega(self):
        from core.models import Curso, Modulo

        curso = Curso.objects.create(nombre='Snap modo', descripcion='d')
        Modulo.objects.create(
            curso=curso,
            numero=1,
            titulo='M1',
            descripcion='',
            contenido='x',
            modo_entrega=Modulo.MODO_ENTREGA_PASOS,
        )
        snap = congelar_ensamblado(curso)
        self.assertEqual(snap['modulos'][0]['modo_entrega'], Modulo.MODO_ENTREGA_PASOS)

    def test_flag_off_ensamblado_de_progreso_none(self):
        from core.cursos.autoria.lectura_entrega import ensamblado_de_progreso
        from core.models import Curso, CursoVersion, Estudiante, ProgresoEstudiante

        curso = Curso.objects.create(nombre='Lect off', descripcion='d')
        v = CursoVersion.objects.create(
            curso=curso, numero=1, estado=CursoVersion.PUBLICADO, ensamblado={'schema': 1, 'modulos': []},
        )
        est = Estudiante.objects.create(
            nombre='Off', telefono='573009990201', cedula='CC990201', activo=True,
        )
        prog = ProgresoEstudiante.objects.create(estudiante=est, curso=curso, curso_version=v)
        with override_settings(EKI_CURSO_VERSIONES=False):
            self.assertIsNone(ensamblado_de_progreso(prog))

    @override_settings(EKI_CURSO_VERSIONES=True)
    def test_lectura_snap_no_sigue_edicion_viva(self):
        from core.cursos.autoria.lectura_entrega import (
            contenido_paso_para_entrega,
            ensamblado_de_progreso,
            titulo_modulo_para_entrega,
        )
        from core.models import (
            Curso,
            Estudiante,
            Modulo,
            PasoModulo,
            ProgresoEstudiante,
            SeccionModulo,
        )

        curso = Curso.objects.create(nombre='Lect on', descripcion='d')
        mod = Modulo.objects.create(
            curso=curso, numero=1, titulo='Titulo v1', descripcion='', contenido='c',
            modo_entrega=Modulo.MODO_ENTREGA_PASOS,
        )
        sec = SeccionModulo.objects.create(modulo=mod, orden=1, titulo='B1')
        paso = PasoModulo.objects.create(
            modulo=mod, seccion=sec, orden=1, tipo=PasoModulo.TIPO_CONTENIDO,
            contenido='texto v1', activo=True,
        )
        v1 = publicar(curso, nota='v1')
        self.assertIsNotNone(v1)
        est = Estudiante.objects.create(
            nombre='Anclado', telefono='573009990202', cedula='CC990202', activo=True,
        )
        prog = ProgresoEstudiante.objects.create(
            estudiante=est, curso=curso, curso_version=v1, modulo_actual=mod,
        )

        mod.titulo = 'Titulo editado vivo'
        mod.save(update_fields=['titulo'])
        paso.contenido = 'texto editado vivo'
        paso.save(update_fields=['contenido'])

        snap = ensamblado_de_progreso(prog)
        self.assertIsNotNone(snap)
        self.assertEqual(titulo_modulo_para_entrega(prog, mod), 'Titulo v1')
        self.assertEqual(contenido_paso_para_entrega(prog, paso), 'texto v1')
        self.assertNotEqual(mod.titulo, 'Titulo v1')
        self.assertNotEqual(paso.contenido, 'texto v1')

    @override_settings(EKI_CURSO_VERSIONES=True)
    def test_module_steps_legacy_lee_snap_no_vivo(self):
        from core.curso.module_steps import modulo_usa_pasos, texto_legacy_whatsapp
        from core.models import Curso, Estudiante, Modulo, ProgresoEstudiante

        curso = Curso.objects.create(nombre='Legacy snap', descripcion='d')
        mod = Modulo.objects.create(
            curso=curso,
            numero=1,
            titulo='M1',
            descripcion='',
            contenido='contenido v1',
            modo_entrega=Modulo.MODO_ENTREGA_LEGACY,
            publicado_wa=True,
        )
        v1 = publicar(curso, nota='v1')
        est = Estudiante.objects.create(
            nombre='Leg', telefono='573009990203', cedula='CC990203', activo=True,
        )
        prog = ProgresoEstudiante.objects.create(
            estudiante=est, curso=curso, curso_version=v1, modulo_actual=mod,
        )
        mod.contenido = 'contenido editado vivo'
        mod.save(update_fields=['contenido'])
        self.assertFalse(modulo_usa_pasos(mod, progreso=prog))
        self.assertEqual(texto_legacy_whatsapp(mod, progreso=prog), 'contenido v1')
        self.assertEqual(texto_legacy_whatsapp(mod), 'contenido editado vivo')

    @override_settings(EKI_CURSO_VERSIONES=True)
    def test_siguiente_modulo_respeta_snap_no_modulo_nuevo_vivo(self):
        from core.curso.modulo_publicacion import siguiente_modulo_publicado_wa
        from core.models import Curso, Estudiante, Modulo, ProgresoEstudiante

        curso = Curso.objects.create(nombre='Avance snap', descripcion='d')
        m1 = Modulo.objects.create(
            curso=curso, numero=1, titulo='M1', descripcion='', contenido='a',
            publicado_wa=True,
        )
        m2 = Modulo.objects.create(
            curso=curso, numero=2, titulo='M2', descripcion='', contenido='b',
            publicado_wa=True,
        )
        v1 = publicar(curso, nota='v1-dos')
        # Autor agrega M3 solo en vivo tras publicar.
        m3 = Modulo.objects.create(
            curso=curso, numero=3, titulo='M3 nuevo vivo', descripcion='', contenido='c',
            publicado_wa=True,
        )
        est = Estudiante.objects.create(
            nombre='Av', telefono='573009990204', cedula='CC990204', activo=True,
        )
        prog = ProgresoEstudiante.objects.create(
            estudiante=est, curso=curso, curso_version=v1, modulo_actual=m2,
        )
        # Vivo vería M3; cohorte v1 no.
        self.assertEqual(siguiente_modulo_publicado_wa(curso, m2), m3)
        self.assertIsNone(siguiente_modulo_publicado_wa(curso, m2, progreso=prog))
        self.assertEqual(
            siguiente_modulo_publicado_wa(curso, m1, progreso=prog),
            m2,
        )
