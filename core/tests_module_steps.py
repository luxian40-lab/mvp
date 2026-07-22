"""Tests: pasos internos por módulo (entrega progresiva)."""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.admin.sites import AdminSite
from django.test import TestCase, override_settings
from django.utils import timezone

from core.admin import PasoModuloInline

from core.models import (
    Cliente,
    Curso,
    Estudiante,
    Modulo,
    ModuloCompletado,
    PasoModulo,
    PreguntaModulo,
    ProgresoEstudiante,
    SeccionModulo,
)
from core.module_steps import (
    modulo_tiene_pasos_activos,
    modulo_usa_pasos,
    reset_progreso_pasos_modulo,
    entregar_paso_indice,
    entregar_bloque_secciones_desde_paso,
    procesar_respuesta_evaluacion_paso,
)
from core.response_templates import get_response_for_intent


def _seccion(mod, orden, titulo=''):
    return SeccionModulo.objects.create(modulo=mod, orden=orden, titulo=titulo)


class ModuleStepsModelTests(TestCase):
    def setUp(self):
        self.curso = Curso.objects.create(
            nombre='Curso pasos',
            descripcion='d',
            dias_espera_entre_modulos=0,
            usar_agentes_ia=False,
        )
        self.mod = Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='M1',
            descripcion='d',
            contenido='Contenido legacy del módulo entero',
            duracion_dias=7,
        )
        self.est = Estudiante.objects.create(
            cedula='10998877',
            nombre='Ana Pasos',
            telefono='573009990011',
        )
        self.prog = ProgresoEstudiante.objects.create(
            estudiante=self.est,
            curso=self.curso,
            modulo_actual=self.mod,
        )

    def test_sin_pasos_modulo_legacy(self):
        self.assertFalse(modulo_tiene_pasos_activos(self.mod))
        self.assertFalse(modulo_usa_pasos(self.mod))

    def test_modulo_usa_pasos_legacy_falso_aunque_haya_filas(self):
        s1 = _seccion(self.mod, 1)
        PasoModulo.objects.create(
            modulo=self.mod,
            seccion=s1,
            orden=1,
            titulo='x',
            tipo=PasoModulo.TIPO_CONTENIDO,
            contenido='y',
        )
        self.mod.modo_entrega = Modulo.MODO_ENTREGA_LEGACY
        self.mod.save(update_fields=['modo_entrega'])
        self.assertTrue(modulo_tiene_pasos_activos(self.mod))
        self.assertFalse(modulo_usa_pasos(self.mod))

    def test_modulo_usa_pasos_forzado_sin_filas(self):
        self.mod.modo_entrega = Modulo.MODO_ENTREGA_PASOS
        self.mod.save(update_fields=['modo_entrega'])
        self.assertTrue(modulo_usa_pasos(self.mod))
        self.assertFalse(modulo_tiene_pasos_activos(self.mod))

    def test_entregar_paso_contenido_avanza_indice(self):
        s1 = _seccion(self.mod, 1)
        PasoModulo.objects.create(
            modulo=self.mod,
            seccion=s1,
            orden=1,
            titulo='Paso uno',
            tipo=PasoModulo.TIPO_CONTENIDO,
            contenido='Solo este bloque',
        )
        reset_progreso_pasos_modulo(self.prog, save=True)
        self.assertEqual(self.prog.paso_actual_modulo, 1)
        msg = entregar_paso_indice(self.prog, self.mod, 1)
        self.prog.refresh_from_db()
        self.assertEqual(self.prog.paso_actual_modulo, 2)
        self.assertIn('Solo este bloque', msg)
        self.assertNotIn('Paso uno', msg)
        self.assertIn('[MULTI_MSG]', msg)

    def test_paso_con_media_incluye_texto_en_mismo_bloque_que_media(self):
        s1 = _seccion(self.mod, 1)
        PasoModulo.objects.filter(modulo=self.mod).delete()
        PasoModulo.objects.create(
            modulo=self.mod,
            seccion=s1,
            orden=1,
            titulo='Video intro',
            tipo=PasoModulo.TIPO_CONTENIDO,
            contenido='Mirá este material',
            media_url='https://example.com/video.mp4',
        )
        reset_progreso_pasos_modulo(self.prog, save=True)
        msg = entregar_paso_indice(self.prog, self.mod, 1)
        self.assertIn('Mirá este material', msg)
        self.assertIn('[MEDIA:https://example.com/video.mp4]', msg)
        self.assertNotIn('📹', msg)
        bloques = [p for p in msg.replace('[MULTI_MSG]', '', 1).split('[SEP]') if p.strip()]
        solos_adjuntos = [b for b in bloques if b.strip().startswith('[MEDIA:')]
        self.assertEqual(
            len(solos_adjuntos),
            0,
            'El adjunto no debe ir en un mensaje Twilio sin texto propio',
        )

    @patch('core.models_extras.ArchivoModulo.validar_url_publica', return_value=True)
    def test_bloque_idx1_inyecta_archivo_modulo_multimedia(self, _mock_val):
        """Regresión: modo pasos no debe olvidar la pestaña Multimedia del módulo."""
        from core.models_extras import ArchivoModulo

        s1 = _seccion(self.mod, 1)
        PasoModulo.objects.filter(modulo=self.mod).delete()
        PasoModulo.objects.create(
            modulo=self.mod,
            seccion=s1,
            orden=1,
            titulo='Texto',
            tipo=PasoModulo.TIPO_CONTENIDO,
            contenido='Solo texto del paso',
        )
        ArchivoModulo.objects.create(
            modulo=self.mod,
            tipo='video',
            titulo='Video módulo',
            url_externa='https://cdn.example.com/modulo1.mp4',
            activo=True,
        )
        reset_progreso_pasos_modulo(self.prog, save=True)
        msg = entregar_bloque_secciones_desde_paso(self.prog, self.mod, 1)
        self.assertIn('[MEDIA:https://cdn.example.com/modulo1.mp4]', msg)
        self.assertIn('Solo texto del paso', msg)
        media_bloque = [
            p for p in msg.replace('[MULTI_MSG]', '', 1).split('[SEP]')
            if '[MEDIA:https://cdn.example.com/modulo1.mp4]' in p
        ]
        self.assertEqual(len(media_bloque), 1)
        self.assertIn('Solo texto del paso', media_bloque[0])
        self.assertNotIn('Aquí tiene el material del módulo', media_bloque[0])
        self.assertEqual(msg.count('Solo texto del paso'), 1)

    def test_recordatorio_no_redetails_el_micro(self):
        from core.module_steps import mensaje_recordatorio_paso_actual

        s1 = _seccion(self.mod, 1)
        PasoModulo.objects.filter(modulo=self.mod).delete()
        PasoModulo.objects.create(
            modulo=self.mod,
            seccion=s1,
            orden=1,
            titulo='Micro',
            tipo=PasoModulo.TIPO_CONTENIDO,
            contenido='¿Combinar redes y sexualidad? Texto del micro.',
        )
        reset_progreso_pasos_modulo(self.prog, save=True)
        rem = mensaje_recordatorio_paso_actual(self.prog, self.mod)
        self.assertIsNotNone(rem)
        self.assertIn('listo', rem.lower())
        self.assertNotIn('Combinar redes', rem)

    def test_evaluacion_opciones_espera_respuesta(self):
        s1 = _seccion(self.mod, 1)
        PasoModulo.objects.create(
            modulo=self.mod,
            seccion=s1,
            orden=1,
            titulo='Quiz',
            tipo=PasoModulo.TIPO_EVAL_OPC,
            contenido='Elige bien',
            opciones_json={'A': 'Uno', 'B': 'Dos', 'correcta': 'B'},
        )
        reset_progreso_pasos_modulo(self.prog, save=True)
        entregar_paso_indice(self.prog, self.mod, 1)
        self.prog.refresh_from_db()
        self.assertTrue(self.prog.esperando_respuesta_evaluacion_paso)
        self.assertEqual(self.prog.paso_actual_modulo, 1)

        out = procesar_respuesta_evaluacion_paso(self.est, self.prog, 'a')
        self.assertIsNotNone(out)
        self.assertIn('incorrecta', out.lower())
        self.assertTrue(out.startswith('[MULTI_MSG]'))
        self.assertIn('listo', out.lower())
        self.assertIn('siguiente material', out.lower())

        out_hint = procesar_respuesta_evaluacion_paso(self.est, self.prog, 'listo')
        self.assertIsNotNone(out_hint)
        self.assertNotIn('incorrecta', out_hint.lower())
        self.prog.refresh_from_db()
        self.assertFalse(self.prog.esperando_respuesta_evaluacion_paso)
        self.assertGreater(self.prog.paso_actual_modulo, 1)

    def test_eval_correcta_feedback_y_cta_listo_en_un_solo_segmento(self):
        """Evita dos bubbles (reorden en WhatsApp): primero feedback, luego CTA *listo*."""
        s1 = _seccion(self.mod, 1)
        PasoModulo.objects.create(
            modulo=self.mod,
            seccion=s1,
            orden=1,
            titulo='Quiz',
            tipo=PasoModulo.TIPO_EVAL_OPC,
            contenido='Elige bien',
            opciones_json={'A': 'Uno', 'B': 'Dos', 'correcta': 'B'},
            feedback_correcto='✅ ¡Excelente! Respuesta correcta.',
        )
        PasoModulo.objects.create(
            modulo=self.mod,
            seccion=s1,
            orden=2,
            titulo='P2',
            tipo=PasoModulo.TIPO_CONTENIDO,
            contenido='Siguiente bloque',
        )
        reset_progreso_pasos_modulo(self.prog, save=True)
        entregar_paso_indice(self.prog, self.mod, 1)
        self.prog.refresh_from_db()
        out = procesar_respuesta_evaluacion_paso(self.est, self.prog, 'b')
        self.assertTrue(out.startswith('[MULTI_MSG]'))
        partes = [p for p in out.replace('[MULTI_MSG]', '', 1).split('[SEP]') if p.strip()]
        self.assertEqual(len(partes), 1, partes)
        blob = partes[0].lower()
        self.assertIn('excelente', blob)
        self.assertIn('listo', blob)
        self.assertLess(blob.index('excelente'), blob.index('listo'))

    @patch('core.tutor_ia_modulo.evaluar_reto_facilitador', return_value=(8, 'Muy bien aplicado el concepto.'))
    def test_eval_abierta_califica_con_facilitadora(self, _mock_eval):
        s1 = _seccion(self.mod, 1)
        PasoModulo.objects.create(
            modulo=self.mod,
            seccion=s1,
            orden=1,
            titulo='Abierta',
            tipo=PasoModulo.TIPO_EVAL_ABIERTA,
            contenido='¿Cómo aplicaría el ahorro en su hogar?',
        )
        PasoModulo.objects.create(
            modulo=self.mod,
            seccion=s1,
            orden=2,
            titulo='P2',
            tipo=PasoModulo.TIPO_CONTENIDO,
            contenido='Siguiente bloque',
        )
        reset_progreso_pasos_modulo(self.prog, save=True)
        entregar_paso_indice(self.prog, self.mod, 1)
        self.prog.refresh_from_db()
        self.assertTrue(self.prog.esperando_respuesta_evaluacion_paso)

        out = procesar_respuesta_evaluacion_paso(
            self.est, self.prog, 'Separaría gastos fijos y variables cada mes.',
        )
        self.assertIsNotNone(out)
        self.assertIn('Facilitadora', out)
        self.assertIn('Muy bien aplicado', out)
        self.prog.refresh_from_db()
        self.assertFalse(self.prog.esperando_respuesta_evaluacion_paso)
        self.assertEqual(self.prog.paso_actual_modulo, 2)
        _mock_eval.assert_called_once()

    def test_eval_incorrecta_feedback_y_cta_listo_en_un_solo_segmento(self):
        """Un bubble: feedback de error + CTA *listo* (misma UX que acierto)."""
        s1 = _seccion(self.mod, 1)
        PasoModulo.objects.create(
            modulo=self.mod,
            seccion=s1,
            orden=1,
            titulo='Quiz',
            tipo=PasoModulo.TIPO_EVAL_OPC,
            contenido='Elige bien',
            opciones_json={'A': 'Uno', 'B': 'Dos', 'correcta': 'B'},
            feedback_incorrecto='🔄 Casi. La buena era otra.',
        )
        PasoModulo.objects.create(
            modulo=self.mod,
            seccion=s1,
            orden=2,
            titulo='P2',
            tipo=PasoModulo.TIPO_CONTENIDO,
            contenido='Siguiente bloque',
        )
        reset_progreso_pasos_modulo(self.prog, save=True)
        entregar_paso_indice(self.prog, self.mod, 1)
        self.prog.refresh_from_db()
        out = procesar_respuesta_evaluacion_paso(self.est, self.prog, 'a')
        self.assertTrue(out.startswith('[MULTI_MSG]'))
        partes = [p for p in out.replace('[MULTI_MSG]', '', 1).split('[SEP]') if p.strip()]
        self.assertEqual(len(partes), 1, partes)
        blob = partes[0].lower()
        self.assertIn('casi', blob)
        self.assertIn('listo', blob)
        self.assertLess(blob.index('casi'), blob.index('listo'))

        out_listo = procesar_respuesta_evaluacion_paso(self.est, self.prog, 'listo')
        self.assertNotIn('seguimos con el curso', out_listo.lower())
        self.assertIn('siguiente bloque', out_listo.lower())

    def test_eval_letra_correcta_usa_campo_admin_si_no_hay_textos_de_opciones(self):
        """Si solo hay correcta en JSON / campo admin, igual se valida la letra."""
        from core.module_steps import _letra_correcta_eval_opciones

        s1 = _seccion(self.mod, 1)
        p = PasoModulo.objects.create(
            modulo=self.mod,
            seccion=s1,
            orden=1,
            titulo='Q',
            tipo=PasoModulo.TIPO_EVAL_OPC,
            contenido='?',
            respuesta_correcta='B',
            opciones_json={'correcta': 'B'},
        )
        self.assertEqual(_letra_correcta_eval_opciones(p), 'B')
        reset_progreso_pasos_modulo(self.prog, save=True)
        entregar_paso_indice(self.prog, self.mod, 1)
        self.prog.refresh_from_db()
        out = procesar_respuesta_evaluacion_paso(self.est, self.prog, 'b')
        self.assertIsNotNone(out)
        self.prog.refresh_from_db()
        self.assertFalse(self.prog.esperando_respuesta_evaluacion_paso)

    def test_contenido_con_opciones_en_campos_se_ve_y_bloquea_como_eval(self):
        """Tipo «Contenido» pero A/B + correcta: debe verse la pregunta opción múltiple (admin mal usado)."""
        s1 = _seccion(self.mod, 1)
        PasoModulo.objects.create(
            modulo=self.mod,
            seccion=s1,
            orden=1,
            titulo='Interno',
            tipo=PasoModulo.TIPO_CONTENIDO,
            contenido='¿Cuál es la correcta?',
            eval_opcion_a='Primera',
            eval_opcion_b='Segunda',
            respuesta_correcta='B',
        )
        reset_progreso_pasos_modulo(self.prog, save=True)
        msg = entregar_paso_indice(self.prog, self.mod, 1)
        self.assertIn('*A*)', msg)
        self.assertIn('*B*)', msg)
        self.assertIn('¿Cuál es la correcta?', msg)
        self.prog.refresh_from_db()
        self.assertTrue(self.prog.esperando_respuesta_evaluacion_paso)

    def test_evaluacion_opciones_campos_admin_sin_json(self):
        s1 = _seccion(self.mod, 1)
        p = PasoModulo.objects.create(
            modulo=self.mod,
            seccion=s1,
            orden=1,
            titulo='Quiz',
            tipo=PasoModulo.TIPO_EVAL_OPC,
            contenido='Elegí una',
            eval_opcion_a='Uno',
            eval_opcion_b='Dos',
            respuesta_correcta='B',
            opciones_json=None,
        )
        p.refresh_from_db()
        self.assertIsInstance(p.opciones_json, dict)
        self.assertEqual(p.opciones_json.get('correcta'), 'B')
        reset_progreso_pasos_modulo(self.prog, save=True)
        entregar_paso_indice(self.prog, self.mod, 1)
        self.prog.refresh_from_db()
        self.assertTrue(self.prog.esperando_respuesta_evaluacion_paso)
        out = procesar_respuesta_evaluacion_paso(self.est, self.prog, 'b')
        self.assertIsNotNone(out)
        self.prog.refresh_from_db()
        self.assertFalse(self.prog.esperando_respuesta_evaluacion_paso)


