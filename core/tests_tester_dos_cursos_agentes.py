"""
Tester local: cliente Pruebas, 2 cursos, mismo estudiante.
- Deja A a la mitad, avanza B, vuelve a A.
- Completa A sin tocar el avance de B.
- Con agentes (Darío): el foco del curso activo no salta al otro.
"""
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from core.flujo_whatsapp_b2b import armar_menu_seleccion_cursos, tiene_varios_cursos_activos
from core.helpers_examenes import contexto_temporal_tras_cerrar_agente
from core.models import (
    Cliente,
    Curso,
    Estudiante,
    Modulo,
    ModuloCompletado,
    ProgresoEstudiante,
)
from core.response_templates import get_response_for_intent
from core.selector_curso import continuar_curso_seleccionado


class TesterLocalDosCursosAgentesTests(TestCase):
    def setUp(self):
        self.org = Cliente.objects.create(
            nombre='Pruebas',
            contacto_principal='Coord',
            email='pruebas-tester@eki.test',
            telefono='573009990099',
            activo=True,
        )
        self.curso_a = Curso.objects.create(
            nombre='Curso A — Fundamentos',
            cliente=self.org,
            activo=True,
            orden=1,
            emoji='📗',
            dias_espera_entre_modulos=0,
            usar_agentes_ia=True,
        )
        self.curso_b = Curso.objects.create(
            nombre='Curso B — Avanzado',
            cliente=self.org,
            activo=True,
            orden=2,
            emoji='📘',
            dias_espera_entre_modulos=0,
            usar_agentes_ia=True,
        )
        self.mods_a = [
            Modulo.objects.create(
                curso=self.curso_a,
                numero=n,
                titulo=f'A-M{n}',
                contenido=f'CONTENIDO_A_{n}',
            )
            for n in range(1, 4)
        ]
        self.mods_b = [
            Modulo.objects.create(
                curso=self.curso_b,
                numero=n,
                titulo=f'B-M{n}',
                contenido=f'CONTENIDO_B_{n}',
            )
            for n in range(1, 4)
        ]
        self.est = Estudiante.objects.create(
            cedula='880077006',
            nombre='Ana Tester',
            telefono='573008800770',
            cliente=self.org,
            activo=True,
            acepto_terminos=True,
            estado_chat='ACTIVO',
            estado_onboarding='completado',
        )
        self.prog_a = ProgresoEstudiante.objects.create(
            estudiante=self.est,
            curso=self.curso_a,
            modulo_actual=self.mods_a[0],
            completado=False,
            fecha_inicio=timezone.now(),
        )
        self.prog_b = ProgresoEstudiante.objects.create(
            estudiante=self.est,
            curso=self.curso_b,
            modulo_actual=self.mods_b[0],
            completado=False,
            fecha_inicio=timezone.now(),
        )

    def _listo(self, trigger='listo'):
        return get_response_for_intent(
            'continuar_leccion',
            self.est.nombre,
            estudiante_id=self.est.id,
            mensaje_original=trigger,
        )

    def test_menu_luego_mitad_a_avanza_b_vuelve_a(self):
        self.assertTrue(tiene_varios_cursos_activos(self.est))

        menu = self._listo()
        self.assertIn('varios cursos', menu.lower())
        self.assertIn('Curso A', menu)
        self.assertIn('Curso B', menu)

        # Elige A (índice según orden fecha_inicio desc: B primero si más reciente)
        self.est.refresh_from_db()
        self.est.estado_onboarding = 'esperando_seleccion_curso'
        self.est.contexto_temporal = {'tipo': 'seleccion_curso'}
        self.est.save()
        progresos = list(
            ProgresoEstudiante.objects.filter(
                estudiante=self.est, completado=False, curso__activo=True
            ).order_by('-fecha_inicio')
        )
        idx_a = next(i for i, p in enumerate(progresos, 1) if p.curso_id == self.curso_a.pk)
        r_a = continuar_curso_seleccionado(self.est.id, idx_a, str(idx_a))
        self.assertIn('Curso A', r_a)
        self.est.refresh_from_db()
        self.assertEqual(self.est.contexto_temporal.get('curso_activo_id'), self.curso_a.pk)

        # Avanza A: cierra M1 → queda en M2 (a la mitad)
        ModuloCompletado.objects.get_or_create(progreso=self.prog_a, modulo=self.mods_a[0])
        self.prog_a.modulo_actual = self.mods_a[1]
        self.prog_a.save()
        self.assertFalse(self.prog_a.completado)
        self.assertEqual(self.prog_a.modulo_actual_id, self.mods_a[1].id)

        # Sin foco: listo vuelve a pedir menú (no daña B)
        self.est.contexto_temporal = {'tipo': 'seleccion_curso'}
        self.est.estado_onboarding = 'esperando_seleccion_curso'
        self.est.save()
        menu2 = armar_menu_seleccion_cursos(self.est)
        self.assertIn('Curso A', menu2)
        self.assertIn('Curso B', menu2)

        idx_b = next(i for i, p in enumerate(
            ProgresoEstudiante.objects.filter(
                estudiante=self.est, completado=False, curso__activo=True
            ).order_by('-fecha_inicio'),
            1,
        ) if p.curso_id == self.curso_b.pk)
        r_b = continuar_curso_seleccionado(self.est.id, idx_b, str(idx_b))
        self.assertIn('Curso B', r_b)
        self.est.refresh_from_db()
        self.assertEqual(self.est.contexto_temporal.get('curso_activo_id'), self.curso_b.pk)

        # Avanza B un módulo
        ModuloCompletado.objects.get_or_create(progreso=self.prog_b, modulo=self.mods_b[0])
        self.prog_b.modulo_actual = self.mods_b[1]
        self.prog_b.save()

        # A sigue a la mitad; B también a la mitad — independientes
        self.prog_a.refresh_from_db()
        self.prog_b.refresh_from_db()
        self.assertEqual(self.prog_a.modulo_actual_id, self.mods_a[1].id)
        self.assertEqual(self.prog_b.modulo_actual_id, self.mods_b[1].id)
        self.assertFalse(self.prog_a.completado)
        self.assertFalse(self.prog_b.completado)

        # Completa A sin tocar B
        for m in self.mods_a:
            ModuloCompletado.objects.get_or_create(progreso=self.prog_a, modulo=m)
        self.prog_a.modulo_actual = self.mods_a[2]
        self.prog_a.completado = True
        self.prog_a.save()

        self.prog_b.refresh_from_db()
        self.assertFalse(self.prog_b.completado)
        self.assertEqual(self.prog_b.modulo_actual_id, self.mods_b[1].id)

        # Con A completo, ya no hay "varios" → un solo activo (B)
        self.assertFalse(tiene_varios_cursos_activos(self.est))
        resp = self._listo()
        self.assertNotIn('varios cursos', resp.lower())
        self.assertIn('CONTENIDO_B', resp)

    def test_agente_dario_respeta_curso_activo_con_dos_progresos(self):
        """Tras cerrar agente, el contexto conserva curso_activo_id de A, no salta a B."""
        self.est.contexto_temporal = {
            'tipo': 'asistente_dario',
            'progreso_id': self.prog_a.id,
            'curso_activo_id': self.curso_a.id,
            'preguntas_hechas': 1,
        }
        self.est.estado_onboarding = 'esperando_respuesta_asistente'
        self.est.save()

        ctx = contexto_temporal_tras_cerrar_agente(self.prog_a, self.est.contexto_temporal)
        self.assertEqual(ctx.get('curso_activo_id'), self.curso_a.id)

        # listo con foco A no entrega contenido de B
        self.est.contexto_temporal = {
            'curso_activo_id': self.curso_a.id,
            'post_reto_entregar_modulo_id': self.mods_a[1].id,
        }
        self.est.estado_onboarding = 'completado'
        self.est.save()
        self.prog_a.modulo_actual = self.mods_a[1]
        self.prog_a.save()
        ModuloCompletado.objects.get_or_create(progreso=self.prog_a, modulo=self.mods_a[0])

        resp = self._listo()
        self.assertIn('CONTENIDO_A_2', resp)
        self.assertNotIn('CONTENIDO_B_', resp)

    @patch('core.tutor_ia_modulo.generar_reto_facilitador', return_value='Reto test multi')
    @patch('core.tutor_ia_modulo.cargar_modulos_reto')
    def test_presentacion_agentes_por_curso_no_mezcla(self, mock_cargar, _mock_reto):
        mock_cargar.return_value = [self.mods_a[0]]
        from core.response_templates import partes_presentacion_agentes_curso

        partes_a = partes_presentacion_agentes_curso(self.est, self.curso_a)
        # Puede ser lista vacía si no hay config de agentes, pero no debe hablar de Curso B
        texto = ' '.join(partes_a) if partes_a else ''
        self.assertNotIn('Curso B', texto)
        self.assertNotIn('CONTENIDO_B', texto)
