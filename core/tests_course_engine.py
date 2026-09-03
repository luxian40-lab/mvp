# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from core.course_engine.storyboard import generar_storyboard
from core.course_engine.tts import generar_narracion
from core.course_engine.types import LessonAnalysis, LessonDraft, SceneType


@override_settings(
    ELEVENLABS_API_KEY='test-el',
    ELEVENLABS_VOICE_ID='voice123',
    COURSE_ENGINE_TTS_PROVIDER='elevenlabs',
    COURSE_ENGINE_TTS_FALLBACK_OPENAI=False,
)
class ElevenLabsTtsTests(SimpleTestCase):
    def test_genera_y_sube_via_elevenlabs(self):
        fake_url = 'https://eki-produccion.s3.us-east-2.amazonaws.com/media/course_engine/tts/abc.mp3'
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b'\xff\xfb' + b'0' * 50
        mock_resp.raise_for_status = MagicMock()

        with patch('httpx.post', return_value=mock_resp) as post:
            with patch('core.course_engine.tts._subir_bytes_s3', return_value=fake_url):
                result = generar_narracion('Hola campo')

        self.assertIsNotNone(result)
        self.assertEqual(result.provider, 'elevenlabs')
        self.assertEqual(result.voice, 'voice123')
        post.assert_called_once()
        self.assertIn('voice123', post.call_args[0][0])

    def test_sin_api_key_retorna_none(self):
        with self.settings(ELEVENLABS_API_KEY=''):
            self.assertIsNone(generar_narracion('hola'))


@override_settings(OPENAI_API_KEY='test-key')
class StoryboardTests(SimpleTestCase):
    def test_genera_escenas_desde_openai(self):
        lesson = LessonDraft(titulo='Riego', contenido='...', puntos_clave=['a'])
        analysis = LessonAnalysis(
            audiencia='Agricultores',
            duracion_estimada_min=3,
            conceptos=['riego'],
            riesgos_pedagogicos=[],
            recomendacion_formato='mixto',
        )
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content=(
                            '{"titulo_leccion":"Riego","objetivo":"Aprender","escenas":'
                            '[{"orden":1,"tipo":"narracion","titulo":"Intro","guion":"Hola",'
                            '"duracion_seg":5,"notas_visuales":""}]}'
                        )
                    )
                )
            ]
        )

        sb = generar_storyboard(lesson, analysis, openai_client=mock_client)

        self.assertIsNotNone(sb)
        self.assertEqual(len(sb.escenas), 1)
        self.assertEqual(sb.escenas[0].tipo, SceneType.NARRACION)


class CourseEngineWaGateTests(SimpleTestCase):
    def test_preparar_mp4_eki_wa_v1_rechaza_vacio(self):
        from core.course_engine.compose import preparar_mp4_eki_wa_v1

        out, gate = preparar_mp4_eki_wa_v1(b'')
        self.assertIsNone(out)
        self.assertFalse(gate.get('apto'))

    def test_subir_video_s3_usa_wa_safe_y_gate(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        from core.course_engine.compose import subir_video_s3

        fake_url = (
            'https://eki-produccion.s3.us-east-2.amazonaws.com/media/course_engine/'
            'videos/wa_safe/abc_h264_main_faststart.mp4'
        )
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp:
            tmp.write(b'\x00' * 128)
            path = Path(tmp.name)

        gate_ok = {'apto': True, 'bytes': 128, 'razon': 'ok'}
        with patch(
            'core.course_engine.compose.preparar_mp4_eki_wa_v1',
            return_value=(b'wa_ready', gate_ok),
        ):
            with patch('core.twilio_media._subir_bytes_s3', return_value=fake_url) as up:
                url = subir_video_s3(path, 'abc12')

        self.assertEqual(url, fake_url)
        key = up.call_args[0][0]
        self.assertIn('wa_safe', key)
        self.assertIn('h264_main_faststart', key)
        path.unlink(missing_ok=True)


class BriefVisualTests(SimpleTestCase):
    def test_inferir_categoria_finanzas(self):
        from core.course_engine.visual_style import inferir_categoria_visual, prompt_keyframe_documental

        texto = 'Manual de Gestión Financiera y Rentabilidad Empresarial'
        self.assertEqual(inferir_categoria_visual(texto), 'finanzas')
        prompt = prompt_keyframe_documental(tema=texto)
        self.assertIn('cuaderno', prompt.lower())

    def test_escena_visual_override_sin_campo(self):
        from core.course_engine.visual_style import prompt_keyframe_documental

        escena = 'Dos socios revisando estados financieros en una mesa de finca'
        prompt = prompt_keyframe_documental(escena_visual=escena)
        self.assertIn('estados financieros', prompt)
        self.assertNotIn('cosecha', prompt.lower())

    @patch('openai.OpenAI')
    def test_planificar_clip_micro_json(self, mock_openai_cls):
        from core.course_engine.brief_visual import planificar_clip_micro

        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content=(
                            '{"titulo_corto":"Rentabilidad empresarial",'
                            '"guion_narracion":"Mida su rentabilidad: relacione ganancia e inversión. '
                            'Sin reportes entre socios, el flujo enmascara problemas.",'
                            '"escena_visual":"Emprendedores rurales en mesa con cuaderno de gastos y calculadora",'
                            '"categoria_visual":"finanzas"}'
                        )
                    )
                )
            ]
        )
        plan = planificar_clip_micro('Manual de rentabilidad y costos', target_sec=15, openai_client=mock_client)
        self.assertEqual(plan.categoria_visual, 'finanzas')
        self.assertIn('rentabilidad', plan.guion_narracion.lower())
        self.assertIn('cuaderno', plan.escena_visual.lower())


