"""Ventas consulta la FAO. Los otros oficios no."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from django.test import override_settings

from core.fao_connector import (
    debe_consultar_fao,
    enriquecer_contexto_fao,
    formatear_contexto_fao,
)
from core.sandbox_agentes import responder_agente_sandbox


pytestmark = pytest.mark.django_db


@override_settings(BOT_VENTAS_FAO_ENABLED=True)
def test_consulta_si_la_pregunta_es_de_ventas():
    assert debe_consultar_fao('no estoy vendiendo el café a buen precio') is True


@override_settings(BOT_VENTAS_FAO_ENABLED=True)
def test_no_consulta_plagas_ni_saludos():
    assert debe_consultar_fao('hay plaga en el café') is False
    assert debe_consultar_fao('hola') is False


@override_settings(BOT_VENTAS_FAO_ENABLED=False)
def test_no_consulta_si_esta_apagado():
    assert debe_consultar_fao('cómo consigo clientes y mejoro el margen') is False


def test_formatear_atribuye_a_la_fao():
    texto = formatear_contexto_fao([{
        'titulo': 'Cooperativas agrícolas',
        'abstract': 'Guía de comercialización.',
        'tipo': 'Book',
        'url': 'https://openknowledge.fao.org/handle/20.500/demo',
    }])
    assert 'FAO' in texto
    assert 'Cooperativas agrícolas' in texto
    assert 'openknowledge.fao.org/handle/' in texto


@override_settings(BOT_VENTAS_FAO_ENABLED=True)
def test_enriquecer_concatena_sin_pisar_el_conocimiento():
    items = [{
        'titulo': 'Guía de mercado',
        'abstract': 'Resumen.',
        'tipo': 'Manual',
        'url': 'https://openknowledge.fao.org/handle/1',
        'handle': '1',
    }]
    with patch('core.fao_connector.buscar_fao', return_value=items) as mock_buscar:
        ctx, meta = enriquecer_contexto_fao(
            'el cliente dice que el precio está caro',
            contexto_rag='Conocimiento aprobado.',
        )
    mock_buscar.assert_called_once()
    assert meta['fao_usada'] is True
    assert ctx.startswith('Conocimiento aprobado.')
    assert 'Guía de mercado' in ctx


@override_settings(OPENAI_API_KEY='sk-test', BOT_VENTAS_FAO_ENABLED=True)
def test_solo_ventas_consulta_la_fao():
    with patch('core.presupuesto_llm.debe_degradar', return_value=False), \
            patch('core.fao_connector.enriquecer_contexto_fao', return_value=('FAO', {'fao_usada': True})) as fao, \
            patch('core.openai_compat.completar_chat', return_value='Respuesta de prueba.'):
        ventas = responder_agente_sandbox('ventas', 'no consigo clientes para vender')
        coach = responder_agente_sandbox('coach', 'no consigo constancia para vender hoy')
    assert ventas == 'Respuesta de prueba.'
    assert coach == 'Respuesta de prueba.'
    fao.assert_called_once()
    assert 'clientes' in fao.call_args.args[0]
