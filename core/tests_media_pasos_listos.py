"""
Contrato: video ya apto para WhatsApp no puede quedar escondido (inactivo).

Causa Innovación (curso 52): MP4 wa_safe + media_wa_apto=True, pero activo=False.
pasos_activos_qs no los entrega → el estudiante no recibe [MEDIA:] y Twilio
no registra 63019/63021 porque el video nunca salió.
"""
from types import SimpleNamespace

from django.test import TestCase

from core.course_engine.adjuntar_pasos import adjuntar_assets_ce_a_modulo
from core.media_pasos_listos import (
    activar_pasos_video_wa_listos,
    aplicar_resultado_encode_a_paso,
    contar_videos_wa_listos_inactivos,
)
from core.models import (
    Cliente,
    Curso,
    Estudiante,
    Modulo,
    PasoModulo,
    ProgresoEstudiante,
    SeccionModulo,
)
from core.modulo_publicacion import (
    evaluar_checklist_publicacion_detalle,
    listar_problemas_media_modulo,
    publicar_modulo_wa,
)
from core.module_steps import entregar_bloque_secciones_desde_paso, reset_progreso_pasos_modulo


VIDEO_LISTO = 'https://eki-produccion.s3.us-east-2.amazonaws.com/modulos/pasos/wa_safe/clip.mp4'


class _Base(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(nombre='QA Innovación', activo=True)
        self.curso = Curso.objects.create(
            nombre='Innovación e ia',
            cliente=self.cliente,
            activo=True,
            descripcion='d',
        )
        self.mod = Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='M1',
            descripcion='d',
            contenido='',
            modo_entrega=Modulo.MODO_ENTREGA_PASOS,
            publicado_wa=False,
        )
        self.sec = SeccionModulo.objects.create(
            modulo=self.mod, orden=1, titulo='Bloque videos', activa=True,
        )
        self.est = Estudiante.objects.create(
            cedula='52000001', nombre='Est Innov', telefono='573001110052',
        )
        self.prog = ProgresoEstudiante.objects.create(
            estudiante=self.est, curso=self.curso, modulo_actual=self.mod,
        )


class EntregaOmiteVideoInactivoTests(_Base):
    def test_texto_activo_y_video_listo_inactivo_no_manda_media(self):
        PasoModulo.objects.create(
            modulo=self.mod,
            seccion=self.sec,
            orden=1,
            titulo='Texto vivo',
            contenido='Leé esto',
            activo=True,
        )
        PasoModulo.objects.create(
            modulo=self.mod,
            seccion=self.sec,
            orden=2,
            titulo='Video escondido',
            contenido='',
            media_url=VIDEO_LISTO,
            media_wa_apto=True,
            activo=False,
        )
        reset_progreso_pasos_modulo(self.prog, save=True)
        msg = entregar_bloque_secciones_desde_paso(self.prog, self.mod, 1)
        self.assertIn('Leé esto', msg)
        self.assertNotIn('[MEDIA:', msg)
        self.assertEqual(contar_videos_wa_listos_inactivos(self.mod), 1)


