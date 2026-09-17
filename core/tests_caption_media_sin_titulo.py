"""El pie de foto de un adjunto no debe exponer el título interno del paso.

Caso real: los pasos del curso Agrosavia se llaman «001.mp4» o «Microcontenido 2»
(nombres de archivo del Builder) y eso llegaba al estudiante como pie de foto.
"""
from django.test import TestCase

from core.models import Curso, Modulo, PasoModulo, SeccionModulo
from core.module_steps import partes_mensaje_paso
from core.response_templates import MENSAJE_CAPTION_SOLO_MEDIA

URL_IMG = 'https://ejemplo.test/modulos/pasos/foto.jpg'


class CaptionMediaSinTituloTests(TestCase):
    def setUp(self):
        self.curso = Curso.objects.create(nombre='QA caption', descripcion='d')
        self.modulo = Modulo.objects.create(
            curso=self.curso,
            numero=1,
            titulo='Bienvenida',
            descripcion='d',
            contenido='c',
        )
        self.seccion = SeccionModulo.objects.create(
            modulo=self.modulo, orden=1, titulo='Bloque 1'
        )

    def _paso(self, titulo='', contenido=''):
        return PasoModulo.objects.create(
            modulo=self.modulo,
            seccion=self.seccion,
            orden=1,
            titulo=titulo,
            contenido=contenido,
            media_url=URL_IMG,
            tipo=PasoModulo.TIPO_CONTENIDO,
            activo=True,
        )

    def test_media_sin_texto_va_sola(self):
        """Sin texto del autor: solo el adjunto, sin título ni relleno genérico."""
        paso = self._paso(titulo='001.mp4')

        partes = partes_mensaje_paso(paso, self.curso)

        self.assertEqual(partes[0], f'[MEDIA:{URL_IMG}]')

    def test_tampoco_el_titulo_de_la_seccion_ni_del_modulo(self):
        paso = self._paso()

        bloque = partes_mensaje_paso(paso, self.curso)[0]

        self.assertNotIn('Bloque 1', bloque)
        self.assertNotIn('Bienvenida', bloque)
        self.assertNotIn(MENSAJE_CAPTION_SOLO_MEDIA, bloque)

    def test_multimedia_del_modulo_tampoco_lleva_titulo(self):
        """Los adjuntos de la pestaña Multimedia iban con «🖼️ <título>»."""
        from unittest.mock import patch

        from core.models import ArchivoModulo
        from core.module_steps import partes_multimedia_modulo

        with patch.object(ArchivoModulo, 'validar_url_publica', return_value=True):
            ArchivoModulo.objects.create(
                modulo=self.modulo,
                titulo='Diagrama de la colmena',
                tipo='imagen',
                url_externa=URL_IMG,
                activo=True,
            )

        partes = partes_multimedia_modulo(self.modulo)

        self.assertTrue(partes)
        self.assertNotIn('Diagrama de la colmena', partes[0])
        self.assertNotIn('🖼️', partes[0])
        self.assertNotIn(MENSAJE_CAPTION_SOLO_MEDIA, partes[0])

    def test_el_texto_del_paso_si_sigue_siendo_el_caption(self):
        """Lo que el autor escribió para el estudiante sí acompaña a la imagen."""
        paso = self._paso(titulo='002.mp4', contenido='Observe la piquera al amanecer.')

        bloque = partes_mensaje_paso(paso, self.curso)[0]

        self.assertIn('Observe la piquera al amanecer.', bloque)
        self.assertNotIn('002.mp4', bloque)


class EnvioAdjuntoSinCuerpoTests(TestCase):
    """La capa de envío no debe reponer el relleno que quitamos aguas arriba."""

    def _enviar(self, body):
        from unittest.mock import MagicMock

        from core.views import _enviar_mensaje_twilio_segmentado

        client = MagicMock()
        client.messages.create.return_value = MagicMock(sid='SM1')
        _enviar_mensaje_twilio_segmentado(
            client=client,
            from_number='whatsapp:+14155238886',
            to_number='whatsapp:+573000000000',
            body=body,
            media_url=URL_IMG,
        )
        return client.messages.create.call_args.kwargs

    def test_adjunto_sin_texto_no_lleva_cuerpo(self):
        params = self._enviar('')

        self.assertEqual(params.get('media_url'), [URL_IMG])
        self.assertNotIn(MENSAJE_CAPTION_SOLO_MEDIA, params.get('body') or '')
        self.assertFalse((params.get('body') or '').strip())

    def test_adjunto_con_texto_lo_conserva(self):
        params = self._enviar('Observe la piquera al amanecer.')

        self.assertEqual(params.get('body'), 'Observe la piquera al amanecer.')
        self.assertEqual(params.get('media_url'), [URL_IMG])
