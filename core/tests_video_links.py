"""Enlaces cortos de video: apertura, progreso y reporte de Analítica."""
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.models import Cliente, Curso, Estudiante, Modulo, PasoModulo, ProgresoEstudiante, SeccionModulo
from core.models_video import VideoEnlace, VideoView
from core.module_steps import entregar_paso_indice, reset_progreso_pasos_modulo
from core.video_links import reescribir_videos_en_mensaje, reporte_aperturas_video


def _org():
    cliente = Cliente.objects.create(
        nombre='Org Video',
        contacto_principal='Ana',
        email='video@example.com',
        telefono='573001110000',
    )
    curso = Curso.objects.create(
        nombre='Curso video',
        descripcion='d',
        cliente=cliente,
        dias_espera_entre_modulos=0,
        usar_agentes_ia=False,
    )
    modulo = Modulo.objects.create(
        curso=curso,
        numero=1,
        titulo='Riego',
        descripcion='d',
        contenido='c',
    )
    est = Estudiante.objects.create(
        cedula='9001',
        nombre='Luz Video',
        telefono='573001110001',
        cliente=cliente,
    )
    return cliente, curso, modulo, est


@override_settings(SECURE_SSL_REDIRECT=False)
class VideoLinkTests(TestCase):
    def setUp(self):
        self.cliente, self.curso, self.modulo, self.est = _org()

    def test_flag_off_no_cambia_el_adjunto(self):
        msg = reescribir_videos_en_mensaje(
            '[MEDIA:https://cdn.example.com/a.mp4]',
            estudiante=self.est,
            curso=self.curso,
            modulo=self.modulo,
        )
        self.assertIn('[MEDIA:https://cdn.example.com/a.mp4]', msg)
        self.assertEqual(VideoEnlace.objects.count(), 0)

    @override_settings(EKI_VIDEO_SHORTLINKS=False, VIDEO_PUBLIC_BASE_URL='https://videos.eki.technology')
    def test_paso_enlace_reescribe_aunque_el_flag_este_apagado(self):
        seccion = SeccionModulo.objects.create(modulo=self.modulo, orden=1, titulo='A')
        PasoModulo.objects.create(
            modulo=self.modulo,
            seccion=seccion,
            orden=1,
            titulo='Video',
            contenido='Mira',
            media_url='https://cdn.example.com/a.mp4',
            video_entrega=PasoModulo.VIDEO_ENLACE,
        )
        msg = reescribir_videos_en_mensaje(
            '[MEDIA:https://cdn.example.com/a.mp4]',
            estudiante=self.est,
            curso=self.curso,
            modulo=self.modulo,
        )
        self.assertIn('https://videos.eki.technology/v/', msg)
        self.assertNotIn('[MEDIA:', msg)

    @override_settings(EKI_VIDEO_SHORTLINKS=True, VIDEO_PUBLIC_BASE_URL='https://videos.eki.technology')
    def test_paso_whatsapp_no_reescribe_aunque_el_flag_este_prendido(self):
        seccion = SeccionModulo.objects.create(modulo=self.modulo, orden=1, titulo='A')
        PasoModulo.objects.create(
            modulo=self.modulo,
            seccion=seccion,
            orden=1,
            titulo='Video',
            contenido='Mira',
            media_url='https://cdn.example.com/a.mp4',
            video_entrega=PasoModulo.VIDEO_WHATSAPP,
        )
        msg = reescribir_videos_en_mensaje(
            '[MEDIA:https://cdn.example.com/a.mp4]',
            estudiante=self.est,
            curso=self.curso,
            modulo=self.modulo,
        )
        self.assertIn('[MEDIA:https://cdn.example.com/a.mp4]', msg)
        self.assertEqual(VideoEnlace.objects.count(), 0)

    @override_settings(EKI_VIDEO_SHORTLINKS=True, VIDEO_PUBLIC_BASE_URL='https://videos.eki.technology')
    def test_reescribe_solo_video_y_reutiliza_token(self):
        original = (
            'Mirá esto\n\n[MEDIA:https://cdn.example.com/clase.mp4]'
            '[SEP][MEDIA:https://cdn.example.com/ficha.jpg]'
        )
        msg = reescribir_videos_en_mensaje(
            original,
            estudiante=self.est,
            curso=self.curso,
            modulo=self.modulo,
        )
        self.assertNotIn('cdn.example.com/clase.mp4', msg)
        self.assertIn('https://videos.eki.technology/v/', msg)
        self.assertIn('[MEDIA:https://cdn.example.com/ficha.jpg]', msg)
        self.assertEqual(VideoEnlace.objects.count(), 1)
        otra = reescribir_videos_en_mensaje(
            '[MEDIA:https://cdn.example.com/clase.mp4]',
            estudiante=self.est,
            curso=self.curso,
            modulo=self.modulo,
        )
        self.assertEqual(VideoEnlace.objects.count(), 1)
        self.assertIn(VideoEnlace.objects.get().token, otra)

    @override_settings(EKI_VIDEO_SHORTLINKS=True, VIDEO_PUBLIC_BASE_URL='https://videos.eki.technology')
    def test_entrega_de_paso_sustituye_media_de_video(self):
        seccion = SeccionModulo.objects.create(modulo=self.modulo, orden=1, titulo='A')
        PasoModulo.objects.create(
            modulo=self.modulo,
            seccion=seccion,
            orden=1,
            titulo='Video intro',
            tipo=PasoModulo.TIPO_CONTENIDO,
            contenido='Mirá este material',
            media_url='https://cdn.example.com/video.mp4',
            video_entrega=PasoModulo.VIDEO_ENLACE,
        )
        prog = ProgresoEstudiante.objects.create(
            estudiante=self.est,
            curso=self.curso,
            modulo_actual=self.modulo,
        )
        reset_progreso_pasos_modulo(prog, save=True)
        msg = entregar_paso_indice(prog, self.modulo, 1)
        self.assertIn('Mirá este material', msg)
        self.assertNotIn('[MEDIA:https://cdn.example.com/video.mp4]', msg)
        self.assertIn('/v/', msg)
        self.assertTrue(VideoEnlace.objects.filter(estudiante=self.est, video_id__startswith='paso:').exists())

    def test_apertura_youtube_302_guarda_user_agent(self):
        enlace = VideoEnlace.objects.create(
            token='abcDEF1234567890xyz',
            estudiante=self.est,
            curso=self.curso,
            modulo=self.modulo,
            video_id='modulo:1',
            etiqueta='M1. Riego',
            destino_tipo=VideoEnlace.DESTINO_EXTERNO,
            destino_ref='https://www.youtube.com/watch?v=dQw4w9WgXcQ',
        )
        resp = self.client.get(
            reverse('video_abrir', args=[enlace.token]),
            HTTP_USER_AGENT='Mozilla/5.0 (Android) Chrome/120',
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp['Location'], enlace.destino_ref)
        vista = VideoView.objects.get()
        self.assertEqual(vista.evento, VideoView.EVENTO_APERTURA)
        self.assertEqual(vista.estudiante_id, self.est.id)
        self.assertEqual(vista.curso_id, self.curso.id)
        self.assertEqual(vista.modulo_id, self.modulo.id)
        self.assertEqual(vista.video_id, 'modulo:1')
        self.assertIn('Chrome/120', vista.user_agent)
        self.assertNotIn('X-Amz-', str(vista.user_agent))

    def test_prefetch_no_cuenta_apertura(self):
        enlace = VideoEnlace.objects.create(
            token='prefetchTOKEN1234567',
            estudiante=self.est,
            curso=self.curso,
            modulo=self.modulo,
            video_id='modulo:1',
            destino_tipo=VideoEnlace.DESTINO_EXTERNO,
            destino_ref='https://vimeo.com/123456789',
        )
        resp = self.client.get(
            reverse('video_abrir', args=[enlace.token]),
            HTTP_USER_AGENT='facebookexternalhit/1.1',
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(VideoView.objects.count(), 0)

    def test_token_desconocido_404(self):
        resp = self.client.get('/v/no-es-un-token/')
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(VideoView.objects.count(), 0)

    def test_destino_externo_ajeno_no_redirige_ni_cuenta(self):
        enlace = VideoEnlace.objects.create(
            token='evilTOKEN1234567890a',
            estudiante=self.est,
            curso=self.curso,
            modulo=self.modulo,
            video_id='url:deadbeef',
            destino_tipo=VideoEnlace.DESTINO_EXTERNO,
            destino_ref='https://evil.example/phish',
        )
        resp = self.client.get(reverse('video_abrir', args=[enlace.token]))
        self.assertEqual(resp.status_code, 502)
        self.assertEqual(VideoView.objects.count(), 0)
        self.assertNotIn('evil.example', resp.content.decode())

    @patch('core.video_links.url_firmada_s3', return_value='https://signed.example/clase.mp4?X-Amz-Signature=abc')
    def test_s3_muestra_reproductor_y_progreso_una_vez(self, _firmada):
        enlace = VideoEnlace.objects.create(
            token='s3TOKEN1234567890abcd',
            estudiante=self.est,
            curso=self.curso,
            modulo=self.modulo,
            video_id='archivo:9',
            etiqueta='Video riego',
            destino_tipo=VideoEnlace.DESTINO_S3,
            destino_ref='media/clase.mp4',
        )
        resp = self.client.get(
            reverse('video_abrir', args=[enlace.token]),
            HTTP_USER_AGENT='Mozilla/5.0',
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn('<video', body)
        self.assertIn('https://signed.example/clase.mp4', body)
        self.assertIn('timeupdate', body)
        self.assertEqual(VideoView.objects.filter(evento=VideoView.EVENTO_APERTURA).count(), 1)
        self.assertFalse(
            VideoView.objects.filter(user_agent__icontains='X-Amz-Signature').exists()
        )

        url = reverse('video_progreso', args=[enlace.token])
        primero = self.client.post(
            url,
            data=json.dumps({'hito': 25}),
            content_type='application/json',
        )
        self.assertEqual(primero.status_code, 200)
        self.assertEqual(primero.json(), {'ok': True, 'evento': 'progreso_25', 'nuevo': True})
        segundo = self.client.post(
            url,
            data=json.dumps({'hito': 25}),
            content_type='application/json',
        )
        self.assertEqual(segundo.json()['nuevo'], False)
        self.assertEqual(VideoView.objects.filter(evento=VideoView.EVENTO_P25).count(), 1)
        malo = self.client.post(
            url,
            data=json.dumps({'hito': 10}),
            content_type='application/json',
        )
        self.assertEqual(malo.status_code, 400)
        self.assertFalse(malo.json()['ok'])

    def test_progreso_en_youtube_no_aplica(self):
        enlace = VideoEnlace.objects.create(
            token='ytTOKEN1234567890abcd',
            estudiante=self.est,
            curso=self.curso,
            modulo=self.modulo,
            video_id='modulo:1',
            destino_tipo=VideoEnlace.DESTINO_EXTERNO,
            destino_ref='https://youtu.be/abcdefghijk',
        )
        resp = self.client.post(
            reverse('video_progreso', args=[enlace.token]),
            data=json.dumps({'hito': 100}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(VideoView.objects.count(), 0)

    def test_reporte_por_curso_y_estudiante(self):
        enlace = VideoEnlace.objects.create(
            token='repTOKEN1234567890abc',
            estudiante=self.est,
            curso=self.curso,
            modulo=self.modulo,
            video_id='archivo:3',
            etiqueta='Riego por goteo',
            destino_tipo=VideoEnlace.DESTINO_S3,
            destino_ref='media/riego.mp4',
        )
        VideoView.objects.create(
            enlace=enlace,
            estudiante=self.est,
            curso=self.curso,
            modulo=self.modulo,
            video_id=enlace.video_id,
            evento=VideoView.EVENTO_APERTURA,
            user_agent='ua',
        )
        VideoView.objects.create(
            enlace=enlace,
            estudiante=self.est,
            curso=self.curso,
            modulo=self.modulo,
            video_id=enlace.video_id,
            evento=VideoView.EVENTO_APERTURA,
            user_agent='ua2',
        )
        VideoView.objects.create(
            enlace=enlace,
            estudiante=self.est,
            curso=self.curso,
            modulo=self.modulo,
            video_id=enlace.video_id,
            evento=VideoView.EVENTO_P100,
            user_agent='ua',
        )
        data = reporte_aperturas_video(curso_id=self.curso.id, cliente_id=self.cliente.id)
        self.assertEqual(data['totales']['aperturas'], 2)
        self.assertEqual(data['totales']['estudiantes'], 1)
        self.assertEqual(data['totales']['llegaron_100'], 1)
        self.assertEqual(data['por_curso'][0]['aperturas'], 2)
        self.assertEqual(data['por_curso'][0]['enlace__etiqueta'], 'Riego por goteo')
        self.assertEqual(data['por_estudiante'][0]['max_hito'], 100)
        self.assertEqual(data['por_estudiante'][0]['estudiante__nombre'], 'Luz Video')
        vacio = reporte_aperturas_video(curso_id=999999)
        self.assertEqual(vacio['totales']['aperturas'], 0)

    def test_dashboard_muestra_aperturas(self):
        user = get_user_model().objects.create_user(
            username='staff-video',
            password='test-pass-123',
            is_staff=True,
        )
        enlace = VideoEnlace.objects.create(
            token='dashTOKEN1234567890ab',
            estudiante=self.est,
            curso=self.curso,
            modulo=self.modulo,
            video_id='archivo:3',
            etiqueta='Riego por goteo',
            destino_tipo=VideoEnlace.DESTINO_ARCHIVO,
            destino_ref='https://cdn.example.com/riego.mp4',
        )
        VideoView.objects.create(
            enlace=enlace,
            estudiante=self.est,
            curso=self.curso,
            modulo=self.modulo,
            video_id=enlace.video_id,
            evento=VideoView.EVENTO_APERTURA,
        )
        client = Client()
        client.force_login(user)
        resp = client.get(reverse('dashboard_unificado') + '?tab=learning&section=videos')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Riego por goteo')
        self.assertContains(resp, 'Luz Video')
        self.assertContains(resp, 'no una reproducción confirmada')
