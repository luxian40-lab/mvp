"""QA: demos de voz Course Engine resolubles (static)."""
from django.test import SimpleTestCase

from core.course_engine.voice_config import catalogo_voces
from core.course_engine.voice_demos import url_demo_voz


class VoiceDemoQaTests(SimpleTestCase):
    def test_cada_voz_catalogo_tiene_demo_static(self):
        faltan = []
        for v in catalogo_voces():
            out = url_demo_voz(v['id'], generar_si_falta=False)
            if not out.get('ok') or not out.get('url'):
                faltan.append(f"{v['label']} ({v['id'][:8]}…) → {out.get('error')}")
            else:
                self.assertIn('/static/course_engine/voices/', out['url'])
                self.assertTrue(out['url'].endswith('.mp3'))
        self.assertEqual(faltan, [], msg='Demos faltantes:\n' + '\n'.join(faltan))
