"""Tests mapeo Excel estudiantes (swap Nombre/Teléfono)."""
from __future__ import annotations

from core.import_estudiantes_excel import (
    extraer_fila_estudiante,
    mapear_columnas_estudiante,
    parece_nombre_persona,
    parece_telefono,
)


def test_mapear_por_encabezados_desordenados():
    headers = ['Nombre Completo', 'Teléfono', 'Documento', 'Tipo documento', 'Cliente']
    m = mapear_columnas_estudiante(headers)
    assert m is not None
    assert m['nombre'] == 0
    assert m['telefono'] == 1
    assert m['documento'] == 2
    assert m['tipo'] == 3
    row = ['Eva Patricia Perez', '573001234567', '1020304050', 'CC', 'Cenipalma']
    c = extraer_fila_estudiante(row, m, True)
    assert c['nombre'] == 'Eva Patricia Perez'
    assert c['telefono_normalizado'] == '573001234567'
    assert c['cedula'] == '1020304050'


def test_swap_nombre_telefono_posicional():
    # Plantilla: Tipo, Doc, Nombre, Tel — pero usuario puso Tel y Nombre al revés
    row = ['CC', '1020304050', '573001234567', 'Eva Patricia Perez Alarcon', '', '', '', '', '', '']
    c = extraer_fila_estudiante(row, None, True)
    assert c['nombre'] == 'Eva Patricia Perez Alarcon'
    assert c['telefono_normalizado'] == '573001234567'


def test_parece_helpers():
    assert parece_nombre_persona('Eva Patricia Perez Alarcon')
    assert not parece_telefono('Eva Patricia Perez Alarcon')
    assert parece_telefono('573001234567')
    assert parece_telefono(573001234567.0)