class ModuleStepsLegacyRegressionTests(TestCase):
    """Sin pasos activos: continuar_leccion con listo sigue cerrando módulo (curso 2 mod, sin IA)."""

    def setUp(self):
        self.curso = Curso.objects.create(
            nombre='Curso legacy drip0',
            descripcion='d',
            dias_espera_entre_modulos=0,
            usar_agentes_ia=False,
        )
        self.m1 = Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='A',
            descripcion='d',
            contenido='c1',
            duracion_dias=7,
        )
        self.m2 = Modulo.objects.create(
            curso=self.curso,
            numero=2,
            titulo='B',
            descripcion='d',
            contenido='c2',
            duracion_dias=7,
        )
        self.est = Estudiante.objects.create(
            cedula='20887766',
            nombre='Bob Legacy',
            telefono='573001112233',
        )
        ProgresoEstudiante.objects.create(
            estudiante=self.est,
            curso=self.curso,
            modulo_actual=self.m1,
        )

    def test_listo_sin_pasos_avanza_a_modulo_2(self):
        r = get_response_for_intent(
            'continuar_leccion',
            self.est.nombre,
            estudiante_id=self.est.id,
            mensaje_original='listo',
        )
        self.assertIn('Módulo 2', r)
        self.assertIn('B', r)


class SelectorCursoPasosTests(TestCase):
    """selector_curso alineado a pasos (sin volcar contenido legacy)."""

    def setUp(self):
        self.curso = Curso.objects.create(
            nombre='Curso selector pasos',
            descripcion='d',
            dias_espera_entre_modulos=0,
            usar_agentes_ia=False,
        )
        self.m1 = Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='Mod uno',
            descripcion='d',
            contenido='TEXTO_LEGACY_NO_DEBE_APARECER_EN_SELECTOR_CON_PASOS',
            duracion_dias=7,
        )
        self.est = Estudiante.objects.create(
            cedula='33445566',
            nombre='Chooser',
            telefono='5730011998877',
        )

    def test_selector_solo_numero_con_pasos_entrega_paso_no_legacy(self):
        from core.models import PasoModulo
        from core.selector_curso import continuar_curso_seleccionado

        s1 = _seccion(self.m1, 1)
        PasoModulo.objects.create(
            modulo=self.m1,
            seccion=s1,
            orden=1,
            titulo='Micro paso',
            tipo=PasoModulo.TIPO_CONTENIDO,
            contenido='Contenido solo paso 1',
        )
        r = continuar_curso_seleccionado(self.est.id, 1, '1')
        self.assertNotIn('TEXTO_LEGACY_NO_DEBE_APARECER', r)
        self.assertIn('Contenido solo paso 1', r)
        self.assertIn('[MULTI_MSG]', r)


