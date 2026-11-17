"""Slice 1: tip en lección detrás de EKI_TURNO_LECCION_TIP (sin LLM)."""
from types import SimpleNamespace

from django.test import SimpleTestCase, override_settings

from core.avance_whatsapp import (
    MARCADOR_BOTON_CONTINUEMOS,
    TEXTO_NO_ENTENDI,
    texto_cuando_no_es_listo,
)
from core.conversacion.turno_leccion import (
    TEXTO_TIP_LECCION_USTED,
    TEXTO_TIP_MEDIA_USTED,
    clasificar_mensaje_leccion,
    texto_tip_turno_leccion,
)


class ClasificarLeccionTests(SimpleTestCase):
    def test_gasto_hormiga_es_leccion_no_media(self):
        self.assertEqual(
            clasificar_mensaje_leccion(
                'un gasto hormiga puede ser gasto diario de comprar dulces'
            ),
            'leccion',
        )

    def test_no_veo_video_es_media(self):
        self.assertEqual(
            clasificar_mensaje_leccion('no veo el video'),
            'media',
        )


@override_settings(EKI_TURNO_LECCION_TIP=False)
class FlagApagadoConservaNoEntendiTests(SimpleTestCase):
    def test_sin_flag_sigue_no_entendi(self):
        est = SimpleNamespace(cliente_id=27, contexto_temporal={})
        out = texto_cuando_no_es_listo(
            est, 'un gasto hormiga puede ser gasto diario'
        )
        self.assertEqual(out, TEXTO_NO_ENTENDI)
        self.assertIn('No entendí', out)


@override_settings(EKI_TURNO_LECCION_TIP=True)
class FlagPrendidoTipTests(SimpleTestCase):
    def test_reflexion_pide_continuar_sin_no_entendi(self):
        est = SimpleNamespace(cliente_id=27, contexto_temporal={})
        out = texto_cuando_no_es_listo(
            est, 'un gasto hormiga puede ser gasto diario de comprar dulces'
        )
        self.assertNotIn('No entendí', out)
        self.assertIn('Continuar', out)
        self.assertIn(MARCADOR_BOTON_CONTINUEMOS, out)
        self.assertEqual(out, TEXTO_TIP_LECCION_USTED)

    def test_media_tip_sin_no_entendi(self):
        est = SimpleNamespace(cliente_id=27, contexto_temporal={})
        out = texto_cuando_no_es_listo(est, 'no veo el video')
        self.assertNotIn('No entendí', out)
        self.assertEqual(out, TEXTO_TIP_MEDIA_USTED)

    def test_agri_tip_en_tu(self):
        with override_settings(EKI_AGRICAPITAL_CLIENTE_ID='26'):
            est = SimpleNamespace(cliente_id=26, contexto_temporal={})
            out = texto_tip_turno_leccion(est, 'quiero anotar una idea')
            self.assertNotIn('No entendí', out)
            self.assertIn('toca Continuar', out)
            self.assertIn('te ayudamos', out)