@override_settings(OPENAI_API_KEY='test-key')
class InteractiveSequenceTests(SimpleTestCase):
    def test_genera_bloques_alternados(self):
        from core.course_engine.interactive_sequence import generar_secuencia_interactiva

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content=(
                            '{"titulo_leccion":"6 errores de rentabilidad","objetivo":"Evitar pérdidas",'
                            '"bloques":['
                            '{"orden":1,"tipo":"texto","titulo":"Gancho","guion":"¿Sabías que el 60% pierde rentabilidad?",'
                            '"escena_visual":"","duracion_seg":0},'
                            '{"orden":2,"tipo":"micro_video","titulo":"Error 1","guion":"No medir costos fijos.",'
                            '"escena_visual":"Cuaderno de gastos en mesa rural","duracion_seg":10},'
                            '{"orden":3,"tipo":"texto","titulo":"Error 2","guion":"Mezclar gastos personales y del negocio.",'
                            '"escena_visual":"","duracion_seg":0},'
                            '{"orden":4,"tipo":"resumen","titulo":"Cierre","guion":"Escribe listo para continuar.",'
                            '"escena_visual":"","duracion_seg":0}'
                            ']}'
                        )
                    )
                )
            ]
        )

        brief = 'Manual: 6 errores que destruyen la rentabilidad empresarial'
        seq = generar_secuencia_interactiva(brief, 'Contexto RAG finanzas', openai_client=mock_client)

        self.assertIsNotNone(seq)
        self.assertTrue(seq.rag_usado)
        self.assertEqual(len(seq.bloques), 4)
        self.assertEqual(seq.bloques[0].tipo, 'texto')
        self.assertEqual(seq.bloques[1].tipo, 'micro_video')
        self.assertEqual(seq.bloques[1].duracion_seg, 10.0)

    def test_respeta_max_micro_videos(self):
        from core.course_engine.interactive_sequence import generar_secuencia_interactiva

        bloques = []
        for i in range(1, 6):
            bloques.append(
                f'{{"orden":{i},"tipo":"micro_video","titulo":"E{i}","guion":"Narración {i}",'
                f'"escena_visual":"Escena {i}","duracion_seg":8}}'
            )
        payload = (
            '{"titulo_leccion":"Test","objetivo":"O",'
            f'"bloques":[{",".join(bloques)}]}}'
        )
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=payload))]
        )

        seq = generar_secuencia_interactiva('brief', openai_client=mock_client, max_micro_videos=2)
        self.assertEqual(sum(1 for b in seq.bloques if b.tipo == 'micro_video'), 2)

    @patch('core.course_engine.interactive_generator.generar_secuencia_interactiva')
    @patch('core.course_engine.interactive_generator.obtener_contexto_rag_empresa')
    def test_dry_run_manifest_sin_runway(self, mock_rag, mock_seq):
        from core.course_engine.interactive_generator import InteractiveSequenceGenerator
        from core.course_engine.interactive_sequence import BloqueInteractivo, SecuenciaInteractiva

        mock_rag.return_value = ('ctx rag', True)
        mock_seq.return_value = SecuenciaInteractiva(
            titulo_leccion='Rentabilidad',
            objetivo='Evitar errores',
            bloques=[
                BloqueInteractivo(1, 'texto', 'Intro', 'Hola productor'),
                BloqueInteractivo(2, 'micro_video', 'Error 1', 'No medir costos', 'Cuaderno', 10),
            ],
            rag_usado=True,
        )

        gen = InteractiveSequenceGenerator()
        out = gen.generar(
            cliente_id=1,
            curso_id=2,
            brief='Manual rentabilidad',
            dry_run=True,
        )

        self.assertEqual(len(out.pasos_wa), 2)
        self.assertEqual(out.pasos_wa[0].tipo, 'texto')
        self.assertEqual(out.pasos_wa[1].tipo, 'texto')
        self.assertIn('pendiente', out.pasos_wa[1].titulo.lower())
        self.assertFalse(out.pasos_wa[1].media_url)
        self.assertTrue(out.manifest_path and out.manifest_path.is_file())

    @patch('core.course_engine.interactive_generator.generar_video_desde_imagen')
    @patch('core.course_engine.interactive_generator.generar_secuencia_interactiva')
    @patch('core.course_engine.interactive_generator.obtener_contexto_rag_empresa')
    def test_sin_generate_videos_no_llama_runway(self, mock_rag, mock_seq, mock_runway):
        from core.course_engine.interactive_generator import InteractiveSequenceGenerator
        from core.course_engine.interactive_sequence import BloqueInteractivo, SecuenciaInteractiva

        mock_rag.return_value = ('', False)
        mock_seq.return_value = SecuenciaInteractiva(
            titulo_leccion='Test',
            objetivo='O',
            bloques=[
                BloqueInteractivo(1, 'micro_video', 'Clip', 'Narración', 'Escena', 8),
            ],
        )

        gen = InteractiveSequenceGenerator()
        out = gen.generar(
            cliente_id=1,
            curso_id=2,
            brief='brief',
            dry_run=False,
            generar_micro_videos=0,
        )

        mock_runway.assert_not_called()
        self.assertEqual(out.costo_real_usd, 0.0)
        self.assertEqual(len(out.pasos_wa), 1)


