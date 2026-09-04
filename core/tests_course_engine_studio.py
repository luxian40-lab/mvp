# -*- coding: utf-8 -*-
"""Tests Course Engine Studio (admin por curso)."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.course_engine.voice_config import DEFAULT_VOICES
from core.models import Curso, DocumentoRAG, Modulo

User = get_user_model()


class CourseEngineStudioViewTests(TestCase):
    def setUp(self):
        self.curso = Curso.objects.create(nombre='CE Studio Curso')
        self.mod = Modulo.objects.create(
            curso=self.curso, numero=1, titulo='M1', descripcion='d', contenido='c',
        )
        self.staff = User.objects.create_user(
            username='ce_studio_staff', password='x', is_staff=True, is_superuser=True,
        )
        self.client = Client()

    @override_settings(SECURE_SSL_REDIRECT=False)
    def test_studio_url_resolves(self):
        url = reverse('admin_course_engine_studio', kwargs={'curso_id': self.curso.pk})
        self.assertEqual(url, f'/admin/curso/{self.curso.pk}/course-engine/')

    @override_settings(SECURE_SSL_REDIRECT=False)
    def test_get_studio_ok(self):
        self.client.force_login(self.staff)
        url = reverse('admin_course_engine_studio', kwargs={'curso_id': self.curso.pk})
        r = self.client.get(url, secure=True)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Sube tus documentos')
        self.assertContains(r, 'Suelta tus archivos aquí')
        self.assertContains(r, 'Genera el demo')
        self.assertContains(r, 'Generar demo')
        self.assertContains(r, 'Sofia')
        self.assertContains(r, 'ce-wa-audio')

    @override_settings(EKI_MODULE_BUILDER_BETA=True, SECURE_SSL_REDIRECT=False)
    def test_module_builder_includes_studio_link(self):
        self.client.force_login(self.staff)
        r = self.client.get(
            reverse('admin_module_builder', kwargs={'modulo_id': self.mod.pk}),
            secure=True,
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Course Engine Studio')

    @override_settings(SECURE_SSL_REDIRECT=False)
    def test_docs_poll_json(self):
        self.client.force_login(self.staff)
        url = reverse('admin_course_engine_studio', kwargs={'curso_id': self.curso.pk})
        r = self.client.get(url + '?docs=1', secure=True)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['documentos'], [])

    @override_settings(SECURE_SSL_REDIRECT=False)
    def test_demo_voice_unauth_returns_json_not_html(self):
        """Sin sesión, demo_voice no debe devolver HTML login (rompe r.json() en el studio)."""
        url = reverse('admin_course_engine_studio', kwargs={'curso_id': self.curso.pk})
        vid = DEFAULT_VOICES[0]['id']
        r = self.client.get(
            url + f'?demo_voice={vid}&generate=1',
            secure=True,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            HTTP_ACCEPT='application/json',
        )
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r['Content-Type'].split(';')[0], 'application/json')
        data = r.json()
        self.assertFalse(data.get('ok', True))
        self.assertIn('Sesión', data.get('error', ''))

    @override_settings(SECURE_SSL_REDIRECT=False)
    def test_set_voice(self):
        self.client.force_login(self.staff)
        url = reverse('admin_course_engine_studio', kwargs={'curso_id': self.curso.pk})
        vid = DEFAULT_VOICES[0]['id']
        r = self.client.post(url, {'action': 'set_voice', 'voice_id': vid}, secure=True)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data['ok'])
        self.curso.refresh_from_db()
        self.assertEqual(self.curso.course_engine_voice_id, vid)

    @override_settings(SECURE_SSL_REDIRECT=False)
    @patch('portal.rag_curso_service.encolar_indexacion_rag_curso')
    def test_reindex_doc(self, mock_encolar):
        doc = DocumentoRAG.objects.create(
            curso=self.curso,
            nombre='manual_test',
            tipo='contenido',
            estado='error',
        )
        self.client.force_login(self.staff)
        url = reverse('admin_course_engine_studio', kwargs={'curso_id': self.curso.pk})
        r = self.client.post(url, {'action': 'reindex', 'doc_id': doc.pk}, secure=True)
        self.assertEqual(r.status_code, 200)
        doc.refresh_from_db()
        self.assertEqual(doc.estado, 'pendiente')
        mock_encolar.assert_called_once_with(doc.pk)


@override_settings(SECURE_SSL_REDIRECT=False)
class CourseEngineVoiceDemosTests(TestCase):
    @patch('core.course_engine.voice_demos.finders.find', return_value='/static/course_engine/voices/sofia.mp3')
    @patch('core.course_engine.voice_demos.static', return_value='/static/course_engine/voices/sofia.mp3')
    def test_url_demo_static(self, mock_static, mock_find):
        from core.course_engine.voice_demos import url_demo_voz

        out = url_demo_voz(DEFAULT_VOICES[0]['id'])
        self.assertTrue(out['ok'])
        self.assertTrue(out['cached'])
        self.assertIn('sofia.mp3', out['url'])

    def test_catalogo_voces_demo_count(self):
        from core.course_engine.voice_demos import catalogo_voces_demo

        rows = catalogo_voces_demo()
        self.assertEqual(len(rows), 4)


class VoiceCatalogIdentityTests(TestCase):
    """El label/genero del catalogo debe corresponder a la voz real de ElevenLabs.

    Verificado con `python manage.py course_engine_verificar_voces`. Si alguien
    reordena o cambia un id sin re-verificar, este test falla.
    """

    IDENTIDAD_REAL = {
        'b2htR0pMe28pYwCY9gnP': ('Sofia', 'F'),
        'Mf0RJxPVoxXD0xzgV88r': ('Gisela', 'F'),
        'Wb1wmVQjMx9g2QSIOTPI': ('Juan Esteban', 'M'),
        'Ux2YbCNfurnKHnzlBHGX': ('Leo', 'M'),
    }

    def test_labels_y_genero_coinciden_con_voz_real(self):
        for v in DEFAULT_VOICES:
            esperado = self.IDENTIDAD_REAL.get(v['id'])
            self.assertIsNotNone(esperado, f"Voice ID sin verificar: {v['id']}")
            label, genero = esperado
            self.assertEqual(
                v['label'], label,
                f"{v['id']} es «{label}» en ElevenLabs, no «{v['label']}»",
            )
            self.assertEqual(
                v['genero'], genero,
                f"{label} es {genero}, catalogo dice {v['genero']}",
            )

    def test_catalogo_dos_mujeres_dos_hombres(self):
        generos = [v['genero'] for v in DEFAULT_VOICES]
        self.assertEqual(generos.count('F'), 2)
        self.assertEqual(generos.count('M'), 2)

    def test_slugs_demo_unicos(self):
        from core.course_engine.voice_demos import demo_slug_for_voice_id

        slugs = [demo_slug_for_voice_id(v['id']) for v in DEFAULT_VOICES]
        self.assertEqual(len(slugs), len(set(slugs)), f'Slugs duplicados: {slugs}')

    def test_catalogo_manda_sobre_label_guardada(self):
        """Una etiqueta vieja guardada no debe seguir nombrando mal una voz del catálogo."""
        from core.course_engine.voice_config import voice_label_efectivo

        # Wb1wmVQjMx9g2QSIOTPI es Juan Esteban (hombre); antes se guardaba como "Maria".
        self.assertIn(
            'Juan Esteban',
            voice_label_efectivo('Wb1wmVQjMx9g2QSIOTPI', 'Maria (mujer)'),
        )

    def test_clon_fuera_de_catalogo_conserva_label(self):
        from core.course_engine.voice_config import voice_label_efectivo

        self.assertEqual(
            voice_label_efectivo('clon_cliente_xyz', 'Voz Doña Rosa'),
            'Voz Doña Rosa',
        )


def _plan_minimo():
    from core.course_engine.video_storyboard import SegmentoStoryboard, VideoLeccionPlan

    return VideoLeccionPlan(
        titulo='Demo',
        objetivo='Registrar ingresos y gastos del mes',
        segmentos=[
            SegmentoStoryboard(1, 'escena', 4.0, 'Guion uno.', 'Guion uno.'),
        ],
        guion_completo='Guion uno.',
    )


class VideoUsaVozDelCursoTests(TestCase):
    """La voz elegida en el Studio debe usarse aunque no se elija módulo."""

    def setUp(self):
        self.voz_curso = DEFAULT_VOICES[1]['id']  # Gisela
        self.curso = Curso.objects.create(
            nombre='Curso con voz',
            course_engine_voice_id=self.voz_curso,
        )

    def _generar_capturando_voz(self, **kwargs):
        vistos = []

        def fake_tts(texto, dest, **kw):
            vistos.append(kw.get('voice'))
            return None  # corta el pipeline tras el TTS

        with patch(
            'core.course_engine.video_pilot_generator.generar_narracion_archivo',
            side_effect=fake_tts,
        ), patch(
            'core.course_engine.video_pilot_generator.obtener_contexto_rag_empresa',
            return_value=('', False),
        ), patch(
            'core.course_engine.video_pilot_generator.resumen_documentos_curso',
            return_value='',
        ), patch(
            'core.course_engine.video_pilot_generator.planificar_video_leccion',
            return_value=_plan_minimo(),
        ):
            from core.course_engine.video_pilot_generator import VideoPilotGenerator

            VideoPilotGenerator().generar(
                cliente_id=0,
                curso_id=self.curso.pk,
                brief='Brief suficientemente largo para pasar la validacion minima.',
                **kwargs,
            )
        return vistos

    @override_settings(ELEVENLABS_VOICE_ID='voz_default_entorno')
    def test_sin_modulo_usa_voz_del_curso(self):
        vistos = self._generar_capturando_voz(modulo_id=None)
        self.assertTrue(vistos, 'No se llamó al TTS')
        self.assertEqual(vistos[0], self.voz_curso)
        self.assertNotEqual(vistos[0], 'voz_default_entorno')

    @override_settings(ELEVENLABS_VOICE_ID='voz_default_entorno')
    def test_voice_id_explicito_gana(self):
        otra = DEFAULT_VOICES[3]['id']  # Leo
        vistos = self._generar_capturando_voz(modulo_id=None, voice_id=otra)
        self.assertEqual(vistos[0], otra)

    @override_settings(ELEVENLABS_VOICE_ID='voz_default_entorno')
    def test_modulo_hereda_voz_del_curso(self):
        mod = Modulo.objects.create(
            curso=self.curso, numero=1, titulo='M1', descripcion='d', contenido='c',
        )
        vistos = self._generar_capturando_voz(modulo_id=mod.pk)
        self.assertEqual(vistos[0], self.voz_curso)
