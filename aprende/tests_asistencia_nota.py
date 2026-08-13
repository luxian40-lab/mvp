# -*- coding: utf-8 -*-
"""Asistencia agregada 1–5 (−0,2 por falta) para ranking por calificación."""
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from aprende.calificacion_aula_service import (
    DETALLE_ASISTENCIA_CURSO,
    guardar_asistencia_sesion,
    nota_asistencia_desde_faltas,
    recalcular_nota_asistencia_estudiante,
    resumen_asistencia_estudiante,
)
from aprende.models import AsistenciaAula
from core.gamificacion import EvaluacionNotaGamificacion
from core.models import Cliente, Curso, Estudiante, ProgresoEstudiante


class NotaAsistenciaAgregadaTests(TestCase):
    def test_formula_paso_02(self):
        self.assertEqual(nota_asistencia_desde_faltas(0), Decimal('5.0'))
        self.assertEqual(nota_asistencia_desde_faltas(1), Decimal('4.8'))
        self.assertEqual(nota_asistencia_desde_faltas(5), Decimal('4.0'))
        self.assertEqual(nota_asistencia_desde_faltas(20), Decimal('1.0'))
        self.assertEqual(nota_asistencia_desde_faltas(100), Decimal('1.0'))

    def test_recalculo_una_nota_por_curso(self):
        org = Cliente.objects.create(
            nombre='Org Notas',
            contacto_principal='A',
            email='n@t.com',
            telefono='573001110000',
            activo=True,
            fecha_fin_suscripcion='2099-12-31',
            modo_gamificacion='calificacion',
        )
        curso = Curso.objects.create(
            nombre='Clases Notas',
            descripcion='d',
            cliente=org,
            activo=True,
            modo_aula=Curso.MODO_AULA_CLASES,
        )
        from core.models import Modulo
        m1 = Modulo.objects.create(curso=curso, numero=1, titulo='C1', contenido='x')
        est = Estudiante.objects.create(
            cedula='100200300',
            nombre='Ana Asiste',
            telefono='573001110001',
            cliente=org,
            activo=True,
            acepto_terminos=True,
        )
        ProgresoEstudiante.objects.create(
            estudiante=est, curso=curso, modulo_actual=m1, completado=False,
        )

        d0 = date(2026, 8, 1)
        d1 = date(2026, 8, 2)
        d2 = date(2026, 8, 3)
        AsistenciaAula.objects.create(curso=curso, estudiante=est, fecha=d0, presente=True)
        AsistenciaAula.objects.create(curso=curso, estudiante=est, fecha=d1, presente=True)
        AsistenciaAula.objects.create(curso=curso, estudiante=est, fecha=d2, presente=False)

        nota = recalcular_nota_asistencia_estudiante(curso, est)
        self.assertEqual(nota, Decimal('4.8'))  # 1 falta
        qs = EvaluacionNotaGamificacion.objects.filter(
            estudiante=est, curso=curso, tipo='asistencia',
        )
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.get().detalle, DETALLE_ASISTENCIA_CURSO)
        self.assertEqual(qs.get().nota, Decimal('4.8'))

        resumen = resumen_asistencia_estudiante(curso, est.pk)
        self.assertEqual(resumen['faltas'], 1)
        self.assertEqual(resumen['nota'], Decimal('4.8'))

    def test_curso_clases_usa_notas_aunque_org_este_en_puntos(self):
        """Capital humano 10x: org Cenipalma en puntos, curso clases → ranking por nota."""
        from aprende.ranking_service import ranking_curso_profesor
        from core.gamificacion import TransaccionPuntos, PerfilGamificacion

        org = Cliente.objects.create(
            nombre='Org Mixto WA+Clases',
            contacto_principal='A',
            email='mix@t.com',
            telefono='573001110010',
            activo=True,
            fecha_fin_suscripcion='2099-12-31',
            modo_gamificacion='puntos',
            usar_gamificacion=True,
        )
        curso = Curso.objects.create(
            nombre='Capital humano test',
            descripcion='d',
            cliente=org,
            activo=True,
            modo_aula=Curso.MODO_AULA_CLASES,
        )
        from core.models import Modulo
        m1 = Modulo.objects.create(curso=curso, numero=1, titulo='C1', contenido='x')
        est = Estudiante.objects.create(
            cedula='100200301',
            nombre='Est Clases Mix',
            telefono='573001110011',
            cliente=org,
            activo=True,
            acepto_terminos=True,
        )
        ProgresoEstudiante.objects.create(
            estudiante=est, curso=curso, modulo_actual=m1, completado=False,
        )

        d0 = date(2026, 8, 10)
        asis = AsistenciaAula.objects.create(
            curso=curso, estudiante=est, fecha=d0, presente=True,
        )
        from aprende.calificacion_aula_service import _sync_asistencia_gamificacion
        _sync_asistencia_gamificacion(asis)
        # No debe sumar +1 punto (modo clases → nota)
        perfil = PerfilGamificacion.objects.filter(estudiante=est).first()
        if perfil:
            self.assertFalse(
                TransaccionPuntos.objects.filter(
                    perfil=perfil, razon__icontains='Asistencia 2026-08-10',
                ).exists()
            )
        nota = EvaluacionNotaGamificacion.objects.filter(
            estudiante=est, curso=curso, tipo='asistencia',
        )
        self.assertEqual(nota.count(), 1)
        self.assertEqual(nota.get().nota, Decimal('5.0'))

        rk = ranking_curso_profesor(org, curso)
        self.assertEqual(rk['modo'], 'calificacion')
        self.assertTrue(rk['filas'])
        self.assertEqual(rk['filas'][0]['estudiante_id'], est.pk)