class PlatziFormatTests(SimpleTestCase):
    def test_formatea_resumen_y_definicion(self):
        from core.course_engine.interactive_sequence import BloqueInteractivo
        from core.course_engine.platzi_format import formatear_paso_whatsapp

        resumen = BloqueInteractivo(1, 'resumen', '', 'Aprenderás los 6 errores de rentabilidad.')
        txt = formatear_paso_whatsapp(resumen, titulo_leccion='Rentabilidad rural')
        self.assertIn('Resumen', txt)
        self.assertIn('Rentabilidad rural', txt)

        defn = BloqueInteractivo(2, 'definicion', 'Rentabilidad', 'Relación ganancia / inversión.')
        txt2 = formatear_paso_whatsapp(defn)
        self.assertIn('Rentabilidad', txt2)
        self.assertIn('Relación ganancia', txt2)

    def test_formatea_seccion_pregunta(self):
        from core.course_engine.interactive_sequence import BloqueInteractivo
        from core.course_engine.platzi_format import formatear_paso_whatsapp

        b = BloqueInteractivo(1, 'seccion', '¿Qué es la rentabilidad?', 'Veamos el concepto clave.')
        self.assertIn('¿Qué es la rentabilidad?', formatear_paso_whatsapp(b))


@override_settings(OPENAI_API_KEY='test-key')
class VideoStoryboardTests(SimpleTestCase):
    def test_fallback_error1_tiene_tarjeta(self):
        from core.course_engine.video_storyboard import _fallback_error1

        plan = _fallback_error1()
        self.assertTrue(any(s.tipo == 'tarjeta' for s in plan.segmentos))
        self.assertIn('socios', plan.guion_completo.lower())

    def test_reparte_duracion_audio(self):
        from core.course_engine.video_storyboard import (
            SegmentoStoryboard,
            VideoLeccionPlan,
            repartir_duracion_por_audio,
        )

        plan = VideoLeccionPlan(
            titulo='Test',
            objetivo='O',
            segmentos=[
                SegmentoStoryboard(1, 'escena', 4, 'a', 'sub1'),
                SegmentoStoryboard(2, 'tarjeta', 6, 'b', 'sub2'),
                SegmentoStoryboard(3, 'escena_cierre', 4, 'c', 'sub3'),
            ],
            guion_completo='a b c',
        )
        timeline = repartir_duracion_por_audio(plan, 12.0)
        self.assertEqual(len(timeline), 3)
        total = sum(d for _, _, d in timeline)
        self.assertAlmostEqual(total, 12.0, places=1)

    def test_plan_openai_mock(self):
        from core.course_engine.video_storyboard import planificar_video_leccion

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content=(
                            '{"titulo":"Error 1","objetivo":"Transparencia","categoria_visual":"finanzas",'
                            '"duracion_objetivo_seg":14,"guion_completo":"Guion completo de prueba.",'
                            '"segmentos":['
                            '{"orden":1,"tipo":"escena","duracion_seg":4,"guion":"A","subtitulo":"Sub A",'
                            '"escena_visual":"Mesa con cuaderno"},'
                            '{"orden":2,"tipo":"tarjeta","duracion_seg":6,"guion":"B","subtitulo":"Sub B",'
                            '"tarjeta_titulo":"Título","tarjeta_puntos":["P1","P2"]},'
                            '{"orden":3,"tipo":"escena_cierre","duracion_seg":4,"guion":"C","subtitulo":"Sub C",'
                            '"escena_visual":"Cierre"}'
                            ']}'
                        )
                    )
                )
            ]
        )
        plan = planificar_video_leccion('brief finanzas', openai_client=mock_client)
        self.assertEqual(plan.titulo, 'Error 1')
        self.assertEqual(len(plan.segmentos), 3)