class SelectorCursoAgentesPrimeraVezTests(TestCase):
    """Al crear progreso vía número (selector), mostrar tutor + compañero como en inscripción."""

    def setUp(self):
        self.curso = Curso.objects.create(
            nombre='Curso selector agentes',
            descripcion='d',
            dias_espera_entre_modulos=0,
            usar_agentes_ia=True,
            nombre_agente_tutor='Claudia',
            nombre_agente_asistente='Darío',
        )
        self.m1 = Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='Mod uno',
            descripcion='d',
            contenido='LEGACY_TEXTO',
            duracion_dias=7,
        )
        self.est = Estudiante.objects.create(
            cedula='44556677',
            nombre='Julián Selector',
            telefono='5730011223344',
        )

    def test_selector_creado_incluye_facilitadora_y_companero(self):
        from core.models import PasoModulo
        from core.selector_curso import continuar_curso_seleccionado

        s1 = _seccion(self.m1, 1)
        PasoModulo.objects.create(
            modulo=self.m1,
            seccion=s1,
            orden=1,
            titulo='Micro paso',
            tipo=PasoModulo.TIPO_CONTENIDO,
            contenido='Contenido solo paso 1',
        )
        r = continuar_curso_seleccionado(self.est.id, 1, '1')
        self.assertIn('Iniciando', r)
        self.assertIn('Facilitadora Claudia', r)
        self.assertIn('Darío', r)
        self.assertIn('Contenido solo paso 1', r)

    def test_selector_retomar_no_repite_presentacion_agentes(self):
        from core.models import PasoModulo
        from core.models import ProgresoEstudiante
        from core.selector_curso import continuar_curso_seleccionado

        s1 = _seccion(self.m1, 1)
        PasoModulo.objects.create(
            modulo=self.m1,
            seccion=s1,
            orden=1,
            titulo='Micro paso',
            tipo=PasoModulo.TIPO_CONTENIDO,
            contenido='Contenido solo paso 1',
        )
        ProgresoEstudiante.objects.create(
            estudiante=self.est,
            curso=self.curso,
            modulo_actual=self.m1,
        )
        r = continuar_curso_seleccionado(self.est.id, 1, '1')
        self.assertIn('Retomando', r)
        self.assertNotIn('Facilitadora Claudia', r)
        # Progreso pre-creado sin material entregado: debe mandar micros, no solo CTA.
        self.assertIn('Contenido solo paso 1', r)