class ChecklistBloqueaVideoInactivoTests(_Base):
    def test_checklist_alerta_video_inactivo_y_publicar_lo_activa(self):
        PasoModulo.objects.create(
            modulo=self.mod,
            seccion=self.sec,
            orden=1,
            titulo='Texto',
            contenido='micro',
            activo=True,
        )
        PasoModulo.objects.create(
            modulo=self.mod,
            seccion=self.sec,
            orden=2,
            titulo='Video',
            contenido='',
            media_url=VIDEO_LISTO,
            media_wa_apto=True,
            activo=False,
        )
        chk = evaluar_checklist_publicacion_detalle(self.mod)
        self.assertFalse(chk.ok, chk.errores)
        self.assertTrue(
            any('inactiv' in e.lower() for e in chk.errores),
            chk.errores,
        )
        ok, errs = publicar_modulo_wa(self.mod)
        self.assertTrue(ok, errs)
        self.mod.refresh_from_db()
        self.assertTrue(self.mod.publicado_wa)
        video = PasoModulo.objects.get(modulo=self.mod, titulo='Video')
        self.assertTrue(video.activo)

    def test_ce_sin_apto_no_bloquea_si_hay_micro_activo(self):
        PasoModulo.objects.create(
            modulo=self.mod,
            seccion=self.sec,
            orden=1,
            titulo='Texto',
            contenido='micro',
            activo=True,
        )
        adjuntar_assets_ce_a_modulo(
            self.mod,
            [SimpleNamespace(url='https://s3.example/ce.mp4', label='CE', tipo='video')],
            activo=False,
        )
        chk = evaluar_checklist_publicacion_detalle(self.mod)
        self.assertTrue(chk.ok, chk.errores)

    def test_problemas_media_incluye_video_inactivo_listo(self):
        PasoModulo.objects.create(
            modulo=self.mod,
            seccion=self.sec,
            orden=1,
            titulo='Video',
            contenido='',
            media_url=VIDEO_LISTO,
            media_wa_apto=True,
            activo=False,
        )
        probs = listar_problemas_media_modulo(self.mod)
        self.assertTrue(probs)
        self.assertTrue(any('inactiv' in (p.get('detalle') or '').lower() for p in probs), probs)


class ActivarVideosListosTests(_Base):
    def test_activar_y_entonces_entrega_media(self):
        PasoModulo.objects.create(
            modulo=self.mod,
            seccion=self.sec,
            orden=1,
            titulo='Video escondido',
            contenido='Mirá',
            media_url=VIDEO_LISTO,
            media_wa_apto=True,
            activo=False,
        )
        n = activar_pasos_video_wa_listos(self.mod)
        self.assertEqual(n, 1)
        paso = PasoModulo.objects.get(modulo=self.mod)
        self.assertTrue(paso.activo)
        chk = evaluar_checklist_publicacion_detalle(self.mod)
        self.assertTrue(chk.ok, chk.errores)
        reset_progreso_pasos_modulo(self.prog, save=True)
        msg = entregar_bloque_secciones_desde_paso(self.prog, self.mod, 1)
        self.assertIn(f'[MEDIA:{VIDEO_LISTO}]', msg)

    def test_no_activa_png_ni_video_no_apto(self):
        PasoModulo.objects.create(
            modulo=self.mod,
            seccion=self.sec,
            orden=1,
            titulo='PNG',
            media_url='https://s3.example/a.png',
            media_wa_apto=True,
            activo=False,
        )
        PasoModulo.objects.create(
            modulo=self.mod,
            seccion=self.sec,
            orden=2,
            titulo='MP4 malo',
            media_url='https://s3.example/bad.mp4',
            media_wa_apto=False,
            activo=False,
        )
        self.assertEqual(activar_pasos_video_wa_listos(self.mod), 0)
        self.assertFalse(PasoModulo.objects.filter(modulo=self.mod, activo=True).exists())


class EncodeActivaPasoTests(_Base):
    def test_encode_ok_activa_paso_y_seccion(self):
        self.sec.activa = False
        self.sec.save(update_fields=['activa'])
        paso = PasoModulo.objects.create(
            modulo=self.mod,
            seccion=self.sec,
            orden=1,
            titulo='Plantilla',
            contenido='',
            activo=False,
        )
        aplicar_resultado_encode_a_paso(
            paso,
            {'url': VIDEO_LISTO, 'media_wa_apto': True, 'bytes': 12},
        )
        paso.refresh_from_db()
        self.sec.refresh_from_db()
        self.assertEqual(paso.media_url, VIDEO_LISTO)
        self.assertTrue(paso.media_wa_apto)
        self.assertTrue(paso.activo)
        self.assertTrue(self.sec.activa)

    def test_encode_no_apto_no_activa(self):
        paso = PasoModulo.objects.create(
            modulo=self.mod,
            seccion=self.sec,
            orden=1,
            titulo='Plantilla',
            activo=False,
        )
        aplicar_resultado_encode_a_paso(
            paso,
            {'url': VIDEO_LISTO, 'media_wa_apto': False, 'bytes': 12},
        )
        paso.refresh_from_db()
        self.assertFalse(paso.activo)
        self.assertFalse(paso.media_wa_apto)


