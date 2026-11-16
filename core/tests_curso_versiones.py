"""Bloque 4 — versiones de curso. Flag apagado: sin efecto en entrega."""
from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings

from core.cursos.autoria.contrato import (
    COHORTE_FIJA_A_VERSION_DE_INSCRIPCION,
    CONTINUEMOS_ENTREGA_UN_BLOQUE,
    PUBLICAR_CREA_VERSION_INMUTABLE,
)
from core.cursos.autoria.ensamblado import congelar_ensamblado
from core.cursos.autoria.servicio import publicar, version_de_progreso, versiones_activas


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
