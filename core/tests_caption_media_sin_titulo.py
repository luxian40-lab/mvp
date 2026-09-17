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

    def test_media_sin_texto_no_manda_el_titulo(self):
        paso = self._paso(titulo='001.mp4')

        partes = partes_mensaje_paso(paso, self.curso)

        bloque = partes[0]
        self.assertNotIn('001.mp4', bloque)
        self.assertIn(MENSAJE_CAPTION_SOLO_MEDIA, bloque)
        self.assertIn(f'[MEDIA:{URL_IMG}]', bloque)

    def test_tampoco_el_titulo_de_la_seccion_ni_del_modulo(self):
        paso = self._paso()

        bloque = partes_mensaje_paso(paso, self.curso)[0]

        self.assertNotIn('Bloque 1', bloque)
        self.assertNotIn('Bienvenida', bloque)

    def test_el_texto_del_paso_si_sigue_siendo_el_caption(self):
        """Lo que el autor escribió para el estudiante sí acompaña a la imagen."""
        paso = self._paso(titulo='002.mp4', contenido='Observe la piquera al amanecer.')

        bloque = partes_mensaje_paso(paso, self.curso)[0]

        self.assertIn('Observe la piquera al amanecer.', bloque)
        self.assertNotIn('002.mp4', bloque)
