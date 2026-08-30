# -*- coding: utf-8 -*-
from django.test import SimpleTestCase

from core.course_engine.budget import VideoTier, aplicar_limites_storyboard, validar_presupuesto
from core.course_engine.types import Scene, SceneType, Storyboard


class BudgetTests(SimpleTestCase):
    def test_degrada_video_ia_en_economico(self):
        sb = Storyboard(
            titulo_leccion='T',
            objetivo='O',
            escenas=[
                Scene(1, SceneType.VIDEO_IA, 'V', 'guion', 6.0, 'visual'),
            ],
        )
        out = aplicar_limites_storyboard(sb, VideoTier.ECONOMICO)
        self.assertEqual(out.escenas[0].tipo, SceneType.IMAGEN_ZOOM)
        self.assertEqual(out.escenas[0].metadata.get('degradado_desde'), 'video_ia')

    def test_validar_presupuesto_ok(self):
        sb = Storyboard(
            titulo_leccion='T',
            objetivo='O',
            escenas=[
                Scene(i, SceneType.IMAGEN, f'S{i}', 'texto corto', 5.0, 'v')
                for i in range(1, 5)
            ],
        )
        ok, costo, msg = validar_presupuesto(sb, 'economico')
        self.assertTrue(ok, msg)
        self.assertLess(costo, 2.0)
