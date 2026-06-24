"""Google Form / formulario externo → habilitar módulo por estudiante."""

from __future__ import annotations

import re
import unicodedata

from django.db import transaction

from core.models import Estudiante, HabilitacionModuloEstudiante, Modulo
from core.models_extras import EnlaceFormularioExterno, RegistroFormularioExterno


def _solo_digitos(valor: str) -> str:
    return re.sub(r'\D', '', str(valor or ''))


def _normalizar_nombre(valor: str) -> str:
    s = unicodedata.normalize('NFD', (valor or '').lower())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9\s]', '', s).strip()


def _nombres_compatibles(ingresado: str, registrado: str) -> bool:
    """Evita habilitar si el nombre del Form no parece el mismo estudiante."""
    t1 = [w for w in _normalizar_nombre(ingresado).split() if len(w) >= 2]
    t2 = [w for w in _normalizar_nombre(registrado).split() if len(w) >= 2]
    if not t1 or not t2:
        return False
    coincidencias = sum(
        1 for w in t1
        if any(w == r or w in r or r in w for r in t2)
    )
    minimo = max(1, min(2, len(t1), len(t2)))
    return coincidencias >= minimo


def _telefonos_coinciden(a: str, b: str) -> bool:
    da, db = _solo_digitos(a), _solo_digitos(b)
    if not da or not db:
        return False
    if da == db:
        return True
    return da.endswith(db[-10:]) or db.endswith(da[-10:])


def _buscar_por_cedula(qs, cedula_raw: str) -> Estudiante | None:
    cedula = (cedula_raw or '').replace(' ', '')
    if not cedula:
        return None
    est = qs.filter(cedula=cedula).first()
    if est:
        return est
    digits = _solo_digitos(cedula)
    if not digits:
        return None
    for est in qs.filter(cedula__isnull=False):
        if _solo_digitos(est.cedula) == digits:
            return est
    return None


def _buscar_por_telefono(qs, telefono_raw: str) -> Estudiante | None:
    digits = _solo_digitos(telefono_raw)
    if not digits:
        return None
    for est in qs.only('id', 'telefono', 'cedula', 'nombre'):
        if _telefonos_coinciden(est.telefono, digits):
            return est
    return None


def resolver_modulo_enlace(enlace: EnlaceFormularioExterno) -> Modulo | None:
    if enlace.modulo_id:
        mod = enlace.modulo
        if mod.curso_id != enlace.curso_id:
            raise ValueError('El módulo no pertenece al curso del enlace.')
        return mod
    return enlace.curso.modulos.order_by('-numero').first()


def _extraer_payload(payload: dict) -> dict:
    """Normaliza claves del Form / Apps Script."""
    def g(*keys):
        for k in keys:
            v = payload.get(k)
            if v is None or v == '':
                continue
            if isinstance(v, list):
                v = v[0] if v else ''
            return str(v).strip()
        return ''

    return {
        'cedula': g('cedula', 'documento', 'identificacion', 'numero_identificacion'),
        'telefono': g('telefono', 'whatsapp', 'celular', 'movil'),
        'nombre': g('nombre', 'nombre_completo', 'nombre completo'),
    }


