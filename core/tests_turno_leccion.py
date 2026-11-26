"""Turno en lección: tip (slice 1) y Compañero una vez (slice 2), sin LLM de más."""
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from core.conversacion.avance_whatsapp import (
    MARCADOR_BOTON_CONTINUEMOS,
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

    def test_pregunta_clara_es_pregunta(self):
        self.assertEqual(
            clasificar_mensaje_leccion('¿qué es el interés compuesto?'),
            'pregunta',
        )


@override_settings(EKI_TURNO_LECCION_TIP=False, EKI_TURNO_LECCION_COMPANERO=False)
class PausaLeccionNuncaNoEntendiTests(SimpleTestCase):
    """Pausa ACTIVO: tip/CTA, nunca «No entendí». Avance solo con el botón/listo."""

    def test_sin_flag_tip_sin_no_entendi(self):
        est = SimpleNamespace(cliente_id=27, contexto_temporal={}, pk=1, nombre='Ana')
        out = texto_cuando_no_es_listo(
            est, 'un gasto hormiga puede ser gasto diario'
        )
        self.assertEqual(out, TEXTO_TIP_LECCION_USTED)
        self.assertNotIn('No entendí', out)

    def test_cortesia_pide_continuar_sin_no_entendi(self):
        """si/ok/emoji no avanzan; reciben tip, no rechazo."""
        from core.conversacion.intent_detector import mensaje_indica_listo

        est = SimpleNamespace(cliente_id=27, contexto_temporal={}, pk=1, nombre='Ana')
        for msg in ('si', 'ok', '👍', '✅'):
            with self.subTest(msg=msg):
                self.assertFalse(mensaje_indica_listo(msg))
                out = texto_cuando_no_es_listo(est, msg)
                self.assertNotIn('No entendí', out)
                self.assertIn(MARCADOR_BOTON_CONTINUEMOS, out)


@override_settings(EKI_TURNO_LECCION_TIP=True, EKI_TURNO_LECCION_COMPANERO=False)
class FlagPrendidoTipTests(SimpleTestCase):
    def test_reflexion_pide_continuar_sin_no_entendi(self):
        est = SimpleNamespace(cliente_id=27, contexto_temporal={}, pk=1, nombre='Ana')
        out = texto_cuando_no_es_listo(
            est, 'un gasto hormiga puede ser gasto diario de comprar dulces'
        )
        self.assertNotIn('No entendí', out)
        self.assertIn('Continuar', out)
        self.assertIn(MARCADOR_BOTON_CONTINUEMOS, out)
        self.assertEqual(out, TEXTO_TIP_LECCION_USTED)

    def test_media_tip_sin_no_entendi(self):
        est = SimpleNamespace(cliente_id=27, contexto_temporal={}, pk=1, nombre='Ana')
        out = texto_cuando_no_es_listo(est, 'no veo el video')
        self.assertNotIn('No entendí', out)
        self.assertEqual(out, TEXTO_TIP_MEDIA_USTED)

    def test_agri_tip_en_tu(self):
        with override_settings(EKI_AGRICAPITAL_CLIENTE_ID='26'):
            est = SimpleNamespace(cliente_id=26, contexto_temporal={}, pk=1, nombre='Ana')
            out = texto_tip_turno_leccion(est, 'quiero anotar una idea')
            self.assertNotIn('No entendí', out)
            self.assertIn('toca Continuar', out)
            self.assertIn('te ayudamos', out)


@override_settings(EKI_TURNO_LECCION_TIP=True, EKI_TURNO_LECCION_COMPANERO=True)
class CompaneroEnLeccionTests(SimpleTestCase):
    def test_pregunta_recibe_companero_sin_abrir_reto(self):
        est = SimpleNamespace(
            cliente_id=27, contexto_temporal={'curso_activo_id': 53}, pk=9, nombre='Ana',
        )
        with patch(
            'core.conversacion.turno_leccion._modulos_para_duda', return_value=[],
        ), patch(
            'core.agentes.tutor_ia_modulo.generar_respuesta_asistente',
            return_value='El interés compuesto suma rendimiento sobre rendimiento.',
        ) as gen:
            out = texto_cuando_no_es_listo(est, '¿qué es el interés compuesto?')
        gen.assert_called_once()
        self.assertNotIn('No entendí', out)
        self.assertIn('interés compuesto', out.lower())
        self.assertIn('Continuar', out)
        self.assertIn(MARCADOR_BOTON_CONTINUEMOS, out)

    def test_reflexion_no_llama_companero(self):
        est = SimpleNamespace(cliente_id=27, contexto_temporal={}, pk=9, nombre='Ana')
        with patch('core.agentes.tutor_ia_modulo.generar_respuesta_asistente') as gen:
            out = texto_cuando_no_es_listo(
                est, 'un gasto hormiga puede ser gasto diario de comprar dulces'
            )
        gen.assert_not_called()
        self.assertEqual(out, TEXTO_TIP_LECCION_USTED)

    def test_media_sigue_siendo_tip_no_companero(self):
        est = SimpleNamespace(cliente_id=27, contexto_temporal={}, pk=9, nombre='Ana')
        with patch('core.agentes.tutor_ia_modulo.generar_respuesta_asistente') as gen:
            out = texto_cuando_no_es_listo(est, 'no veo el video')
        gen.assert_not_called()
        self.assertEqual(out, TEXTO_TIP_MEDIA_USTED)


# Clientes en producción (Alitic, Agrosavia, Agri, Lhaura, Ganaderos).
_CLIENTES_PRODUCCION = (7, 22, 26, 27, 28)


@override_settings(EKI_TURNO_LECCION_TIP=True, EKI_TURNO_LECCION_COMPANERO=True)
class NingunCursoDevuelveNoEntendiTests(SimpleTestCase):
    """Con los flags de producción, texto libre en lección no puede decir «No entendí»."""

    def test_reflexion_y_media_en_todos_los_clientes(self):
        for cliente_id in _CLIENTES_PRODUCCION:
            est = SimpleNamespace(
                cliente_id=cliente_id,
                contexto_temporal={'curso_activo_id': 53},
                pk=1000 + cliente_id,
                nombre='QA',
            )
            with self.subTest(cliente_id=cliente_id, caso='reflexion'):
                out = texto_cuando_no_es_listo(
                    est, 'un gasto hormiga puede ser gasto diario de comprar dulces',
                )
                self.assertNotIn('No entendí', out)
                self.assertIn(MARCADOR_BOTON_CONTINUEMOS, out)
            with self.subTest(cliente_id=cliente_id, caso='media'):
                out = texto_cuando_no_es_listo(est, 'no veo el video')
                self.assertNotIn('No entendí', out)
                self.assertIn(MARCADOR_BOTON_CONTINUEMOS, out)

    def test_pregunta_en_todos_los_clientes_sin_no_entendi(self):
        for cliente_id in _CLIENTES_PRODUCCION:
            est = SimpleNamespace(
                cliente_id=cliente_id,
                contexto_temporal={'curso_activo_id': 53},
                pk=2000 + cliente_id,
                nombre='QA',
            )
            with self.subTest(cliente_id=cliente_id), patch(
                'core.conversacion.turno_leccion._modulos_para_duda', return_value=[],
            ), patch(
                'core.agentes.tutor_ia_modulo.generar_respuesta_asistente',
                return_value='Respuesta de prueba del Compañero.',
            ):
                out = texto_cuando_no_es_listo(est, '¿qué es el interés compuesto?')
                self.assertNotIn('No entendí', out)
                self.assertIn('Continuar', out)
                self.assertIn(MARCADOR_BOTON_CONTINUEMOS, out)