class InfographicCardTests(SimpleTestCase):
    def test_genera_png_con_panel(self):
        import tempfile
        from pathlib import Path

        from PIL import Image

        from core.course_engine.infographic_card import generar_tarjeta_infografica

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'tarjeta.png'
            ok = generar_tarjeta_infografica(
                titulo='Error #1: Sin cuentas claras',
                puntos=['Reporte mensual', 'Mismos números', 'Decidir con datos'],
                salida=out,
                usar_fondo_ia=False,
            )
            self.assertTrue(ok)
            self.assertGreater(out.stat().st_size, 8000)
            with Image.open(out) as img:
                self.assertEqual(img.size, (1280, 720))

    def test_beats_alineados_al_guion(self):
        from core.course_engine.tarjeta_beats import beats_desde_tarjeta

        beats = beats_desde_tarjeta(
            titulo='Error #1: Sin cuentas claras',
            puntos=[
                'Reporte mensual de ingresos y gastos',
                'Todos los socios ven los mismos números',
            ],
            guion=(
                'Compartan ingresos y gastos cada mes. '
                'Un reporte común evita sorpresas y permite decidir a tiempo.'
            ),
        )
        self.assertEqual(len(beats), 2)
        self.assertIn('Compartan ingresos', beats[0].narracion)
        self.assertIn('reporte común', beats[1].narracion.lower())
        self.assertNotEqual(beats[0].narracion, beats[1].narracion)

    def test_beats_un_beat_por_punto(self):
        from core.course_engine.tarjeta_beats import beats_desde_tarjeta

        beats = beats_desde_tarjeta(
            titulo='Margen',
            puntos=['Costos fijos', 'Precio de venta', 'Simular escenarios'],
            guion='Primero identifique costos. Luego fije precio. Finalmente simule.',
        )
        self.assertEqual(len(beats), 3)
        self.assertEqual(len(beats[-1].filas), 3)

    def test_typing_mas_lento_en_beat_largo(self):
        from core.course_engine.infographic_card import (
            _frames_para_beat,
            _typing_progress_en_beat,
            _typing_text,
        )
        from core.course_engine.tarjeta_beats import TarjetaBeat

        corto = TarjetaBeat('T', 'Hola.', '', [])
        largo = TarjetaBeat(
            'T',
            'Compartan ingresos y gastos cada mes con un reporte común.',
            'Evita sorpresas entre socios.',
            [('Reporte', 'Todos ven los mismos números')],
        )
        self.assertGreater(_frames_para_beat(largo, 15), _frames_para_beat(corto, 15))
        self.assertLess(len(_typing_text('uno dos tres cuatro', 0.3)), len('uno dos tres cuatro'))
        self.assertEqual(_typing_progress_en_beat(999, 40), 1.0)

    def test_frames_progresivos_uno_por_bullet(self):
        import tempfile
        from pathlib import Path

        from core.course_engine.infographic_card import generar_frames_tarjeta_animada

        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / 'anim'
            frames = generar_frames_tarjeta_animada(
                titulo='Error #1: Sin cuentas claras',
                puntos=['Reporte mensual de ingresos y gastos', 'Todos los socios ven los mismos números'],
                guion='Compartan ingresos y gastos cada mes. Un reporte común evita sorpresas.',
                salida_dir=d,
                estilo='platzi',
                duracion_seg=3.0,
                fps=10,
            )
            self.assertGreaterEqual(len(frames), 20)

    def test_split_vertical_resolucion_9_16(self):
        import tempfile
        from pathlib import Path

        from PIL import Image

        from core.course_engine.split_screen_ui import generar_frames_split_vertical

        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            frames = generar_frames_split_vertical(
                titulo='Error #1: mezclar gastos',
                puntos=['Separa costos fijos'],
                salida_dir=d,
                duracion_seg=2.0,
                fps=10,
            )
            self.assertGreaterEqual(len(frames), 18)
            with Image.open(frames[0]) as img:
                self.assertEqual(img.size, (1080, 1920))

    def test_platzi_frame_tiene_contenido_visible(self):
        import tempfile
        from pathlib import Path

        from PIL import Image

        from core.course_engine.infographic_card import generar_frames_tarjeta_animada

        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / 'anim'
            frames = generar_frames_tarjeta_animada(
                titulo='Error #1: mezclar gastos',
                puntos=['Gastos fijos — anótalos aparte'],
                salida_dir=d,
                estilo='platzi',
            )
            self.assertGreaterEqual(len(frames), 2)
            with Image.open(frames[-1]) as img:
                self.assertEqual(img.size, (1280, 720))
                px = img.getpixel((400, 300))
                self.assertGreater(sum(px), 200)


