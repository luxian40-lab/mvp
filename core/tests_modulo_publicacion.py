"""Publicación WA: gate runtime, porcentajes, retos, campaña."""
from django.test import TestCase, override_settings

from core.helpers_examenes import evaluar_checkpoint_reto_ia
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
from core.modulo_publicacion import (
    curso_listo_para_campana_wa,
    mensaje_bloqueo_sin_siguiente_publicado,
    publicar_modulo_wa,
    total_modulos_publicados_wa,
)
from core.response_templates import get_response_for_intent
from core.services import ejecutar_campana_servicio


class ModuloPublicacionHelpersTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(nombre='QA Pub', activo=True)
        self.curso = Curso.objects.create(
            nombre='Curso QA Pub',
            cliente=self.cliente,
            activo=True,
        )
        self.m1 = Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='Uno',
            descripcion='d',
            contenido='Texto m1',
            publicado_wa=True,
        )
        self.m2 = Modulo.objects.create(
            curso=self.curso,
            numero=2,
            titulo='Dos',
            descripcion='d',
            contenido='',
            publicado_wa=False,
        )
        sec = SeccionModulo.objects.create(modulo=self.m2, orden=1, titulo='S1')
        PasoModulo.objects.create(
            modulo=self.m2,
            seccion=sec,
            orden=1,
            titulo='P1',
            contenido='Micro',
            activo=True,
        )

    def test_total_solo_publicados(self):
        self.assertEqual(total_modulos_publicados_wa(self.curso), 1)

    def test_publicar_modulo_con_contenido(self):
        ok, errs = publicar_modulo_wa(self.m2)
        self.assertTrue(ok, errs)
        self.m2.refresh_from_db()
        self.assertTrue(self.m2.publicado_wa)

    def test_publicar_bloquea_media_no_apto(self):
        self.m2.pasos.update(
            media_url='https://cdn.example.com/clip.mp4',
            media_wa_apto=False,
        )
        ok, errs = publicar_modulo_wa(self.m2)
        self.assertFalse(ok)
        self.assertTrue(any('apto' in e.lower() for e in errs))

    @override_settings(PUBLICAR_MODULO_REQUIRE_MEDIA_QA=True, PUBLICAR_MODULO_HEAD_QA=False)
    def test_publicar_bloquea_video_sin_qa(self):
        self.m2.pasos.update(
            media_url='https://cdn.example.com/clip.mp4',
            media_wa_apto=None,
        )
        ok, errs = publicar_modulo_wa(self.m2)
        self.assertFalse(ok)
        self.assertTrue(any('QA media' in e for e in errs))

    def test_campana_bloqueada_si_m1_no_publicado(self):
        self.m1.publicado_wa = False
        self.m1.save(update_fields=['publicado_wa'])
        ok, msg = curso_listo_para_campana_wa(self.curso)
        self.assertFalse(ok)
        self.assertIn('Módulo 1', msg)

    def test_checkpoint_usa_total_publicados(self):
        for i in range(3, 7):
            Modulo.objects.create(
                curso=self.curso,
                numero=i,
                titulo=f'M{i}',
                descripcion='d',
                publicado_wa=False,
            )
        total = total_modulos_publicados_wa(self.curso)
        self.assertEqual(total, 1)
        d = evaluar_checkpoint_reto_ia(self.m1, total, True)
        self.assertFalse(d.es_reto)


class ModuloPublicacionGateRuntimeTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(nombre='Gate WA', activo=True)
        self.curso = Curso.objects.create(
            nombre='Gate',
            cliente=self.cliente,
            activo=True,
            usar_agentes_ia=False,
        )
        self.est = Estudiante.objects.create(
            cedula='990011001',
            nombre='Est Gate',
            telefono='573001112233',
            cliente=self.cliente,
            activo=True,
        )
        self.m1 = Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='M1',
            descripcion='d',
            contenido='Contenido m1',
            publicado_wa=True,
        )
        self.m2 = Modulo.objects.create(
            curso=self.curso,
            numero=2,
            titulo='M2 borrador',
            descripcion='d',
            contenido='',
            publicado_wa=False,
        )
        sec = SeccionModulo.objects.create(modulo=self.m2, orden=1, titulo='S')
        PasoModulo.objects.create(
            modulo=self.m2,
            seccion=sec,
            orden=1,
            titulo='P',
            contenido='x',
            activo=True,
        )
        self.prog = ProgresoEstudiante.objects.create(
            estudiante=self.est,
            curso=self.curso,
            modulo_actual=self.m1,
        )

    def test_mensaje_bloqueo_si_m2_borrador(self):
        ModuloCompletado.objects.create(progreso=self.prog, modulo=self.m1)
        msg = mensaje_bloqueo_sin_siguiente_publicado(self.est, self.prog, self.m1)
        self.assertIsNotNone(msg)
        self.assertIn('preparando', msg.lower())

    def test_porcentaje_solo_cuenta_publicados(self):
        ModuloCompletado.objects.create(progreso=self.prog, modulo=self.m1)
        self.assertEqual(self.prog.porcentaje_avance(), 100)

    def test_no_salta_m3_si_m2_borrador(self):
        """Regresión: no avanzar a M3 publicado mientras M2 sigue en borrador."""
        from core.modulo_publicacion import siguiente_modulo_publicado_wa

        self.assertIsNone(siguiente_modulo_publicado_wa(self.curso, self.m1))

    def test_listo_no_envia_si_siguiente_borrador(self):
        ModuloCompletado.objects.create(progreso=self.prog, modulo=self.m1)
        resp = get_response_for_intent(
            'continuar_leccion',
            self.est.nombre,
            estudiante_id=self.est.id,
            mensaje_original='listo',
        )
        self.assertIn('preparando', resp.lower())
        self.prog.refresh_from_db()
        self.assertEqual(self.prog.modulo_actual_id, self.m1.id)


class ModuloPublicacionCampañaTests(TestCase):
    def setUp(self):
        from core.models import Campana, Plantilla

        self.cliente = Cliente.objects.create(nombre='Camp', activo=True)
        self.plantilla = Plantilla.objects.create(
            nombre_interno='pub_qa',
            cuerpo_mensaje='Hola {nombre}',
        )
        self.curso = Curso.objects.create(
            nombre='Camp Curso',
            cliente=self.cliente,
            activo=True,
        )
        Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='M1',
            descripcion='d',
            contenido='',
            publicado_wa=False,
        )
        self.est = Estudiante.objects.create(
            cedula='99001100299',
            nombre='E Camp',
            telefono='57300999887799',
            cliente=self.cliente,
            activo=True,
        )
        self.campana = Campana.objects.create(
            nombre='Test camp pub',
            cliente=self.cliente,
            plantilla=self.plantilla,
            es_campana_curso=True,
            curso_destino=self.curso,
            template_twilio_id='HXtest123456789012345678901234',
        )
        self.campana.destinatarios.add(self.est)

    def test_ejecutar_campana_falla_sin_m1_publicado(self):
        with self.assertRaises(ValueError) as ctx:
            ejecutar_campana_servicio(self.campana)
        self.assertIn('Publicá', str(ctx.exception))


class ModoClasesExentoTests(TestCase):
    def test_modo_clases_no_usa_gate(self):
        cliente = Cliente.objects.create(nombre='Aprende Co', activo=True)
        curso = Curso.objects.create(
            nombre='Capital Humano QA',
            cliente=cliente,
            activo=True,
            modo_aula=Curso.MODO_AULA_CLASES,
        )
        Modulo.objects.create(
            curso=curso,
            numero=1,
            titulo='Clase 1',
            descripcion='d',
            publicado_wa=False,
        )
        ok, _ = curso_listo_para_campana_wa(curso)
        self.assertTrue(ok)