class RepararCursoYAdminTests(_Base):
    def test_reparar_curso_resetea_progreso_si_no_completo(self):
        from core.media_pasos_listos import reparar_curso_videos_wa_inactivos

        PasoModulo.objects.create(
            modulo=self.mod,
            seccion=self.sec,
            orden=1,
            titulo='Video',
            media_url=VIDEO_LISTO,
            media_wa_apto=True,
            activo=False,
        )
        self.prog.paso_actual_modulo = 4
        self.prog.save(update_fields=['paso_actual_modulo'])
        stats = reparar_curso_videos_wa_inactivos(self.curso, reset_progreso=True)
        self.assertEqual(stats['pasos'], 1)
        self.prog.refresh_from_db()
        self.assertEqual(self.prog.paso_actual_modulo, 1)

    def test_ficha_modulo_boton_activar_videos(self):
        from django.contrib.auth.models import User
        from django.test import Client, override_settings
        from django.urls import reverse

        PasoModulo.objects.create(
            modulo=self.mod,
            seccion=self.sec,
            orden=1,
            titulo='Video',
            media_url=VIDEO_LISTO,
            media_wa_apto=True,
            activo=False,
        )
        user = User.objects.create_superuser('vid_staff', 'v@t.com', 'pass12345')
        client = Client()
        client.force_login(user)
        with override_settings(SECURE_SSL_REDIRECT=False):
            r = client.get(reverse('admin:core_modulo_change', args=[self.mod.pk]))
        self.assertEqual(r.status_code, 200)
        body = r.content.decode('utf-8')
        self.assertIn('Activar', body)
        self.assertIn('video', body.lower())
        url = reverse('admin:core_modulo_activar_videos_listos', args=[self.mod.pk])
        with override_settings(SECURE_SSL_REDIRECT=False):
            r2 = client.get(url)
        self.assertEqual(r2.status_code, 302)
        self.assertTrue(PasoModulo.objects.get(modulo=self.mod).activo)


class AuditVideoInactivoTests(_Base):
    def test_audit_warn_si_video_listo_inactivo(self):
        from core.media_wa_audit import auditar_media_cursos

        PasoModulo.objects.create(
            modulo=self.mod,
            seccion=self.sec,
            orden=1,
            titulo='Video escondido',
            media_url=VIDEO_LISTO,
            media_wa_apto=True,
            activo=False,
        )
        filas, resumen = auditar_media_cursos(
            curso_id=self.curso.pk, head_urls=False, solo_activos=False,
        )
        self.assertGreaterEqual(resumen.warn, 1)
        self.assertTrue(
            any('inactiv' in (f.motivo or '').lower() for f in filas),
            [(f.motivo, f.nivel) for f in filas],
        )