class ClipBuilderSubtitleTests(SimpleTestCase):
    def test_franja_legible_incluye_fondo_oscuro(self):
        from pathlib import Path

        from core.course_engine.clip_builder import _vf_subtitulos_inferior

        vf = _vf_subtitulos_inferior('scale=1280:720', Path('/tmp/test.srt'), franja_legible=True)
        self.assertIn('BackColour', vf)
        self.assertIn('FontSize=18', vf)

    def test_subtitulo_escena_mas_pequeno(self):
        from pathlib import Path

        from core.course_engine.clip_builder import _vf_subtitulos_inferior

        vf = _vf_subtitulos_inferior('scale=1280:720', Path('/tmp/test.srt'))
        self.assertIn('FontSize=20', vf)


class VideoPilotGeneratorTests(SimpleTestCase):
    @patch('core.course_engine.video_pilot_generator.obtener_contexto_rag_empresa')
    @patch('core.course_engine.video_pilot_generator.planificar_video_leccion')
    def test_dry_run_un_solo_paso_wa(self, mock_plan, mock_rag):
        from core.course_engine.video_pilot_generator import VideoPilotGenerator
        from core.course_engine.video_storyboard import SegmentoStoryboard, VideoLeccionPlan

        mock_rag.return_value = ('ctx', True)
        mock_plan.return_value = VideoLeccionPlan(
            titulo='Error 1',
            objetivo='O',
            segmentos=[
                SegmentoStoryboard(1, 'escena', 4, 'g1', 'sub1'),
                SegmentoStoryboard(2, 'tarjeta', 6, 'g2', 'sub2', tarjeta_titulo='T', tarjeta_puntos=['P']),
                SegmentoStoryboard(3, 'escena_cierre', 4, 'g3', 'sub3'),
            ],
            guion_completo='g1 g2 g3',
        )

        gen = VideoPilotGenerator()
        out = gen.generar(
            cliente_id=1,
            curso_id=22,
            brief='Manual rentabilidad',
            dry_run=True,
        )

        self.assertIsNotNone(out.paso_wa)
        self.assertEqual(out.paso_wa.orden, 1)
        self.assertFalse(out.paso_wa.media_url)
        self.assertIn('eki video', out.paso_wa.caption.lower())
        self.assertTrue(out.manifest_path and out.manifest_path.is_file())
