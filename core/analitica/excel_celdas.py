"""Celdas Excel → texto sin perder dígitos de teléfono/documento."""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation


def celda_excel_a_texto(val) -> str:
    """
    openpyxl a menudo entrega teléfonos como float (5.73e11) o texto científico.
    Convertimos a dígitos/texto legible sin notación científica.
    """
    if val is None:
        return ''
    if isinstance(val, bool):
        return '1' if val else '0'
    if isinstance(val, int):
        return str(val)
    if isinstance(val, float):
        if abs(val) >= 1e15:
            # fuera de rango seguro float→int; intentar Decimal vía str
            try:
                return format(Decimal(str(val)), 'f').split('.')[0]
            except (InvalidOperation, ValueError):
                return re.sub(r'\D', '', f'{val:.0f}')
        rounded = int(round(val))
        if abs(val - rounded) < 1e-6:
            return str(rounded)
        return str(val).strip()
    if isinstance(val, Decimal):
        try:
            if val == val.to_integral_value():
                return str(int(val))
        except Exception:
            pass
        return format(val, 'f').rstrip('0').rstrip('.')

    s = str(val).strip()
    if not s:
        return ''
    # "5.73001234567E+11" o "5,73001234567E+11"
    sci = s.replace(',', '.')
    if re.match(r'^[+-]?\d+(\.\d+)?[eE][+-]?\d+$', sci):
        try:
            return str(int(round(float(sci))))
        except (ValueError, OverflowError):
            pass
    if re.match(r'^\d+\.0+$', s):
        return s.split('.', 1)[0]
    return s
