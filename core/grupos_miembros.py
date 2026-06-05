"""Agregar o quitar estudiantes de un grupo sin usar filter_horizontal del admin."""
from __future__ import annotations

import re
from typing import Iterable

from core.models import Estudiante
from core.models_extras import GrupoEstudiantes


def _solo_digitos(val: str) -> str:
    return re.sub(r'\D', '', (val or '').strip())


def _normalizar_telefono(raw: str) -> str:
    tel = _solo_digitos(raw)
    if tel.startswith('57') and len(tel) == 12:
        return tel
    if len(tel) == 10 and tel.startswith('3'):
        return '57' + tel
    if len(tel) in (7, 10):
        return '57' + tel
    return tel


def parsear_lineas_identificadores(texto: str) -> list[str]:
    """Un identificador por línea o separado por coma/punto y coma."""
    if not texto:
        return []
    partes = re.split(r'[\n,;]+', texto)
    return [p.strip() for p in partes if p and p.strip()]


def _qs_estudiantes_grupo(grupo: GrupoEstudiantes):
    qs = Estudiante.objects.filter(activo=True)
    if grupo.cliente_id:
        qs = qs.filter(cliente_id=grupo.cliente_id)
    return qs


def buscar_estudiante_por_identificador(
    grupo: GrupoEstudiantes,
    identificador: str,
    *,
    modo: str = 'auto',
) -> Estudiante | None:
    """Busca por cédula o teléfono (modo auto prueba ambos)."""
    ident = (identificador or '').strip()
    if not ident:
        return None
    qs = _qs_estudiantes_grupo(grupo)

    if modo in ('auto', 'cedula'):
        ced = _solo_digitos(ident) or ident
        est = qs.filter(cedula=ced).first()
        if est or modo == 'cedula':
            return est

    if modo in ('auto', 'telefono'):
        tel = _normalizar_telefono(ident)
        if tel:
            est = qs.filter(telefono=tel).first()
            if est:
                return est
            if len(tel) > 10:
                est = qs.filter(telefono__endswith=tel[-10:]).first()
                if est:
                    return est
    return None


def agregar_miembros_por_identificadores(
    grupo: GrupoEstudiantes,
    identificadores: Iterable[str],
    *,
    modo: str = 'auto',
) -> dict:
    agregados = 0
    ya_estaban = 0
    no_encontrados: list[str] = []

    for ident in identificadores:
        est = buscar_estudiante_por_identificador(grupo, ident, modo=modo)
        if not est:
            no_encontrados.append(ident)
            continue
        if grupo.estudiantes.filter(pk=est.pk).exists():
            ya_estaban += 1
            continue
        grupo.estudiantes.add(est)
        agregados += 1

    return {
        'agregados': agregados,
        'ya_estaban': ya_estaban,
        'no_encontrados': no_encontrados,
    }


def quitar_miembros_por_identificadores(
    grupo: GrupoEstudiantes,
    identificadores: Iterable[str],
    *,
    modo: str = 'auto',
) -> dict:
    quitados = 0
    no_en_grupo: list[str] = []
    no_encontrados: list[str] = []

    for ident in identificadores:
        est = buscar_estudiante_por_identificador(grupo, ident, modo=modo)
        if not est:
            no_encontrados.append(ident)
            continue
        if not grupo.estudiantes.filter(pk=est.pk).exists():
            no_en_grupo.append(ident)
            continue
        grupo.estudiantes.remove(est)
        quitados += 1

    return {
        'quitados': quitados,
        'no_en_grupo': no_en_grupo,
        'no_encontrados': no_encontrados,
    }


def leer_identificadores_desde_excel(archivo, *, columna: str = 'cedula') -> list[str]:
    """Lee cédulas (col A) o teléfonos (col C) de plantilla de importación."""
    import openpyxl

    wb = openpyxl.load_workbook(archivo, data_only=True)
    ws = wb.active
    idx = 0 if columna == 'cedula' else 2
    ids = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row or len(row) <= idx:
            continue
        val = row[idx]
        if val is None or str(val).strip() == '':
            continue
        if isinstance(val, float) and val == int(val):
            ids.append(str(int(val)))
        elif isinstance(val, int):
            ids.append(str(val))
        else:
            ids.append(str(val).strip())
    return ids
