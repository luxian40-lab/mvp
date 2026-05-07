"""Tests: pasos internos por módulo (entrega progresiva)."""
from django.test import TestCase

from core.models import (
    Curso,
    Estudiante,
    Modulo,
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
        self.assertIn('Paso uno', msg)
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
        bloques = [p for p in msg.replace('[MULTI_MSG]', '', 1).split('[SEP]') if p.strip()]
        solos_adjuntos = [b for b in bloques if b.strip().startswith('[MEDIA:')]
        self.assertEqual(
            len(solos_adjuntos),
            0,
            'El adjunto no debe ir en un mensaje Twilio sin texto propio',
        )

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
        self.assertIn('No es correcto', out)

        out2 = procesar_respuesta_evaluacion_paso(self.est, self.prog, 'b')
        self.assertIsNotNone(out2)
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
        ProgresoEstudiante.objects.create(
            estudiante=self.est,
            curso=self.curso,
            modulo_actual=self.m1,
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
        self.assertIn('Micro paso', r)
        self.assertIn('[MULTI_MSG]', r)


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
        self.assertIn('Solo paso auto', r)

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

    def test_dos_secciones_titulos_k2(self):
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
        msg = entregar_bloque_secciones_desde_paso(self.prog, self.mod, 1)
        self.assertIn('Bloque Alfa', msg)
        self.assertIn('Bloque Beta', msg)
        self.assertIn('uno', msg)
        self.assertIn('dos', msg)
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
