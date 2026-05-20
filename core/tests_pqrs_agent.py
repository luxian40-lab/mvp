"""Tests ampliados del agente PQRS (máx. 2 preguntas, alcance, contenido curso)."""
from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase

from core.models import Cliente, Estudiante, SolicitudSoporte
from core.pqrs_agent import (
    MENSAJE_CONTENIDO_CURSO,
    MENSAJE_FUERA_ALCANCE,
    aplicar_resultado_pqrs,
    procesar_pqrs_automatico,
    procesar_seguimiento_pqrs,
)


def _estudiante() -> Estudiante:
    cliente = Cliente.objects.create(
        nombre='Coop Test',
        nit='900000001-0',
        contacto_principal='Tester',
        email='pqrs@example.com',
        telefono='573000099990',
        activo=True,
    )
    return Estudiante.objects.create(
        cedula='8888888',
        nombre='Est PQRS',
        telefono='573000099991',
        cliente=cliente,
        estado_chat='ACTIVO',
        acepto_terminos=True,
        activo=True,
    )


class TestPQRSAgentReglas(TestCase):
    def setUp(self):
        self.est = _estudiante()

    def test_max_dos_preguntas_escalada(self):
        solicitud = SolicitudSoporte.objects.create(
            estudiante=self.est,
            mensaje_original='ayuda',
            keyword_usada='ayuda',
            estado='en_atencion',
            resuelto_por_agente=False,
            preguntas_realizadas=2,
        )
        resultado = procesar_seguimiento_pqrs(solicitud, 'sigue sin funcionar')
        self.assertTrue(resultado['escalar'])
        self.assertEqual(resultado['categoria'], 'otro')
        self.assertIn('2 intentos', resultado['nota_interna'])

        aplicar_resultado_pqrs(solicitud, resultado)
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, 'pendiente')
        self.assertFalse(solicitud.resuelto_por_agente)

    def test_fuera_de_alcance_remite_facilitador(self):
        solicitud = SolicitudSoporte.objects.create(
            estudiante=self.est,
            mensaje_original='Quiero cambiar mi teléfono',
            keyword_usada='ayuda',
        )
        resultado = procesar_pqrs_automatico(solicitud)
        self.assertIn(MENSAJE_FUERA_ALCANCE, resultado['respuesta_whatsapp'])
        aplicar_resultado_pqrs(solicitud, resultado)
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, 'pendiente')
        self.assertIn('fuera de alcance', solicitud.notas_internas.lower())

    def test_consulta_contenido_no_respondida(self):
        solicitud = SolicitudSoporte.objects.create(
            estudiante=self.est,
            mensaje_original='¿Cuándo se fumiga el café y qué dosis de fertilizante?',
            keyword_usada='ayuda',
        )
        resultado = procesar_pqrs_automatico(solicitud)
        self.assertIn(MENSAJE_CONTENIDO_CURSO, resultado['respuesta_whatsapp'])
        self.assertFalse(resultado['escalar'])
        self.assertNotIn('dosis', resultado['respuesta_whatsapp'].lower())

    def test_pregunta_clarificacion_incrementa_contador(self):
        solicitud = SolicitudSoporte.objects.create(
            estudiante=self.est,
            mensaje_original='ayuda',
            keyword_usada='ayuda',
            estado='en_atencion',
            resuelto_por_agente=False,
            preguntas_realizadas=0,
        )
        raw = (
            '{"categoria":"acceso","respuesta_whatsapp":"¿Podría indicar si es acceso o contenido?",'
            '"escalar":false,"nota_interna":"ambiguo",'
            '"hacer_pregunta_clarificacion":true,"fuera_de_alcance":false,"consulta_contenido_curso":false}'
        )
        with patch('core.pqrs_agent._llamar_openai_pqrs', return_value=raw):
            resultado = procesar_seguimiento_pqrs(solicitud, 'no sé')
        aplicar_resultado_pqrs(solicitud, resultado)
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.preguntas_realizadas, 1)
        self.assertFalse(solicitud.resuelto_por_agente)
