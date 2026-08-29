"""Preview Content SID: parser local, sin red Twilio."""
from django.test import SimpleTestCase
from django.utils.safestring import SafeString

from core.twilio_content_preview import (
    _parse_types,
    content_sid_de_campana,
    fill_samples,
    highlight_variables,
    preview_html,
)


class FakeCamp:
    def __init__(self, hx='', plantilla=None):
        self.template_twilio_id = hx
        self.plantilla = plantilla


class FakePlantilla:
    def __init__(self, sid=''):
        self.twilio_template_sid = sid


class TwilioContentPreviewTests(SimpleTestCase):
    def test_sid_campana_directo_gana(self):
        p = FakePlantilla('HXaaaa')
        c = FakeCamp('HXbbbb', p)
        self.assertEqual(content_sid_de_campana(c), 'HXbbbb')

    def test_sid_desde_plantilla(self):
        c = FakeCamp('', FakePlantilla('HXcccc'))
        self.assertEqual(content_sid_de_campana(c), 'HXcccc')

    def test_parse_quick_reply(self):
        kind, body, buttons = _parse_types({
            'twilio/quick-reply': {
                'body': 'Hola {{1}}, listo para {{2}}?',
                'actions': [
                    {'title': 'Sí', 'id': 'si'},
                    {'title': 'Luego', 'id': 'no'},
                ],
            }
        })
        self.assertEqual(kind, 'twilio/quick-reply')
        self.assertIn('{{1}}', body)
        self.assertEqual([b['title'] for b in buttons], ['Sí', 'Luego'])

    def test_highlight_y_samples(self):
        html = highlight_variables('Hola {{1}}')
        self.assertIn('eki-hx-var', html)
        self.assertIn('{{1}}', html)
        self.assertEqual(fill_samples('Hola {{1}}', {'1': 'Ana'}), 'Hola Ana')

    def test_preview_html_error_no_mock(self):
        html = preview_html({'ok': False, 'sid': 'HX1', 'error': 'boom'})
        self.assertIsInstance(html, SafeString)
        self.assertIn('boom', str(html))
        self.assertNotIn('Comenzar curso', str(html))

    def test_preview_html_ok_botones(self):
        html = preview_html({
            'ok': True,
            'sid': 'HXabcd1234abcd1234abcd1234abcd12',
            'name': 'bienvenida',
            'language': 'es',
            'kind': 'twilio/quick-reply',
            'body': 'Hola {{1}}',
            'buttons': [{'title': 'Empezar', 'kind': 'reply'}],
            'variables': {'1': 'María'},
            'approval': 'approved',
            'error': '',
        })
        text = str(html)
        self.assertIn('Hola', text)
        self.assertIn('Empezar', text)
        self.assertIn('María', text)
        self.assertIn('HX', text)
