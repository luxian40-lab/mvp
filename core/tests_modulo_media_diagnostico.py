"""Diagnóstico explícito de media WA por paso en módulo."""
from django.test import TestCase

from core.modulo_publicacion import (
    detalle_problema_media_paso,
    evaluar_checklist_publicacion_detalle,
    listar_problemas_media_modulo,
)
from core.models import Curso, Modulo, PasoModulo, SeccionModulo


class ModuloMediaDiagnosticoTests(TestCase):
    def setUp(self):
        self.curso = Curso.objects.create(
            nombre='Diag media',
            descripcion='d',
            dias_espera_entre_modulos=0,
        )
        self.mod = Modulo.objects.create(
            curso=self.curso,
            numero=8,
            titulo='Finanzas',
            descripcion='d',
            contenido='ok',
            duracion_dias=7,
        )
        self.sec = SeccionModulo.objects.create(
            modulo=self.mod, orden=1, titulo='Bloque M8', activa=True
        )
        self.paso_ok = PasoModulo.objects.create(
            modulo=self.mod,
            seccion=self.sec,
            orden=1,
            titulo='Intro OK',
            contenido='hola',
            media_url='https://eki-produccion.s3.us-east-2.amazonaws.com/ok.mp4',
            media_wa_apto=True,
            activo=True,
        )
        self.paso_malo = PasoModulo.objects.create(
            modulo=self.mod,
            seccion=self.sec,
            orden=2,
            titulo='Video roto',
            contenido='',
            media_url='https://eki-produccion.s3.us-east-2.amazonaws.com/roto.mp4',
            media_wa_apto=False,
            activo=True,
        )

    def test_listar_solo_pasos_con_problema(self):
        probs = listar_problemas_media_modulo(self.mod)
        self.assertEqual(len(probs), 1)
        self.assertEqual(probs[0]['orden'], 2)
        self.assertIn('Video roto', probs[0]['titulo'])
        self.assertIn('Materiales', probs[0]['accion'])

    def test_detalle_incluye_motivo(self):
        prob = detalle_problema_media_paso(self.paso_malo)
        self.assertIsNotNone(prob)
        self.assertEqual(prob['codigo'], 'fail')
        self.assertIn('No apto', prob['detalle'])

    def test_checklist_nombra_paso_explicito(self):
        chk = evaluar_checklist_publicacion_detalle(self.mod)
        self.assertFalse(chk.ok)
        joined = ' '.join(chk.errores)
        self.assertIn('#2', joined)
        self.assertIn('Video roto', joined)
        self.assertIn('Materiales', joined)
