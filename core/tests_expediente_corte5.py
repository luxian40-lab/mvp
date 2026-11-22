"""
Corte 5 — nota vacía en emisiones nuevas (EKI_DIPLOMA_NOTA_VACIA_SIN_PREGUNTAS).

docs/PLAN_EXPEDIENTE_APRENDIZAJE_EKI.md. PDF ya emitidos no se tocan.
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from core.certificados.certificado_service import calcular_calificacion_curso, crear_certificado_automatico
from core.conversacion.progreso_completado import marcar_progreso_curso_completado
from core.models import Cliente, Curso, Estudiante, Modulo, ProgresoEstudiante
from core.models_certificados import Certificado


def _curso_sin_preguntas(tag: str):
    cli = Cliente.objects.create(nombre=f'C5 {tag}', activo=True)
    curso = Curso.objects.create(nombre=f'SinQA {tag}', cliente=cli, activo=True)
    mod = Modulo.objects.create(
        curso=curso, numero=1, titulo='M1', descripcion='d', contenido='c', publicado_wa=True,
    )
    est = Estudiante.objects.create(
        cedula=f'EXP-C5-{tag}',
        nombre='Luis',
        telefono=f'57300999{abs(hash(tag)) % 10000:04d}',
        cliente=cli,
        activo=True,
    )
    progreso = ProgresoEstudiante.objects.create(
        estudiante=est, curso=curso, modulo_actual=mod, completado=False,
    )
    return cli, curso, est, progreso


class ExpedienteNotaFlagOffTests(TestCase):
    def test_sin_preguntas_sigue_100(self):
        _cli, curso, est, _prog = _curso_sin_preguntas('Off')
        self.assertEqual(calcular_calificacion_curso(est, curso), 100.0)


@override_settings(EKI_DIPLOMA_NOTA_VACIA_SIN_PREGUNTAS=True, EKI_CERTIFICADO_ASYNC=False)
class ExpedienteNotaFlagOnTests(TestCase):
    def test_sin_preguntas_calculo_vacio(self):
        _cli, curso, est, _prog = _curso_sin_preguntas('OnCalc')
        self.assertIsNone(calcular_calificacion_curso(est, curso))

    @patch('core.certificados.certificado_service.generar_y_guardar_certificado', return_value=True)
    def test_certificado_nuevo_sin_100(self, _gen):
        _cli, curso, est, progreso = _curso_sin_preguntas('OnCert')
        marcar_progreso_curso_completado(progreso)
        # Evitar double-create via signal path already done; fetch or create explicit.
        cert = Certificado.objects.filter(estudiante=est, curso=curso).first()
        if cert is None:
            cert = crear_certificado_automatico(est, curso, encolar=False)
        self.assertIsNotNone(cert)
        self.assertIsNone(cert.calificacion_final)

    def test_pdf_viejo_con_100_no_se_reescribe(self):
        _cli, curso, est, progreso = _curso_sin_preguntas('Old')
        marcar_progreso_curso_completado(progreso)
        # Simula emisión histórica (nota 100) sin pasar por el helper de calificación.
        Certificado.objects.filter(estudiante=est, curso=curso).delete()
        viejo = Certificado.objects.create(
            estudiante=est,
            curso=curso,
            calificacion_final=Decimal('100.00'),
            fecha_inicio=timezone.now().date(),
            fecha_completado=timezone.now().date(),
        )
        # Recalcular no muta filas existentes.
        self.assertIsNone(calcular_calificacion_curso(est, curso))
        viejo.refresh_from_db()
        self.assertEqual(viejo.calificacion_final, Decimal('100.00'))