class ModoEntregaExplicitoTests(TestCase):
    """modo_entrega en Modulo: legacy / pasos / auto."""

    def setUp(self):
        self.curso = Curso.objects.create(
            nombre='Curso modo entrega',
            descripcion='d',
            dias_espera_entre_modulos=0,
            usar_agentes_ia=False,
        )
        self.m1 = Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='Mod uno',
            descripcion='d',
            contenido='TEXTO_LEGACY_SELECTOR',
            duracion_dias=7,
        )
        self.m2 = Modulo.objects.create(
            curso=self.curso,
            numero=2,
            titulo='Mod dos',
            descripcion='d',
            contenido='c2',
            duracion_dias=7,
        )
        self.est = Estudiante.objects.create(
            cedula='77889900',
            nombre='Modo Tester',
            telefono='5730011220055',
        )
        ProgresoEstudiante.objects.create(
            estudiante=self.est,
            curso=self.curso,
            modulo_actual=self.m1,
        )

    def test_modo_legacy_ignora_pasos(self):
        from core.selector_curso import continuar_curso_seleccionado

        s1 = _seccion(self.m1, 1)
        PasoModulo.objects.create(
            modulo=self.m1,
            seccion=s1,
            orden=1,
            titulo='Paso interno',
            tipo=PasoModulo.TIPO_CONTENIDO,
            contenido='NO_DEBE_SALIR_EN_LEGACY',
        )
        self.m1.modo_entrega = Modulo.MODO_ENTREGA_LEGACY
        self.m1.save(update_fields=['modo_entrega'])
        r = continuar_curso_seleccionado(self.est.id, 1, '1')
        self.assertIn('TEXTO_LEGACY_SELECTOR', r)
        self.assertNotIn('NO_DEBE_SALIR_EN_LEGACY', r)

    def test_modo_pasos_sin_pasos_activos_listo(self):
        self.m1.modo_entrega = Modulo.MODO_ENTREGA_PASOS
        self.m1.save(update_fields=['modo_entrega'])
        with self.assertLogs('core.module_steps', level='WARNING'):
            r = get_response_for_intent(
                'continuar_leccion',
                self.est.nombre,
                estudiante_id=self.est.id,
                mensaje_original='listo',
            )
        self.assertIn('organizando el contenido', r)

    def test_modo_auto_con_pasos_usa_pasos(self):
        from core.selector_curso import continuar_curso_seleccionado

        self.assertEqual(self.m1.modo_entrega, Modulo.MODO_ENTREGA_AUTO)
        # Primera inscripción (sin progreso previo) debe entregar el micro, no solo CTA.
        ProgresoEstudiante.objects.filter(estudiante=self.est, curso=self.curso).delete()
        s1 = _seccion(self.m1, 1)
        PasoModulo.objects.create(
            modulo=self.m1,
            seccion=s1,
            orden=1,
            titulo='Solo paso auto',
            tipo=PasoModulo.TIPO_CONTENIDO,
            contenido='Bloque auto',
        )
        r = continuar_curso_seleccionado(self.est.id, 1, '1')
        self.assertNotIn('TEXTO_LEGACY_SELECTOR', r)
        self.assertIn('Bloque auto', r)

    def test_modo_auto_sin_pasos_usa_legacy(self):
        self.assertEqual(self.m1.modo_entrega, Modulo.MODO_ENTREGA_AUTO)
        r = get_response_for_intent(
            'continuar_leccion',
            self.est.nombre,
            estudiante_id=self.est.id,
            mensaje_original='listo',
        )
        self.assertIn('Módulo 2', r)
        self.assertIn('Mod dos', r)


class MiniExamenTrasMicrocontenidosTests(TestCase):
    """PreguntaModulo (mini examen) después del último PasoModulo."""

    def setUp(self):
        self.curso = Curso.objects.create(
            nombre='Curso mini tras pasos',
            descripcion='d',
            dias_espera_entre_modulos=0,
            usar_agentes_ia=False,
        )
        self.m1 = Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='M1',
            descripcion='d',
            contenido='legacy',
            duracion_dias=7,
            modo_entrega=Modulo.MODO_ENTREGA_PASOS,
        )
        self.m2 = Modulo.objects.create(
            curso=self.curso,
            numero=2,
            titulo='M2',
            descripcion='d',
            contenido='sig',
            duracion_dias=7,
        )
        s1 = _seccion(self.m1, 1)
        PasoModulo.objects.create(
            modulo=self.m1,
            seccion=s1,
            orden=1,
            titulo='Solo micro',
            tipo=PasoModulo.TIPO_CONTENIDO,
            contenido='Contenido paso 1',
        )
        PreguntaModulo.objects.create(
            modulo=self.m1,
            pregunta='PREG_MINI_EXAMEN_TRAS_PASOS',
            opcion_a='Uno',
            opcion_b='Dos',
            respuesta_correcta='A',
            activa=True,
        )
        self.est = Estudiante.objects.create(
            cedula='55667788',
            nombre='Mini Paso',
            telefono='573009991010',
        )
        ProgresoEstudiante.objects.create(
            estudiante=self.est,
            curso=self.curso,
            modulo_actual=self.m1,
        )

    def test_mini_examen_tras_ultimo_listo_con_pasos(self):
        get_response_for_intent(
            'continuar_leccion',
            self.est.nombre,
            estudiante_id=self.est.id,
            mensaje_original='listo',
        )
        import time
        est = Estudiante.objects.get(pk=self.est.id)
        ctx = dict(est.contexto_temporal or {})
        ctx['_ts_leccion'] = time.time() - 60
        est.contexto_temporal = ctx
        est.save(update_fields=['contexto_temporal'])

        r2 = get_response_for_intent(
            'continuar_leccion',
            self.est.nombre,
            estudiante_id=self.est.id,
            mensaje_original='listo',
        )
        self.assertIn('PREG_MINI_EXAMEN_TRAS_PASOS', r2)
        self.assertIn('letra correcta', r2.lower())


