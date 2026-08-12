"""Tests P0: conector Agrosavia live + umbral de enriquecimiento."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings

from core.agrosavia_connector import (
    debe_consultar_agrosavia,
    enriquecer_contexto_con_agrosavia,
    formatear_contexto_agrosavia,
)


pytestmark = pytest.mark.django_db


@override_settings(BOT_COMERCIAL_AGROSAVIA_ENABLED=True, BOT_COMERCIAL_AGROSAVIA_MIN_RAG_CHARS=1400)
def test_debe_consultar_si_rag_corto():
    assert debe_consultar_agrosavia('manchas en café Huila', contexto_rag_chars=200) is True


@override_settings(BOT_COMERCIAL_AGROSAVIA_ENABLED=True, BOT_COMERCIAL_AGROSAVIA_MIN_RAG_CHARS=1400)
def test_debe_consultar_pista_agro_con_rag_medio():
    # Entre min y min+800 con pista agro → sí
    assert debe_consultar_agrosavia(
        '¿Qué fungicida para antracnosis en aguacate?',
        contexto_rag_chars=1600,
    ) is True


@override_settings(BOT_COMERCIAL_AGROSAVIA_ENABLED=True, BOT_COMERCIAL_AGROSAVIA_MIN_RAG_CHARS=1400)
def test_no_consulta_rag_muy_largo_sin_pista():
    assert debe_consultar_agrosavia('hola', contexto_rag_chars=3500) is False


@override_settings(BOT_COMERCIAL_AGROSAVIA_ENABLED=False)
def test_no_consulta_si_deshabilitado():
    assert debe_consultar_agrosavia('plaga en papa', contexto_rag_chars=0) is False


def test_formatear_contexto_incluye_atribucion():
    texto = formatear_contexto_agrosavia([
        {
            'titulo': 'Manejo de roya del café',
            'abstract': 'Resumen técnico corto.',
            'tipo': 'Cartilla',
            'cultivo': 'Coffea',
            'url': 'https://repository.agrosavia.co/handle/20.500/demo',
        }
    ])
    assert 'AGROSAVIA' in texto
    assert 'Manejo de roya del café' in texto
    assert 'https://repository.agrosavia.co/handle/' in texto


@override_settings(BOT_COMERCIAL_AGROSAVIA_ENABLED=True, BOT_COMERCIAL_AGROSAVIA_MIN_RAG_CHARS=1400)
def test_enriquecer_concatena_y_meta():
    fake_items = [
        {
            'titulo': 'Cartilla demo',
            'abstract': 'Abstract útil.',
            'tipo': 'Manual',
            'cultivo': '',
            'url': 'https://repository.agrosavia.co/handle/1',
            'handle': '1',
        }
    ]
    with patch('core.agrosavia_connector.buscar_agrosavia', return_value=fake_items) as mock_buscar:
        ctx, meta = enriquecer_contexto_con_agrosavia(
            'Roya en café del Huila',
            contexto_rag='Info eki breve.',
        )
    mock_buscar.assert_called_once()
    assert meta['agrosavia_usada'] is True
    assert meta['agrosavia_items'] == 1
    assert meta['agrosavia_chars'] > 0
    assert 'Info eki breve.' in ctx
    assert 'Cartilla demo' in ctx
    assert 'AGROSAVIA' in ctx


@override_settings(BOT_COMERCIAL_AGROSAVIA_ENABLED=True, BOT_COMERCIAL_AGROSAVIA_MIN_RAG_CHARS=100)
def test_enriquecer_omite_si_no_debe():
    with patch('core.agrosavia_connector.buscar_agrosavia') as mock_buscar:
        ctx, meta = enriquecer_contexto_con_agrosavia(
            'xx',  # query muy corta
            contexto_rag='x' * 500,
        )
    mock_buscar.assert_not_called()
    assert meta['agrosavia_usada'] is False
    assert meta['agrosavia_consultada'] is False
    assert ctx == 'x' * 500
