"""Tests para el agente PQRS automático.

Cubre:
- Caso ``acceso`` resuelto por el agente (queda ``en_atencion``).
- Caso ``tecnico`` escalado (queda ``pendiente``).
- Caso fallback cuando OpenAI no está disponible (escala con seguridad).
- Parser robusto frente a JSON malformado.

Los tests mockean la llamada a OpenAI para no depender de la red.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from django.test import TestCase

from core.models import Cliente, Estudiante, SolicitudSoporte
from core.pqrs_agent import (
    aplicar_resultado_pqrs,
    procesar_pqrs_automatico,
    _fallback_escalar,
    _parsear_respuesta_pqrs,
)


def _make_estudiante(cliente=None) -> Estudiante:
    if cliente is None:
        cliente = Cliente.objects.create(
            nombre="Test Coop",
            nit="900000000-0",
            contacto_principal="Tester",
            email="t@example.com",
            telefono="573000099999",
            activo=True,
        )
    return Estudiante.objects.create(
        cedula="9999999",
        nombre="Productor Test",
        telefono="573000099998",
        cliente=cliente,
        estado_chat="ACTIVO",
        acepto_terminos=True,
        activo=True,
    )


@pytest.mark.django_db
class TestAgentePQRS(TestCase):
    def setUp(self):
        self.estudiante = _make_estudiante()
        self.solicitud = SolicitudSoporte.objects.create(
            estudiante=self.estudiante,
            mensaje_original="No puedo entrar, mi cédula sale mal",
            keyword_usada="ayuda",
            prioridad="media",
        )

    def test_acceso_resuelto_por_agente(self):
        """Mensaje de acceso → agente resuelve, solicitud queda en_atencion."""
        respuesta_modelo = (
            '{"categoria":"acceso","respuesta_whatsapp":"Hola, intente con su cédula sin puntos.",'
            '"escalar":false,"nota_interna":"Acceso, resuelto en primer nivel."}'
        )
        with patch("core.pqrs_agent._llamar_openai_pqrs", return_value=respuesta_modelo):
            resultado = procesar_pqrs_automatico(self.solicitud)
        self.assertEqual(resultado["categoria"], "acceso")
        self.assertFalse(resultado["escalar"])
        self.assertIn("Si necesita más ayuda escríbame de nuevo.", resultado["respuesta_whatsapp"])

        aplicar_resultado_pqrs(self.solicitud, resultado)
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.categoria, "acceso")
        self.assertTrue(self.solicitud.resuelto_por_agente)
        self.assertEqual(self.solicitud.estado, "en_atencion")
        self.assertIn("[Agente PQRS]", self.solicitud.notas_internas)

    def test_tecnico_se_escala(self):
        """Categoría 'tecnico' SIEMPRE escala aunque el modelo diga lo contrario."""
        respuesta_modelo = (
            '{"categoria":"tecnico","respuesta_whatsapp":"Reportamos su caso al equipo.",'
            '"escalar":false,"nota_interna":"Error 500 al cargar el video."}'
        )
        with patch("core.pqrs_agent._llamar_openai_pqrs", return_value=respuesta_modelo):
            resultado = procesar_pqrs_automatico(self.solicitud)
        self.assertEqual(resultado["categoria"], "tecnico")
        self.assertTrue(resultado["escalar"])

        aplicar_resultado_pqrs(self.solicitud, resultado)
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, "pendiente")
        self.assertFalse(self.solicitud.resuelto_por_agente)

    def test_fallback_si_openai_falla(self):
        """Si OpenAI no responde, fallback escala con seguridad."""
        with patch("core.pqrs_agent._llamar_openai_pqrs", return_value=None):
            resultado = procesar_pqrs_automatico(self.solicitud)
        self.assertEqual(resultado["categoria"], "otro")
        self.assertTrue(resultado["escalar"])
        self.assertIn("Si necesita más ayuda escríbame de nuevo.", resultado["respuesta_whatsapp"])

    def test_fallback_si_mensaje_vacio(self):
        self.solicitud.mensaje_original = ""
        self.solicitud.save()
        resultado = procesar_pqrs_automatico(self.solicitud)
        self.assertTrue(resultado["escalar"])
        self.assertEqual(resultado["categoria"], "otro")

    def test_parser_json_invalido_devuelve_fallback(self):
        resultado = _parsear_respuesta_pqrs("no es json")
        self.assertEqual(resultado["categoria"], "otro")
        self.assertTrue(resultado["escalar"])

    def test_parser_agrega_cierre_si_falta(self):
        raw = (
            '{"categoria":"contenido","respuesta_whatsapp":"Mire el video del módulo 2.",'
            '"escalar":false,"nota_interna":"Contenido"}'
        )
        resultado = _parsear_respuesta_pqrs(raw)
        self.assertIn("Si necesita más ayuda escríbame de nuevo.", resultado["respuesta_whatsapp"])

    def test_fallback_helper_estructura(self):
        f = _fallback_escalar("motivo X")
        self.assertEqual(f["categoria"], "otro")
        self.assertTrue(f["escalar"])
        self.assertIn("Fallback", f["nota_interna"])
