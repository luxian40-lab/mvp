"""
Tipos de documento de identidad para LatAm (campañas multi-país).

El campo de modelo sigue llamándose ``cedula`` por legacy, pero almacena
cualquier número/ID según ``tipo_documento``.
"""
from __future__ import annotations

import re
import unicodedata

# Códigos cortos (max 8) usados en Estudiante.tipo_documento
TIPO_DOCUMENTO_CHOICES = [
    # Colombia
    ('CC', 'Cédula de Ciudadanía (CO)'),
    ('TI', 'Tarjeta de Identidad (CO)'),
    ('CE', 'Cédula de Extranjería (CO)'),
    # LatAm frecuentes
    ('DUI', 'DUI — Documento Único de Identidad (SV)'),
    ('CURP', 'CURP (MX)'),
    ('INE', 'Credencial INE / IFE (MX)'),
    ('DNI', 'DNI — Documento Nacional de Identidad'),
    ('RUT', 'RUT (CL)'),
    ('DPI', 'DPI (GT)'),
    ('CI', 'Cédula de Identidad (LatAm)'),
    # Universal
    ('PP', 'Pasaporte'),
    ('OTRO', 'Otro documento / ID'),
]

_CODIGOS_VALIDOS = {c for c, _ in TIPO_DOCUMENTO_CHOICES}

# Alias de texto libre → código (import Excel / Forms)
_ALIASES_TIPO = {
    'cc': 'CC',
    'cedula': 'CC',
    'cedula de ciudadania': 'CC',
    'cedula ciudadania': 'CC',
    'ti': 'TI',
    'tarjeta de identidad': 'TI',
    'ce': 'CE',
    'cedula de extranjeria': 'CE',
    'extranjeria': 'CE',
    'dui': 'DUI',
    'documento unico': 'DUI',
    'documento unico de identidad': 'DUI',
    'curp': 'CURP',
    'ine': 'INE',
    'ife': 'INE',
    'credencial': 'INE',
    'dni': 'DNI',
    'rut': 'RUT',
    'dpi': 'DPI',
    'ci': 'CI',
    'cedula de identidad': 'CI',
    'pp': 'PP',
    'pasaporte': 'PP',
    'passport': 'PP',
    'otro': 'OTRO',
    'id': 'OTRO',
    'documento': 'OTRO',
}


def _sin_acentos(s: str) -> str:
    nfkd = unicodedata.normalize('NFD', s or '')
    return ''.join(c for c in nfkd if unicodedata.category(c) != 'Mn')


def normalizar_tipo_documento(raw: str | None, default: str = 'CC') -> str:
    """Resuelve texto/código a un choice válido."""
    if raw is None:
        return default if default in _CODIGOS_VALIDOS else 'CC'
    s = _sin_acentos(str(raw)).strip().upper()
    if not s:
        return default if default in _CODIGOS_VALIDOS else 'CC'
    if s in _CODIGOS_VALIDOS:
        return s
    key = _sin_acentos(str(raw)).strip().lower()
    key = re.sub(r'\s+', ' ', key)
    if key in _ALIASES_TIPO:
        return _ALIASES_TIPO[key]
    # Aceptar códigos ya en mayúsculas aunque no estén en alias
    if s in _ALIASES_TIPO.values():
        return s
    return default if default in _CODIGOS_VALIDOS else 'OTRO'


def normalizar_numero_documento(raw: str | None) -> str:
    """
    Limpia número/ID: quita espacios, puntos y guiones; conserva letras/dígitos.
    CURP, RUT y similares necesitan alfanuméricos.
    """
    if raw is None:
        return ''
    s = str(raw).strip()
    if s.upper().startswith('TEMP_'):
        return s
    # Excel a veces manda float
    if re.fullmatch(r'\d+\.0+', s):
        s = s.split('.', 1)[0]
    s = re.sub(r'[\s\.\-]', '', s)
    s = s.upper()
    # Solo alfanumérico (permite CURP / RUT con K)
    s = re.sub(r'[^A-Z0-9]', '', s)
    return s


def etiqueta_documento(tipo: str | None, numero: str | None) -> str:
    tipo_n = normalizar_tipo_documento(tipo)
    return f'{tipo_n} {numero or ""}'.strip()
