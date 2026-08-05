"""Mapeo flexible de columnas Excel para importar estudiantes."""
from __future__ import annotations

import re

from core.excel_celdas import celda_excel_a_texto
from core.utils_telefono import normalizar_telefono


def _norm_header(val) -> str:
    return re.sub(r'\s+', ' ', celda_excel_a_texto(val).lower().strip())


def parece_telefono(val) -> bool:
    digits = re.sub(r'\D', '', celda_excel_a_texto(val))
    return len(digits) >= 10


def parece_nombre_persona(val) -> bool:
    s = celda_excel_a_texto(val).strip()
    if len(s) < 5:
        return False
    digits = sum(c.isdigit() for c in s)
    letters = sum(c.isalpha() for c in s)
    return letters >= 5 and digits <= 2 and (' ' in s or letters >= 8)


def mapear_columnas_estudiante(headers: list[str]) -> dict[str, int] | None:
    """
    Devuelve índices por campo si los encabezados son reconocibles.
    None → usar layout posicional.
    """
    idx: dict[str, int] = {}
    for i, raw in enumerate(headers):
        h = _norm_header(raw)
        if not h:
            continue
        if h in ('tipo documento', 'tipo_documento', 'tipodocumento', 'tipo doc', 'tipo'):
            idx.setdefault('tipo', i)
        elif 'tipo' in h and 'doc' in h:
            idx.setdefault('tipo', i)
        elif h in ('documento', 'cedula', 'cédula', 'nro documento', 'numero documento', 'nº documento', 'id'):
            idx.setdefault('documento', i)
        elif 'documento' in h and 'tipo' not in h:
            idx.setdefault('documento', i)
        elif 'cedula' in h or 'cédula' in h:
            idx.setdefault('documento', i)
        elif h in ('nombre completo', 'nombre', 'nombres', 'estudiante'):
            idx.setdefault('nombre', i)
        elif 'nombre' in h:
            idx.setdefault('nombre', i)
        elif h in ('telefono', 'teléfono', 'celular', 'whatsapp', 'movil', 'móvil', 'tel'):
            idx.setdefault('telefono', i)
        elif any(k in h for k in ('tel', 'celu', 'whats', 'móvil', 'movil')):
            idx.setdefault('telefono', i)
        elif 'municipio' in h or h in ('ciudad', 'city'):
            idx.setdefault('municipio', i)
        elif 'departamento' in h or 'estado' in h or 'provincia' in h:
            idx.setdefault('departamento', i)
        elif 'genero' in h or 'género' in h or 'sexo' in h:
            idx.setdefault('genero', i)
        elif h == 'edad' or h.startswith('edad'):
            idx.setdefault('edad', i)
        elif h == 'curso' or h.startswith('curso'):
            idx.setdefault('curso', i)
        elif h in ('cliente', 'organizacion', 'organización', 'empresa', 'org'):
            idx.setdefault('cliente', i)
        elif 'cliente' in h or 'organiz' in h:
            idx.setdefault('cliente', i)

    # Mínimo útil: documento + nombre + teléfono localizados
    if 'documento' in idx and 'nombre' in idx and 'telefono' in idx:
        return idx
    return None


def celda(row, i: int | None) -> str:
    if i is None or i < 0 or i >= len(row):
        return ''
    return celda_excel_a_texto(row[i])


def extraer_fila_estudiante(row, colmap: dict[str, int] | None, tiene_tipo_col: bool) -> dict:
    """Extrae campos; corrige Nombre↔Teléfono si vienen intercambiados."""
    if colmap:
        tipo_raw = celda(row, colmap.get('tipo'))
        cedula = celda(row, colmap.get('documento'))
        nombre = celda(row, colmap.get('nombre'))
        telefono_raw = celda(row, colmap.get('telefono'))
        municipio = celda(row, colmap.get('municipio'))
        departamento = celda(row, colmap.get('departamento'))
        genero_raw = celda(row, colmap.get('genero'))
        edad_raw = celda(row, colmap.get('edad'))
        curso_nombre = celda(row, colmap.get('curso'))
        cliente_nombre = celda(row, colmap.get('cliente'))
    elif tiene_tipo_col:
        tipo_raw = celda(row, 0)
        cedula = celda(row, 1)
        nombre = celda(row, 2)
        telefono_raw = celda(row, 3)
        municipio = celda(row, 4)
        departamento = celda(row, 5)
        genero_raw = celda(row, 6)
        edad_raw = celda(row, 7)
        curso_nombre = celda(row, 8)
        cliente_nombre = celda(row, 9)
    else:
        tipo_raw = celda(row, 9) if len(row) > 9 else ''
        cedula = celda(row, 0)
        nombre = celda(row, 1)
        telefono_raw = celda(row, 2)
        municipio = celda(row, 3)
        departamento = celda(row, 4)
        genero_raw = celda(row, 5)
        edad_raw = celda(row, 6)
        curso_nombre = celda(row, 7)
        cliente_nombre = celda(row, 8)

    # Swap clásico: columnas Nombre y Teléfono al revés
    if parece_nombre_persona(telefono_raw) and parece_telefono(nombre):
        nombre, telefono_raw = telefono_raw, nombre
    elif parece_nombre_persona(telefono_raw) and not parece_telefono(telefono_raw):
        # Buscar un teléfono real en la fila
        for cell in row:
            if parece_telefono(cell) and not parece_nombre_persona(cell):
                telefono_raw = celda_excel_a_texto(cell)
                break
        # Si el "documento" parece nombre y hay un doc-like en otra celda, no tocamos aquí

    # Si nombre quedó vacío pero hay texto tipo nombre en otra celda útil
    if not nombre and parece_nombre_persona(cedula) and parece_telefono(telefono_raw):
        # caso raro: doc col tiene nombre — no auto-fix sin más señales
        pass

    return {
        'tipo_raw': tipo_raw,
        'cedula': cedula,
        'nombre': nombre,
        'telefono_raw': telefono_raw,
        'municipio': municipio,
        'departamento': departamento,
        'genero_raw': genero_raw,
        'edad_raw': edad_raw,
        'curso_nombre': curso_nombre,
        'cliente_nombre': cliente_nombre,
        'telefono_normalizado': normalizar_telefono(telefono_raw),
    }