def buscar_estudiante_enlace(enlace: EnlaceFormularioExterno, datos: dict) -> tuple[Estudiante | None, str]:
    """
    Busca estudiante según modo de validación.
    Returns (estudiante, error_mensaje).
    """
    qs = Estudiante.objects.filter(cliente=enlace.cliente, activo=True)
    modo = enlace.campo_identificador
    cedula = datos.get('cedula', '')
    telefono = datos.get('telefono', '')
    nombre = datos.get('nombre', '')

    if modo == 'telefono':
        est = _buscar_por_telefono(qs, telefono or datos.get('identificador', ''))
        if est:
            return est, ''
        return None, 'Teléfono no encontrado en este cliente.'

    if modo == 'cedula':
        est = _buscar_por_cedula(qs, cedula or datos.get('identificador', ''))
        if est:
            return est, ''
        return None, 'Cédula no encontrada. Revise que no tenga puntos ni comas.'

    if modo == 'cedula_y_telefono':
        if not cedula or not telefono:
            return None, 'Faltan cédula y teléfono WhatsApp en el envío.'
        est_ced = _buscar_por_cedula(qs, cedula)
        est_tel = _buscar_por_telefono(qs, telefono)
        if not est_ced and not est_tel:
            return None, 'Ni la cédula ni el teléfono coinciden con un estudiante.'
        if not est_ced or not est_tel:
            return None, 'Cédula o teléfono incorrecto — no coinciden con la misma persona.'
        if est_ced.id != est_tel.id:
            return None, 'La cédula y el teléfono pertenecen a personas distintas. Revise los datos.'
        return est_ced, ''

    if modo == 'cedula_y_nombre':
        if not cedula or not nombre:
            return None, 'Faltan cédula y nombre completo en el envío.'
        est = _buscar_por_cedula(qs, cedula)
        if not est:
            return None, 'Cédula no encontrada. Si se equivocó, escriba a soporte.'
        if not _nombres_compatibles(nombre, est.nombre):
            return None, (
                f'El nombre no coincide con nuestros registros ({est.nombre}). '
                'Revise cédula y nombre sin abreviar.'
            )
        return est, ''

    est = _buscar_por_cedula(qs, cedula)
    return (est, '') if est else (None, 'Estudiante no encontrado.')


@transaction.atomic
def habilitar_estudiante_en_modulo(estudiante: Estudiante, curso, modulo: Modulo) -> bool:
    """Activa acceso al módulo sin quitar accesos de otros estudiantes."""
    if modulo.curso_id != curso.id:
        raise ValueError('Módulo fuera del curso.')
    if estudiante.cliente_id != curso.cliente_id:
        raise ValueError('Estudiante fuera del cliente.')

    fila, created = HabilitacionModuloEstudiante.objects.get_or_create(
        estudiante=estudiante,
        curso=curso,
        modulo=modulo,
        defaults={'activo': True},
    )
    if not created and not fila.activo:
        fila.activo = True
        fila.save(update_fields=['activo'])
    return True


def procesar_respuesta_formulario_externo(
    enlace: EnlaceFormularioExterno,
    payload: dict,
) -> dict:
    """
    Procesa POST del webhook.
    Recomendado: {"cedula": "123", "telefono": "573...", "nombre": "..."}
    """
    datos = _extraer_payload(payload or {})
    identificador_log = datos.get('cedula') or datos.get('telefono') or str(payload.get('identificador', ''))

    resultado = {
        'ok': False,
        'mensaje': '',
        'estudiante_id': None,
        'modulo_id': None,
    }

    if not enlace.activo:
        resultado['mensaje'] = 'Enlace inactivo.'
        _registrar(enlace, None, identificador_log, False, resultado['mensaje'], payload)
        return resultado

    modulo = resolver_modulo_enlace(enlace)
    if not modulo:
        resultado['mensaje'] = 'El curso no tiene módulos.'
        _registrar(enlace, None, identificador_log, False, resultado['mensaje'], payload)
        return resultado

    estudiante, error = buscar_estudiante_enlace(enlace, {**datos, **payload})
    if not estudiante:
        resultado['mensaje'] = error or 'Estudiante no encontrado.'
        _registrar(enlace, None, identificador_log, False, resultado['mensaje'], payload)
        return resultado

    try:
        habilitar_estudiante_en_modulo(estudiante, enlace.curso, modulo)
    except ValueError as exc:
        resultado['mensaje'] = str(exc)
        _registrar(enlace, estudiante, identificador_log, False, resultado['mensaje'], payload)
        return resultado

    resultado['ok'] = True
    resultado['estudiante_id'] = estudiante.id
    resultado['modulo_id'] = modulo.id
    resultado['mensaje'] = (
        f'Acceso habilitado: {estudiante.nombre} → M{modulo.numero} {modulo.titulo}'
    )
    _registrar(enlace, estudiante, identificador_log, True, resultado['mensaje'], payload)
    return resultado


def _registrar(enlace, estudiante, identificador, exito, detalle, payload):
    RegistroFormularioExterno.objects.create(
        enlace=enlace,
        estudiante=estudiante,
        identificador_recibido=identificador[:80],
        exito=exito,
        detalle=detalle[:255],
        payload=payload or {},
    )
