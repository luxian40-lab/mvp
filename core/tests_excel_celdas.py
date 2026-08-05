"""Celdas Excel: teléfonos no deben perder dígitos."""
from __future__ import annotations

from decimal import Decimal

from core.excel_celdas import celda_excel_a_texto
from core.utils_telefono import normalizar_telefono


def test_celda_float_telefono_colombia():
    assert celda_excel_a_texto(573001234567.0) == '573001234567'
    assert normalizar_telefono(celda_excel_a_texto(573001234567.0)) == '573001234567'


def test_celda_notacion_cientifica_texto():
    assert celda_excel_a_texto('5.73001234567E+11') == '573001234567'
    assert celda_excel_a_texto('5,73001234567E+11') == '573001234567'


def test_celda_decimal_y_entero():
    assert celda_excel_a_texto(573001234567) == '573001234567'
    assert celda_excel_a_texto(Decimal('573001234567')) == '573001234567'


def test_celda_texto_normal():
    assert celda_excel_a_texto(' 573001234567 ') == '573001234567'
    assert celda_excel_a_texto(None) == ''