class SectionBatchTests(TestCase):
    """Bloques por sección + secciones_por_listo (fase A/B)."""

    def setUp(self):
        self.curso = Curso.objects.create(
            nombre='Curso secciones',
            descripcion='d',
            dias_espera_entre_modulos=0,
            usar_agentes_ia=False,
        )
        self.mod = Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='M1',
            descripcion='d',
            contenido='legacy',
            duracion_dias=7,
        )
        self.est = Estudiante.objects.create(
            cedula='10990011',
            nombre='Sec Batch',
            telefono='573009990022',
        )
        self.prog = ProgresoEstudiante.objects.create(
            estudiante=self.est,
            curso=self.curso,
            modulo_actual=self.mod,
        )

    def test_varios_pasos_misma_seccion_un_listo(self):
        s1 = _seccion(self.mod, 1)
        for o, tit in [(1, 'A'), (2, 'B')]:
            PasoModulo.objects.create(
                modulo=self.mod,
                seccion=s1,
                orden=o,
                titulo=tit,
                tipo=PasoModulo.TIPO_CONTENIDO,
                contenido=f'c{o}',
            )
        self.mod.secciones_por_listo = 1
        self.mod.save(update_fields=['secciones_por_listo'])
        reset_progreso_pasos_modulo(self.prog, save=True)
        msg = entregar_bloque_secciones_desde_paso(self.prog, self.mod, 1)
        self.prog.refresh_from_db()
        self.assertEqual(self.prog.paso_actual_modulo, 3)
        self.assertIn('c1', msg)
        self.assertIn('c2', msg)
        self.assertIn('siguiente', msg.lower())
        self.assertIn('listo', msg.lower())

    def test_dos_secciones_titulos_un_listo_por_seccion(self):
        """Aunque secciones_por_listo sea 2, solo se entrega una sección; el segundo *listo* abre la otra."""
        sa = _seccion(self.mod, 1, titulo='Bloque Alfa')
        sb = _seccion(self.mod, 2, titulo='Bloque Beta')
        PasoModulo.objects.create(
            modulo=self.mod,
            seccion=sa,
            orden=1,
            titulo='p1',
            tipo=PasoModulo.TIPO_CONTENIDO,
            contenido='uno',
        )
        PasoModulo.objects.create(
            modulo=self.mod,
            seccion=sb,
            orden=2,
            titulo='p2',
            tipo=PasoModulo.TIPO_CONTENIDO,
            contenido='dos',
        )
        self.mod.secciones_por_listo = 2
        self.mod.save(update_fields=['secciones_por_listo'])
        reset_progreso_pasos_modulo(self.prog, save=True)
        msg1 = entregar_bloque_secciones_desde_paso(self.prog, self.mod, 1)
        self.assertNotIn('Bloque Alfa', msg1)
        self.assertIn('uno', msg1)
        self.assertNotIn('dos', msg1)
        self.assertIn('revisar el contenido', msg1.lower())
        self.assertNotIn('escribí', msg1.lower())
        self.prog.refresh_from_db()
        self.assertEqual(self.prog.paso_actual_modulo, 2)

        msg2 = entregar_bloque_secciones_desde_paso(self.prog, self.mod, 2)
        self.assertNotIn('Bloque Beta', msg2)
        self.assertIn('dos', msg2)
        self.assertIn('siguiente', msg2.lower())
        self.assertIn('listo', msg2.lower())
        self.prog.refresh_from_db()
        self.assertEqual(self.prog.paso_actual_modulo, 3)

    def test_dos_secciones_sin_titulo_dos_listos(self):
        sa = _seccion(self.mod, 1, titulo='')
        sb = _seccion(self.mod, 2, titulo='')
        PasoModulo.objects.create(
            modulo=self.mod,
            seccion=sa,
            orden=1,
            titulo='p1',
            tipo=PasoModulo.TIPO_CONTENIDO,
            contenido='uno',
        )
        PasoModulo.objects.create(
            modulo=self.mod,
            seccion=sb,
            orden=2,
            titulo='p2',
            tipo=PasoModulo.TIPO_CONTENIDO,
            contenido='dos',
        )
        self.mod.secciones_por_listo = 2
        self.mod.save(update_fields=['secciones_por_listo'])
        reset_progreso_pasos_modulo(self.prog, save=True)
        msg1 = entregar_bloque_secciones_desde_paso(self.prog, self.mod, 1)
        self.assertIn('uno', msg1)
        self.assertNotIn('dos', msg1)
        self.assertNotIn('📑 *Bloque 1*', msg1)

        msg2 = entregar_bloque_secciones_desde_paso(self.prog, self.mod, 2)
        self.assertIn('dos', msg2)
        self.assertNotIn('📑 *Bloque 2*', msg2)
        self.assertIn('siguiente', msg2.lower())
        self.assertIn('listo', msg2.lower())
        self.prog.refresh_from_db()
        self.assertEqual(self.prog.paso_actual_modulo, 3)

    def test_eval_en_bloque_corta_en_primera_eval(self):
        s1 = _seccion(self.mod, 1)
        PasoModulo.objects.create(
            modulo=self.mod,
            seccion=s1,
            orden=1,
            titulo='Lectura',
            tipo=PasoModulo.TIPO_CONTENIDO,
            contenido='Lee',
        )
        PasoModulo.objects.create(
            modulo=self.mod,
            seccion=s1,
            orden=2,
            titulo='Quiz',
            tipo=PasoModulo.TIPO_EVAL_OPC,
            contenido='?',
            opciones_json={'A': 'Si', 'B': 'No', 'correcta': 'A'},
        )
        PasoModulo.objects.create(
            modulo=self.mod,
            seccion=s1,
            orden=3,
            titulo='Extra',
            tipo=PasoModulo.TIPO_CONTENIDO,
            contenido='No_va_en_primer_listo',
        )
        self.mod.secciones_por_listo = 1
        self.mod.save(update_fields=['secciones_por_listo'])
        reset_progreso_pasos_modulo(self.prog, save=True)
        entregar_bloque_secciones_desde_paso(self.prog, self.mod, 1)
        self.prog.refresh_from_db()
        self.assertTrue(self.prog.esperando_respuesta_evaluacion_paso)
        self.assertEqual(self.prog.paso_actual_modulo, 2)

    def test_eval_en_primera_fila_siguiente_seccion_va_en_mismo_batch(self):
        """Pregunta en sección 1 y opciones en sección 2: mismo envío (regresión WhatsApp)."""
        sa = _seccion(self.mod, 1)
        sb = _seccion(self.mod, 2)
        PasoModulo.objects.create(
            modulo=self.mod,
            seccion=sa,
            orden=1,
            titulo='Enunciado',
            tipo=PasoModulo.TIPO_CONTENIDO,
            contenido='¿Cuál es el principal objetivo?',
        )
        PasoModulo.objects.create(
            modulo=self.mod,
            seccion=sb,
            orden=2,
            titulo='Opciones',
            tipo=PasoModulo.TIPO_EVAL_OPC,
            contenido='Elige:',
            eval_opcion_a='Informar',
            eval_opcion_b='Vender',
            respuesta_correcta='A',
        )
        self.mod.secciones_por_listo = 1
        self.mod.save(update_fields=['secciones_por_listo'])
        reset_progreso_pasos_modulo(self.prog, save=True)
        msg = entregar_bloque_secciones_desde_paso(self.prog, self.mod, 1)
        self.assertIn('¿Cuál es el principal objetivo?', msg)
        self.assertIn('*A*)', msg)
        self.assertIn('*B*)', msg)
        self.prog.refresh_from_db()
        self.assertTrue(self.prog.esperando_respuesta_evaluacion_paso)


class InscripcionModuloCeroConPasosTests(TestCase):
    """Módulo 0 con pasos: el contenido del módulo debe enviarse junto a la inscripción."""

    def setUp(self):
        self.curso = Curso.objects.create(
            nombre='Curso mod0 pasos',
            descripcion='d',
            dias_espera_entre_modulos=0,
            usar_agentes_ia=False,
        )
        self.m0 = Modulo.objects.create(
            curso=self.curso,
            numero=0,
            titulo='Bienvenida',
            descripcion='d',
            contenido='CONTENIDO_EDUCATIVO_MODULO_CERO',
            duracion_dias=7,
            modo_entrega=Modulo.MODO_ENTREGA_PASOS,
        )
        Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='Uno',
            descripcion='d',
            contenido='x',
            duracion_dias=7,
        )
        s1 = _seccion(self.m0, 1)
        PasoModulo.objects.create(
            modulo=self.m0,
            seccion=s1,
            orden=1,
            titulo='Micro',
            tipo=PasoModulo.TIPO_CONTENIDO,
            contenido='TEXTO_MICRO_PASO',
        )
        self.est = Estudiante.objects.create(
            cedula='11223344',
            nombre='Mod Cero',
            telefono='5730011223344',
        )

    def test_inscripcion_incluye_contenido_modulo_cero_antes_de_pasos(self):
        r = get_response_for_intent(
            'inscribir_curso',
            self.est.nombre,
            estudiante_id=self.est.id,
            mensaje_original='1',
        )
        self.assertIn('CONTENIDO_EDUCATIVO_MODULO_CERO', r)
        self.assertIn('TEXTO_MICRO_PASO', r)
        self.assertIn('📖 *0.', r)


