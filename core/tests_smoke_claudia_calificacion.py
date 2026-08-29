"""
QA gate: Claudia calificación — respuestas vacías vs sustancia vs fallback sin IA.
Ejecutar en precheck antes de deploy.
"""
from unittest.mock import MagicMock, patch

import pytest

from core.gamificacion_modo import MODO_CALIFICACION, MODO_PUNTOS, construir_mensaje_evaluacion_reto
from core.models import Cliente, Curso, Estudiante, ProgresoEstudiante
from core.tutor_ia_modulo import (
    _es_respuesta_sin_contenido_reto,
    evaluar_reto_facilitador,
)

RESPUESTA_BUENA = (
    'Revisaría el gasto en mercado primero, anotaría 50 mil pesos semanales '
    'y cortaría antojos los viernes para ahorrar 20 mil.'
)
RETO = '¿Qué haría usted con su presupuesto semanal del hogar?'


@pytest.mark.parametrize(
    'texto',
    ['no se', 'no sé', 'bueno', 'ok', 'vale', '   ', 'si'],
)
def test_qa_respuesta_vacia_no_pasa(texto):
    assert _es_respuesta_sin_contenido_reto(texto)


def test_qa_respuesta_buena_pasa_detector():
    assert not _es_respuesta_sin_contenido_reto(RESPUESTA_BUENA)


@pytest.mark.parametrize('texto', ['no se', 'bueno', 'ok'])
def test_qa_evaluacion_vacia_siempre_1_sin_llamar_openai(texto):
    with patch('core.tutor_ia_modulo._get_client') as mock_client:
        puntaje, fb = evaluar_reto_facilitador(
            modulos_cubiertos=[],
            respuesta_estudiante=texto,
            reto_original=RETO,
            estudiante_nombre='Ana',
        )
    mock_client.assert_not_called()
    assert puntaje == 1
    assert 'evidencia' in fb.lower() or 'no sabía' in fb.lower()


@patch('core.tutor_ia_modulo._get_client')
def test_qa_evaluacion_buena_usa_openai_y_parsea(mock_client):
    choice = MagicMock()
    choice.message.content = (
        'Citó el gasto en mercado y un monto concreto. '
        'Puntaje total: 8/10\nDesglose: Enfoque 3/3 | Fundamentación 3/4 | Claridad 2/3'
    )
    mock_client.return_value.chat.completions.create.return_value = MagicMock(choices=[choice])

    puntaje, fb = evaluar_reto_facilitador(
        modulos_cubiertos=[],
        respuesta_estudiante=RESPUESTA_BUENA,
        reto_original=RETO,
        estudiante_nombre='Ana',
    )
    assert puntaje == 8
    assert '8/10' in fb or puntaje >= 7
    mock_client.return_value.chat.completions.create.assert_called_once()


@patch('core.tutor_ia_modulo._get_client', return_value=None)
def test_qa_fallback_sin_ia_cero_puntos(mock_client):
    puntaje, fb = evaluar_reto_facilitador(
        modulos_cubiertos=[],
        respuesta_estudiante=RESPUESTA_BUENA,
        reto_original=RETO,
        estudiante_nombre='Luis',
    )
    assert puntaje == 0
    assert 'no se registró puntaje' in fb.lower() or 'no pude evaluar' in fb.lower()


@pytest.mark.django_db
@patch('core.tutor_ia_modulo._get_client', return_value=None)
def test_qa_mensaje_whatsapp_sin_otorgar_puntos_en_fallback(_mock):
    cli = Cliente.objects.create(
        nombre='QA Coop',
        contacto_principal='Q',
        email='qa@test.co',
        telefono='573000000099',
        modo_gamificacion=MODO_PUNTOS,
    )
    curso = Curso.objects.create(nombre='Finanzas QA', cliente=cli, activo=True)
    est = Estudiante.objects.create(
        cedula='999',
        nombre='QA Est',
        telefono='573000000098',
        cliente=cli,
        activo=True,
    )
    prog = ProgresoEstudiante.objects.create(estudiante=est, curso=curso)
    puntaje, fb = evaluar_reto_facilitador(
        [], RESPUESTA_BUENA, RETO, estudiante_nombre='QA Est',
    )
    msg = construir_mensaje_evaluacion_reto(est, prog, puntaje, fb, 'Claudia')
    assert 'no se registró puntaje' in msg.lower() or 'no pude evaluar' in msg.lower()
    est.refresh_from_db()
    assert not hasattr(est, 'perfilgamificacion') or getattr(
        getattr(est, 'perfilgamificacion', None), 'puntos_totales', 0
    ) in (0, None)
