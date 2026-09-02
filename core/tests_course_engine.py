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