class InscripcionConPasosSinContenidoModuloMuestraAgentesTests(TestCase):
    """Si el contenido legacy del módulo está vacío pero hay pasos, igual deben verse tutor y asistente."""

    def setUp(self):
        self.curso = Curso.objects.create(
            nombre='Curso solo pasos vacío',
            descripcion='d',
            dias_espera_entre_modulos=0,
            usar_agentes_ia=False,
        )
        self.m1 = Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='Solo pasos',
            descripcion='d',
            contenido='',
            duracion_dias=7,
            modo_entrega=Modulo.MODO_ENTREGA_PASOS,
        )
        s1 = _seccion(self.m1, 1)
        PasoModulo.objects.create(
            modulo=self.m1,
            seccion=s1,
            orden=1,
            titulo='Paso',
            tipo=PasoModulo.TIPO_CONTENIDO,
            contenido='BLOQUE_PASO_UNICO',
        )
        self.est = Estudiante.objects.create(
            cedula='55664433',
            nombre='Sin Legacy',
            telefono='573009887766',
        )

    def test_facilitadora_y_asistente_en_multimsg(self):
        r = get_response_for_intent(
            'inscribir_curso',
            self.est.nombre,
            estudiante_id=self.est.id,
            mensaje_original='1',
        )
        self.assertIn('Facilitadora', r)
        self.assertIn('compañero de estudio', r)
        self.assertIn('BLOQUE_PASO_UNICO', r)


class RetoModulosCoberturaTests(TestCase):
    """Regresión: reto Darío con checkpoint en módulo < 4 debe incluir módulos hasta ese número."""

    def setUp(self):
        self.curso = Curso.objects.create(
            nombre='Curso reto cobertura',
            descripcion='d',
            dias_espera_entre_modulos=0,
            usar_agentes_ia=True,
        )
        self.m1 = Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='A',
            descripcion='',
            contenido='',
            duracion_dias=7,
        )
        self.m2 = Modulo.objects.create(
            curso=self.curso,
            numero=2,
            titulo='B',
            descripcion='',
            contenido='',
            duracion_dias=7,
        )

    def test_checkpoint_modulo_2_incluye_hasta_2(self):
        from core.tutor_ia_modulo import (
            descripcion_rango_modulos_reto_esp,
            listar_modulos_cobertura_reto,
        )

        rows = listar_modulos_cobertura_reto(self.m2, self.curso)
        self.assertEqual([r.numero for r in rows], [1, 2])
        self.assertEqual(descripcion_rango_modulos_reto_esp(rows), 'los módulos 1 a 2')

    def test_checkpoint_modulo_5_ventana_desde_4(self):
        from core.tutor_ia_modulo import listar_modulos_cobertura_reto

        m3 = Modulo.objects.create(
            curso=self.curso,
            numero=3,
            titulo='C',
            descripcion='',
            contenido='',
            duracion_dias=7,
        )
        m4 = Modulo.objects.create(
            curso=self.curso,
            numero=4,
            titulo='D',
            descripcion='',
            contenido='',
            duracion_dias=7,
        )
        m5 = Modulo.objects.create(
            curso=self.curso,
            numero=5,
            titulo='E',
            descripcion='',
            contenido='',
            duracion_dias=7,
        )
        rows = listar_modulos_cobertura_reto(m5, self.curso)
        self.assertEqual([r.numero for r in rows], [4, 5])
        self.assertNotIn(3, [r.numero for r in rows])


class CheckpointIgnoraDripFinModulo1Tests(TestCase):
    """
    Tras varios microcontenidos + última eval ABCD en módulo 1, con drip activo,
    debe entrar el checkpoint (Darío) y no devolver solo el mensaje de pausa drip.
    """

    def setUp(self):
        self.curso = Curso.objects.create(
            nombre='Curso drip vs checkpoint',
            descripcion='d',
            dias_espera_entre_modulos=7,
            usar_agentes_ia=True,
        )
        self.m1 = Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='Módulo uno',
            descripcion='d',
            contenido='legacy',
            duracion_dias=7,
            modo_entrega=Modulo.MODO_ENTREGA_PASOS,
            facilitador_checkpoint=Modulo.FACILITADOR_CP_SI,
        )
        self.m2 = Modulo.objects.create(
            curso=self.curso,
            numero=2,
            titulo='Módulo dos',
            descripcion='d',
            contenido='sig',
            duracion_dias=7,
        )
        self.est = Estudiante.objects.create(
            cedula='11223344',
            nombre='Est DripCk',
            telefono='5730011223344',
        )
        self.prog = ProgresoEstudiante.objects.create(
            estudiante=self.est,
            curso=self.curso,
            modulo_actual=self.m1,
        )

    def test_fin_modulo_1_con_pasos_y_eval_abcd_drip_no_bloquea_agentes(self):
        from core.models import PasoModulo
        from core.module_steps import reset_progreso_pasos_modulo
        from core.response_templates import get_response_for_intent

        s1 = _seccion(self.m1, 1, 'Sección')
        for i, txt in enumerate(['Micro 1', 'Micro 2', 'Micro 3'], start=1):
            PasoModulo.objects.create(
                modulo=self.m1,
                seccion=s1,
                orden=i,
                titulo=f'Paso {i}',
                tipo=PasoModulo.TIPO_CONTENIDO,
                contenido=txt,
            )
        PasoModulo.objects.create(
            modulo=self.m1,
            seccion=s1,
            orden=4,
            titulo='Eval ABCD',
            tipo=PasoModulo.TIPO_EVAL_OPC,
            contenido='Pregunta final',
            opciones_json={'A': 'Uno', 'B': 'Dos', 'correcta': 'B'},
        )
        reset_progreso_pasos_modulo(self.prog, save=True)
        self.prog.paso_actual_modulo = 5
        self.prog.esperando_respuesta_evaluacion_paso = False
        self.prog.save(
            update_fields=[
                'paso_actual_modulo',
                'esperando_respuesta_evaluacion_paso',
                'paso_evaluacion_paso',
            ]
        )

        r = get_response_for_intent(
            'continuar_leccion',
            self.est.nombre,
            estudiante_id=self.est.id,
            mensaje_original='listo',
        )
        self.assertNotIn('Tu próxima lección se desbloquea el', r)
        self.assertIn('pausa para repasar', r.lower())
        self.assertIn('Darío', r)

        self.est.refresh_from_db()
        self.assertEqual(self.est.estado_onboarding, 'esperando_respuesta_asistente')

    def test_sin_checkpoint_si_ia_off_drip_sigue_apegado(self):
        from core.models import PasoModulo
        from core.module_steps import reset_progreso_pasos_modulo
        from core.response_templates import get_response_for_intent

        self.curso.usar_agentes_ia = False
        self.curso.save(update_fields=['usar_agentes_ia'])

        s1 = _seccion(self.m1, 1, 'S')
        PasoModulo.objects.create(
            modulo=self.m1,
            seccion=s1,
            orden=1,
            titulo='P1',
            tipo=PasoModulo.TIPO_CONTENIDO,
            contenido='x',
        )
        reset_progreso_pasos_modulo(self.prog, save=True)
        self.prog.paso_actual_modulo = 2
        self.prog.save(update_fields=['paso_actual_modulo', 'paso_evaluacion_paso'])

        r = get_response_for_intent(
            'continuar_leccion',
            self.est.nombre,
            estudiante_id=self.est.id,
            mensaje_original='listo',
        )
        self.assertIn('Tu próxima lección se desbloquea el', r)


