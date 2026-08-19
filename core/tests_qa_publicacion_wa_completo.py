"""
QA completo publicación WA — sin envíos Twilio reales.

Teléfono canónico pruebas: 573026480629 (3026480629).
Pruebas puntuales: gate, %, retos, agentes, cert cierre, campaña.
"""
from django.test import TestCase

from core.helpers_examenes import evaluar_checkpoint_reto_ia
from core.models import (
    Campana,
    Cliente,
    Curso,
    Estudiante,
    Modulo,
    ModuloCompletado,
    PasoModulo,
    Plantilla,
    ProgresoEstudiante,
    SeccionModulo,
)
from core.modulo_publicacion import (
    curso_listo_para_campana_wa,
    mensaje_bloqueo_sin_siguiente_publicado,
    numeros_cierre_curso_publicados,
    publicar_modulo_wa,
    siguiente_modulo_publicado_wa,
    total_modulos_publicados_wa,
)
from core.response_templates import get_response_for_intent
from core.services import ejecutar_campana_servicio

QA_PHONE = '573026480629'
QA_CEDULA = 'QA3026480629'


class QAPublicacionWAPhoneSmokeTests(TestCase):
    """Flujo puntual con el teléfono de pruebas ops — cero envíos WA."""

    def setUp(self):
        self.cliente = Cliente.objects.create(nombre='QA Pub WA', activo=True)
        self.curso = Curso.objects.create(
            nombre='QA Smoke Publicación',
            cliente=self.cliente,
            activo=True,
            usar_agentes_ia=True,
            dias_espera_entre_modulos=0,
        )
        self.est, _ = Estudiante.objects.update_or_create(
            telefono=QA_PHONE,
            defaults={
                'cedula': QA_CEDULA,
                'nombre': 'Tester QA Publicación',
                'cliente': self.cliente,
                'activo': True,
                'acepto_terminos': True,
                'estado_chat': 'ACTIVO',
                'estado_onboarding': 'completado',
            },
        )
        self.m1 = Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='M1 QA',
            descripcion='d',
            contenido='Contenido M1 smoke',
            publicado_wa=True,
        )
        self.m2 = Modulo.objects.create(
            curso=self.curso,
            numero=2,
            titulo='M2 borrador QA',
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
            contenido='Micro M2',
            activo=True,
        )
        self.m3 = Modulo.objects.create(
            curso=self.curso,
            numero=3,
            titulo='M3 cierre QA',
            descripcion='d',
            contenido='Contenido M3',
            publicado_wa=True,
        )
        self.prog = ProgresoEstudiante.objects.create(
            estudiante=self.est,
            curso=self.curso,
            modulo_actual=self.m1,
        )

    def test_01_porcentaje_solo_modulos_publicados(self):
        ModuloCompletado.objects.create(progreso=self.prog, modulo=self.m1)
        self.assertEqual(total_modulos_publicados_wa(self.curso), 2)
        self.assertEqual(self.prog.porcentaje_avance(), 50)

    def test_02_porcentaje_coherente_para_agentes_en_chat(self):
        """Misma fórmula que AgenteBase.obtener_contexto_estudiante (Progreso %)."""
        ModuloCompletado.objects.create(progreso=self.prog, modulo=self.m1)
        pct = self.prog.porcentaje_avance()
        self.assertEqual(pct, 50)
        self.assertEqual(self.est.telefono, QA_PHONE)
        self.assertEqual(self.prog.modulo_actual.titulo, 'M1 QA')

    def test_03_listo_bloqueado_m2_borrador_sin_media(self):
        ModuloCompletado.objects.create(progreso=self.prog, modulo=self.m1)
        self.prog.modulo_actual = self.m1
        self.prog.save(update_fields=['modulo_actual'])
        resp = get_response_for_intent(
            'continuar_leccion',
            self.est.nombre,
            estudiante_id=self.est.id,
            mensaje_original='listo',
        )
        low = resp.lower()
        self.assertIn('preparando', low)
        self.assertNotIn('63019', resp)
        self.assertNotIn('63021', resp)
        self.prog.refresh_from_db()
        self.assertEqual(self.prog.modulo_actual_id, self.m1.id)

    def test_04_checkpoint_m1_no_dispara_reto_ultimo_con_borrador_intermedio(self):
        total = total_modulos_publicados_wa(self.curso)
        d = evaluar_checkpoint_reto_ia(self.m1, total, True)
        self.assertFalse(d.es_reto)

    def test_05_publicar_m2_desbloquea_avance_puntual(self):
        ok, errs = publicar_modulo_wa(self.m2)
        self.assertTrue(ok, errs)
        ModuloCompletado.objects.create(progreso=self.prog, modulo=self.m1)
        self.prog.modulo_actual = self.m1
        self.prog.save(update_fields=['modulo_actual'])
        blk = mensaje_bloqueo_sin_siguiente_publicado(self.est, self.prog, self.m1)
        self.assertIsNone(blk)
        sig = siguiente_modulo_publicado_wa(self.curso, self.m1)
        self.assertEqual(sig.id, self.m2.id)

    def test_06_cert_penultimo_ultimo_solo_publicados(self):
        pen, ult = numeros_cierre_curso_publicados(self.curso)
        self.assertEqual(ult, 3)
        self.assertEqual(pen, 1)

    def test_07_campana_bloqueada_si_m1_despublicado(self):
        self.m1.publicado_wa = False
        self.m1.save(update_fields=['publicado_wa'])
        ok, msg = curso_listo_para_campana_wa(self.curso)
        self.assertFalse(ok)
        self.assertIn('Módulo 1', msg)

    def test_08_campana_servicio_no_envia_sin_m1_publicado(self):
        self.m1.publicado_wa = False
        self.m1.save(update_fields=['publicado_wa'])
        plantilla = Plantilla.objects.create(
            nombre_interno='qa_pub',
            cuerpo_mensaje='Hola {nombre}',
        )
        camp = Campana.objects.create(
            nombre='QA pub block',
            cliente=self.cliente,
            plantilla=plantilla,
            es_campana_curso=True,
            curso_destino=self.curso,
            template_twilio_id='HXtest123456789012345678901234',
        )
        camp.destinatarios.add(self.est)
        with self.assertRaises(ValueError):
            ejecutar_campana_servicio(camp)