class SubidaStaffActivaPasoTests(_Base):
    def test_clase_url_sin_checkbox_activa(self):
        from core.admin.cursos import aplicar_clase_simple_desde_form

        fake = SimpleNamespace(
            instance=self.mod,
            cleaned_data={
                'clase_texto': 'Mirá',
                'clase_url': VIDEO_LISTO,
                'clase_activo': False,
                'titulo': 'M1',
            },
            changed_data=['clase_url', 'clase_texto'],
            _clase_pending_media_url=None,
            _clase_pending_media_wa_apto=True,
        )
        paso = aplicar_clase_simple_desde_form(fake)
        self.assertIsNotNone(paso)
        paso.refresh_from_db()
        self.assertTrue(paso.activo)
        self.assertEqual(paso.media_url, VIDEO_LISTO)

    def test_formset_subida_sin_checkbox_activa(self):
        from django.forms import inlineformset_factory

        from core.admin.cursos import PasoModuloForm, PasoModuloInlineFormSet

        png = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
            b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00'
            b'\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        p = 'pasos'
        data = {
            f'{p}-TOTAL_FORMS': '1',
            f'{p}-INITIAL_FORMS': '1',
            f'{p}-MIN_NUM_FORMS': '0',
            f'{p}-MAX_NUM_FORMS': '1000',
            f'{p}-0-id': str(
                PasoModulo.objects.create(
                    modulo=self.mod,
                    seccion=self.sec,
                    orden=1,
                    titulo='Plantilla',
                    contenido='',
                    activo=False,
                ).pk
            ),
            f'{p}-0-modulo': str(self.mod.pk),
            f'{p}-0-seccion': str(self.sec.pk),
            f'{p}-0-orden': '1',
            f'{p}-0-titulo': 'Plantilla',
            f'{p}-0-tipo': PasoModulo.TIPO_CONTENIDO,
            f'{p}-0-contenido': '',
            f'{p}-0-media_url': '',
        }
        from django.core.files.uploadedfile import SimpleUploadedFile

        files = {
            f'{p}-0-media_file_upload': SimpleUploadedFile(
                'clip.png', png, content_type='image/png',
            ),
        }
        FormSet = inlineformset_factory(
            Modulo,
            PasoModulo,
            form=PasoModuloForm,
            formset=PasoModuloInlineFormSet,
            extra=0,
            can_delete=True,
            fk_name='modulo',
        )
        fs = FormSet(data, files, instance=self.mod, prefix=p)
        self.assertTrue(fs.is_valid(), list(fs.non_form_errors()) + [dict(f.errors) for f in fs.forms])
        objs = fs.save()
        self.assertEqual(len(objs), 1)
        self.assertTrue(objs[0].activo, 'subir archivo debe dejar el paso activo')
        self.assertTrue((objs[0].media_url or '').strip())

    def test_guardar_sin_checkbox_no_apaga_video_ya_activo(self):
        from django.forms import inlineformset_factory

        from core.admin.cursos import PasoModuloForm, PasoModuloInlineFormSet

        paso = PasoModulo.objects.create(
            modulo=self.mod,
            seccion=self.sec,
            orden=1,
            titulo='Video',
            contenido='',
            media_url=VIDEO_LISTO,
            media_wa_apto=True,
            activo=True,
        )
        p = 'pasos'
        data = {
            f'{p}-TOTAL_FORMS': '1',
            f'{p}-INITIAL_FORMS': '1',
            f'{p}-MIN_NUM_FORMS': '0',
            f'{p}-MAX_NUM_FORMS': '1000',
            f'{p}-0-id': str(paso.pk),
            f'{p}-0-modulo': str(self.mod.pk),
            f'{p}-0-seccion': str(self.sec.pk),
            f'{p}-0-orden': '1',
            f'{p}-0-titulo': 'Video',
            f'{p}-0-tipo': PasoModulo.TIPO_CONTENIDO,
            f'{p}-0-contenido': '',
            f'{p}-0-media_url': VIDEO_LISTO,
        }
        FormSet = inlineformset_factory(
            Modulo,
            PasoModulo,
            form=PasoModuloForm,
            formset=PasoModuloInlineFormSet,
            extra=0,
            can_delete=True,
            fk_name='modulo',
        )
        fs = FormSet(data, instance=self.mod, prefix=p)
        self.assertTrue(fs.is_valid(), list(fs.non_form_errors()) + [dict(f.errors) for f in fs.forms])
        fs.save()
        paso.refresh_from_db()
        self.assertTrue(paso.activo)

    def test_entrega_omite_media_si_encode_pendiente(self):
        from django.core.cache import cache

        from core.media_encode_async import media_encode_paso_key

        paso = PasoModulo.objects.create(
            modulo=self.mod,
            seccion=self.sec,
            orden=1,
            titulo='Video',
            contenido='clip',
            media_url='https://s3.example/incoming/x.mp4',
            media_wa_apto=None,
            activo=True,
        )
        reset_progreso_pasos_modulo(self.prog, save=True)
        cache.set(
            media_encode_paso_key(paso.pk),
            {'status': 'pending', 'paso_id': paso.pk},
            60,
        )
        try:
            msg = entregar_bloque_secciones_desde_paso(self.prog, self.mod, 1)
            self.assertIn('clip', msg)
            self.assertNotIn('[MEDIA:', msg)
        finally:
            cache.delete(media_encode_paso_key(paso.pk))