@override_settings(TWILIO_ACCOUNT_SID='', TWILIO_AUTH_TOKEN='')
class RetoFacilitadoraRespetaDripTests(TestCase):
    """Tras evaluar el reto de la facilitadora (no final), debe aplicar drip antes de puntero→módulo 2."""

    def setUp(self):
        self.curso = Curso.objects.create(
            nombre='Curso reto + drip',
            descripcion='d',
            dias_espera_entre_modulos=7,
            usar_agentes_ia=True,
        )
        self.m1 = Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='M1',
            descripcion='d',
            contenido='c',
            duracion_dias=7,
        )
        self.m2 = Modulo.objects.create(
            curso=self.curso,
            numero=2,
            titulo='M2',
            descripcion='d',
            contenido='sig',
            duracion_dias=7,
        )
        self.est = Estudiante.objects.create(
            cedula='99887766',
            nombre='Est Reto Drip',
            telefono='5730099988776',
            acepto_terminos=True,
            estado_chat='ACTIVO',
        )
        self.prog = ProgresoEstudiante.objects.create(
            estudiante=self.est,
            curso=self.curso,
            modulo_actual=self.m1,
        )

    def _webhook_reto(self, body='respuesta al reto de prueba', sid_suffix='a'):
        from core.views import _procesar_twilio_webhook

        _procesar_twilio_webhook(
            {
                'Body': body,
                'From': 'whatsapp:+5730099988776',
                'To': 'whatsapp:+14155238886',
                'MessageSid': f'SM_test_reto_drip_{sid_suffix}',
                'NumMedia': '0',
            }
        )

    @patch('core.tutor_ia_modulo.evaluar_reto_facilitador', return_value=(8, 'Feedback reto'))
    def test_con_drip_no_adelanta_modulo_actual(self, _mock_eval):
        ModuloCompletado.objects.create(progreso=self.prog, modulo=self.m1)
        self.prog.fecha_ultimo_avance = timezone.now() - timedelta(days=1)
        self.prog.save(update_fields=['fecha_ultimo_avance'])

        self.est.estado_onboarding = 'esperando_respuesta_reto'
        self.est.contexto_temporal = {
            'tipo': 'reto_facilitador',
            'modulos_reto_ids': [self.m1.id],
            'reto_texto': 'Describa X',
            'progreso_id': self.prog.id,
            'es_final': False,
        }
        self.est.save(update_fields=['estado_onboarding', 'contexto_temporal'])

        self._webhook_reto(sid_suffix='drip')

        self.prog.refresh_from_db()
        self.est.refresh_from_db()
        self.assertEqual(self.prog.modulo_actual_id, self.m1.id)
        self.assertEqual(self.est.estado_onboarding, 'completado')
        self.assertNotIn('post_reto_entregar_modulo_id', self.est.contexto_temporal or {})

    @patch('core.tutor_ia_modulo.evaluar_reto_facilitador', return_value=(7, 'OK'))
    def test_sin_espera_entre_modulos_sigue_avanzando_puntero(self, _mock_eval):
        self.curso.dias_espera_entre_modulos = 0
        self.curso.save(update_fields=['dias_espera_entre_modulos'])
        ModuloCompletado.objects.create(progreso=self.prog, modulo=self.m1)
        self.prog.fecha_ultimo_avance = timezone.now()
        self.prog.save(update_fields=['fecha_ultimo_avance'])

        self.est.estado_onboarding = 'esperando_respuesta_reto'
        self.est.contexto_temporal = {
            'tipo': 'reto_facilitador',
            'modulos_reto_ids': [self.m1.id],
            'reto_texto': 'Describa Y',
            'progreso_id': self.prog.id,
            'es_final': False,
        }
        self.est.save(update_fields=['estado_onboarding', 'contexto_temporal'])

        self._webhook_reto(sid_suffix='nodrip')

        self.prog.refresh_from_db()
        self.est.refresh_from_db()
        self.assertEqual(self.prog.modulo_actual_id, self.m2.id)
        self.assertEqual(
            (self.est.contexto_temporal or {}).get('post_reto_entregar_modulo_id'),
            self.m2.id,
        )


class ModuloContenidoVsMicrocontenidosTests(TestCase):
    def setUp(self):
        self.curso = Curso.objects.create(
            nombre='Curso validación',
            descripcion='d',
            dias_espera_entre_modulos=0,
        )
        self.mod = Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='M1',
            descripcion='d',
            contenido='Texto legacy',
            duracion_dias=7,
        )

    def test_sin_microcontenidos_contenido_obligatorio(self):
        from django.core.exceptions import ValidationError

        from core.module_steps import validar_contenido_modulo

        self.mod.contenido = ''
        with self.assertRaises(ValidationError):
            validar_contenido_modulo('', self.mod)

    def test_con_microcontenidos_contenido_opcional(self):
        from core.module_steps import validar_contenido_modulo

        s1 = _seccion(self.mod, 1)
        PasoModulo.objects.create(
            modulo=self.mod,
            seccion=s1,
            orden=1,
            titulo='Paso 1',
            tipo=PasoModulo.TIPO_CONTENIDO,
            contenido='Hola paso',
        )
        validar_contenido_modulo('', self.mod)
        self.mod.contenido = ''
        self.mod.full_clean()
        self.mod.save()

    def test_modulo_nuevo_sin_contenido_falla(self):
        from django.core.exceptions import ValidationError

        from core.module_steps import validar_contenido_modulo

        nuevo = Modulo(
            curso=self.curso,
            numero=2,
            titulo='M2',
            descripcion='d',
            contenido='',
            duracion_dias=7,
        )
        with self.assertRaises(ValidationError):
            validar_contenido_modulo('', nuevo)

    def test_formset_admin_sin_contenido_ni_pasos_falla(self):
        from django.contrib.auth import get_user_model
        from django.test import RequestFactory

        User = get_user_model()
        user = User.objects.create_superuser('admin_mod', 'a@test.com', 'pass')
        request = RequestFactory().get('/')
        request.user = user

        site = AdminSite()
        inline = PasoModuloInline(Modulo, site)
        FormSet = inline.get_formset(request=request, obj=self.mod)
        prefix = FormSet.get_default_prefix()
        data = {
            'contenido': '',
            f'{prefix}-TOTAL_FORMS': '0',
            f'{prefix}-INITIAL_FORMS': '0',
            f'{prefix}-MIN_NUM_FORMS': '0',
            f'{prefix}-MAX_NUM_FORMS': '1000',
        }
        formset = FormSet(data, instance=self.mod)
        self.assertFalse(formset.is_valid())

    def test_formset_admin_con_paso_permite_contenido_vacio(self):
        from django.contrib.auth import get_user_model
        from django.test import RequestFactory

        s1 = _seccion(self.mod, 1)
        User = get_user_model()
        user = User.objects.create_superuser('admin_mod2', 'b@test.com', 'pass')
        request = RequestFactory().get('/')
        request.user = user

        site = AdminSite()
        inline = PasoModuloInline(Modulo, site)
        FormSet = inline.get_formset(request=request, obj=self.mod)
        prefix = FormSet.get_default_prefix()
        data = {
            'contenido': '',
            f'{prefix}-TOTAL_FORMS': '1',
            f'{prefix}-INITIAL_FORMS': '0',
            f'{prefix}-MIN_NUM_FORMS': '0',
            f'{prefix}-MAX_NUM_FORMS': '1000',
            f'{prefix}-0-seccion': str(s1.pk),
            f'{prefix}-0-orden': '1',
            f'{prefix}-0-modulo': str(self.mod.pk),
            f'{prefix}-0-tipo': PasoModulo.TIPO_CONTENIDO,
            f'{prefix}-0-contenido': 'Micro paso 1',
            f'{prefix}-0-activo': 'on',
            f'{prefix}-0-requiere_listo_para_avanzar': 'on',
        }
        formset = FormSet(data, instance=self.mod)
        self.assertTrue(formset.is_valid(), formset.errors)

    def test_formset_sin_cleaned_data_usa_pasos_en_bd(self):
        """Regresión: con micros en BD, no exigir contenido aunque el formset no limpie bien."""
        from core.module_steps import validar_contenido_modulo

        s1 = _seccion(self.mod, 1)
        paso = PasoModulo.objects.create(
            modulo=self.mod,
            seccion=s1,
            orden=1,
            titulo='Ya guardado',
            tipo=PasoModulo.TIPO_CONTENIDO,
            contenido='Texto del paso',
        )

        class _FakeForm:
            prefix = 'pasos-0'
            cleaned_data = None  # simula form con errores / sin clean
            data = {}
            instance = paso

        class _FakeFormSet:
            forms = [_FakeForm()]

        # No debe lanzar: hay microcontenido persistido
        validar_contenido_modulo('', self.mod, pasos_formset=_FakeFormSet())

    def test_formset_borrar_ultimo_paso_exige_contenido(self):
        from django.core.exceptions import ValidationError

        from core.module_steps import validar_contenido_modulo

        s1 = _seccion(self.mod, 1)
        paso = PasoModulo.objects.create(
            modulo=self.mod,
            seccion=s1,
            orden=1,
            titulo='A borrar',
            tipo=PasoModulo.TIPO_CONTENIDO,
            contenido='x',
        )

        class _FakeForm:
            prefix = 'pasos-0'
            cleaned_data = {'DELETE': True, 'seccion': s1}
            data = {'pasos-0-DELETE': 'on'}
            instance = paso

        class _FakeFormSet:
            forms = [_FakeForm()]

        with self.assertRaises(ValidationError):
            validar_contenido_modulo('', self.mod, pasos_formset=_FakeFormSet())


