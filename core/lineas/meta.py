"""Registro de líneas de producto en WhatsApp Cloud API.

Vacío `META_LINEAS` deja las dos líneas de siempre. Con valor, esa lista
es la única: phone number id, número y nombre, separados por punto y coma.
Twilio no es una línea de este registro. El aula sigue en core.twilio_puerta.
"""
from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings

from core.lineas.perfil import USO_COMPLETA, USO_SOLO_CURSOS, PerfilLinea, perfil_por_uso
from core.nati import normalizar_telefono_whatsapp


@dataclass(frozen=True)
class LineaMeta:
    phone_id: str
    e164: str
    nombre: str
    uso: str = USO_COMPLETA
    waba_id: str = ''
    cliente_id: int | None = None

    @property
    def perfil(self) -> PerfilLinea:
        return perfil_por_uso(self.uso)


def lineas_producto() -> tuple[LineaMeta, ...]:
    if getattr(settings, 'EKI_LINEAS_BD_ENABLED', False):
        de_bd = _lineas_bd()
        if de_bd:
            return de_bd
    explicito = _parsear(getattr(settings, 'META_LINEAS', '') or '')
    if explicito:
        return explicito
    return _lineas_historicas()


def phone_ids() -> tuple[str, ...]:
    vistos: list[str] = []
    for linea in lineas_producto():
        if linea.phone_id and linea.phone_id not in vistos:
            vistos.append(linea.phone_id)
    return tuple(vistos)


def linea_por_phone_id(phone_id: str | None) -> LineaMeta | None:
    buscado = str(phone_id or '').strip()
    if not buscado:
        return None
    for linea in lineas_producto():
        if linea.phone_id == buscado:
            return linea
    return None


def nombre_de_linea(phone_id: str) -> str:
    """Nombre de la línea de ese phone number id; el id si no está en el registro."""
    for linea in lineas_producto():
        if linea.phone_id == phone_id:
            return linea.nombre
    return phone_id or 'desconocida'


def numeros_e164() -> tuple[str, ...]:
    vistos: list[str] = []
    for linea in lineas_producto():
        if linea.e164 and linea.e164 not in vistos:
            vistos.append(linea.e164)
    return tuple(vistos)


def _lineas_bd() -> tuple[LineaMeta, ...]:
    from core.lineas.modelo import filas_activas

    return tuple(
        LineaMeta(phone, normalizar_telefono_whatsapp(e164) if e164 else '', nombre, uso=uso, waba_id=waba, cliente_id=cliente_id)
        for phone, e164, nombre, uso, waba, cliente_id in filas_activas()
    )


def _lineas_historicas() -> tuple[LineaMeta, ...]:
    """Las dos variables que ya están en producción. No agrega una tercera."""
    phone = (
        (getattr(settings, 'SANDBOX_WHATSAPP_PHONE_ID', '') or '').strip()
        or (getattr(settings, 'WHATSAPP_PHONE_ID', '') or '').strip()
    )
    e164 = normalizar_telefono_whatsapp(
        getattr(settings, 'BOT_COMERCIAL_SANDBOX_NUMBER', '') or '14155238886'
    )
    lineas = [LineaMeta(phone, e164, 'Línea principal')]
    phone_2 = (getattr(settings, 'WHATSAPP_PHONE_NUMBER_ID_2', '') or '').strip()
    e164_2 = normalizar_telefono_whatsapp(
        getattr(settings, 'WHATSAPP_NUMERO_2_E164', '') or ''
    )
    if (phone_2 or e164_2) and phone_2 != phone:
        lineas.append(LineaMeta(phone_2, e164_2, 'Línea 2', uso=USO_SOLO_CURSOS))
    return tuple(lineas)


def _parsear(bruto: str) -> tuple[LineaMeta, ...]:
    lineas: list[LineaMeta] = []
    vistos: set[str] = set()
    for trozo in str(bruto or '').split(';'):
        partes = [p.strip() for p in trozo.split('|')]
        if not any(partes):
            continue
        phone = partes[0] if partes else ''
        e164 = normalizar_telefono_whatsapp(partes[1]) if len(partes) > 1 else ''
        nombre = partes[2] if len(partes) > 2 and partes[2] else ''
        if not phone and not e164:
            continue
        clave = phone or e164
        if clave in vistos:
            continue
        vistos.add(clave)
        if not nombre:
            nombre = f'Línea {len(lineas) + 1}'
        marca = partes[3].lower() if len(partes) > 3 else ''
        uso = (
            USO_SOLO_CURSOS
            if marca in ('cursos', 'solo_cursos', 'twilio', 'curso_lineal')
            else USO_COMPLETA
        )
        lineas.append(LineaMeta(phone, e164, nombre, uso=uso))
    return tuple(lineas)