class AntiDuplicadoPostEvalPasosTests(TestCase):
    """Tras eval final de micros, continuar_leccion interno no debe caer en anti-duplicado 45s."""

    def setUp(self):
        self.curso = Curso.objects.create(
            nombre='Curso anti-dup',
            descripcion='d',
            dias_espera_entre_modulos=0,
            usar_agentes_ia=False,
        )
        self.m1 = Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='M1',
            descripcion='d',
            contenido='legacy',
            duracion_dias=7,
            modo_entrega=Modulo.MODO_ENTREGA_PASOS,
        )
        self.m2 = Modulo.objects.create(
            curso=self.curso,
            numero=2,
            titulo='M2',
            descripcion='d',
            contenido='sig',
            duracion_dias=7,
        )
        self.est = Estudiante.objects.create(
            cedula='55667788',
            nombre='Anti Dup',
            telefono='5730099112233',
        )
        self.prog = ProgresoEstudiante.objects.create(
            estudiante=self.est,
            curso=self.curso,
            modulo_actual=self.m1,
        )

    def test_cola_post_eval_no_devuelve_cargando(self):
        import time

        from core.models import PasoModulo
        from core.module_steps import _respuesta_cola_tras_avanzar_eval_opc

        s1 = _seccion(self.m1, 1, 'S')
        PasoModulo.objects.create(
            modulo=self.m1,
            seccion=s1,
            orden=1,
            titulo='Eval',
            tipo=PasoModulo.TIPO_EVAL_OPC,
            contenido='Q',
            opciones_json={'A': '1', 'B': '2', 'correcta': 'B'},
            feedback_correcto='Bien hecho',
        )
        # Simula que hace segundos se entregó material (*listo*).
        self.est.contexto_temporal = {'_ts_leccion': time.time()}
        self.est.save(update_fields=['contexto_temporal'])
        self.prog.paso_actual_modulo = 2
        self.prog.esperando_respuesta_evaluacion_paso = False
        self.prog.save(update_fields=['paso_actual_modulo', 'esperando_respuesta_evaluacion_paso'])

        paso = self.m1.pasos.first()
        r = _respuesta_cola_tras_avanzar_eval_opc(
            self.est, self.prog, paso, n=1, es_acierto=True,
        )
        self.assertNotIn('se está cargando', (r or '').lower())
        self.assertIn('Bien hecho', r)


class MultiCursoDripNoHijackPasosTests(TestCase):
    """Si un curso está en drip y otro mid-pasos, *listo* no debe atrapar en el drip."""

    def setUp(self):
        from django.utils import timezone
        from datetime import timedelta

        self.org = Cliente.objects.create(
            nombre='Org Multi',
            contacto_principal='C',
            email='multi@t.com',
            telefono='573008887766',
            activo=True,
        )
        self.curso_a = Curso.objects.create(
            nombre='Curso A drip',
            cliente=self.org,
            activo=True,
            dias_espera_entre_modulos=7,
        )
        self.curso_b = Curso.objects.create(
            nombre='Curso B pasos',
            cliente=self.org,
            activo=True,
            dias_espera_entre_modulos=0,
        )
        self.ma1 = Modulo.objects.create(
            curso=self.curso_a, numero=1, titulo='A1', contenido='a1', duracion_dias=7,
        )
        self.ma2 = Modulo.objects.create(
            curso=self.curso_a, numero=2, titulo='A2', contenido='a2', duracion_dias=7,
        )
        self.mb1 = Modulo.objects.create(
            curso=self.curso_b, numero=1, titulo='B1', contenido='b1',
            modo_entrega=Modulo.MODO_ENTREGA_PASOS, duracion_dias=7,
        )
        self.est = Estudiante.objects.create(
            cedula='99887766',
            nombre='Multi Hijack',
            telefono='5730077665544',
            cliente=self.org,
        )
        self.prog_a = ProgresoEstudiante.objects.create(
            estudiante=self.est,
            curso=self.curso_a,
            modulo_actual=self.ma1,
            fecha_ultimo_avance=timezone.now() - timedelta(hours=1),
        )
        from core.models import ModuloCompletado
        ModuloCompletado.objects.create(progreso=self.prog_a, modulo=self.ma1)
        self.prog_a.modulo_actual = self.ma2
        self.prog_a.save(update_fields=['modulo_actual'])

        self.prog_b = ProgresoEstudiante.objects.create(
            estudiante=self.est,
            curso=self.curso_b,
            modulo_actual=self.mb1,
        )

    def test_listo_muestra_menu_si_hay_curso_libre(self):
        from core.models import PasoModulo
        from core.response_templates import get_response_for_intent

        s1 = _seccion(self.mb1, 1)
        PasoModulo.objects.create(
            modulo=self.mb1,
            seccion=s1,
            orden=1,
            titulo='Micro B',
            tipo=PasoModulo.TIPO_CONTENIDO,
            contenido='Material curso B',
        )
        r = get_response_for_intent(
            'continuar_leccion',
            self.est.nombre,
            estudiante_id=self.est.id,
            mensaje_original='listo',
        )
        low = (r or '').lower()
        self.assertNotIn('próxima lección se desbloquea', low)
        self.assertTrue(
            'varios cursos' in low or 'material curso b' in low or 'curso b' in low,
            msg=r[:400],
        )
