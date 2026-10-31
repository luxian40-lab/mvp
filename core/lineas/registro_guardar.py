"""Guarda el Flow de registro en la ficha del estudiante.

El cliente sale de la marca del Flow, no del formulario. Si la persona ya
pertenece a otro cliente, se queda con ese. No corre para un Flow GEI.
"""
from __future__ import annotations

import json
import logging

from django.db import IntegrityError, transaction
from django.utils import timezone

from core.lineas.registro_enlace import destino_de_token

logger = logging.getLogger(__name__)

_ONBOARDING = frozenset({
    '',
    'nuevo',
    'ESPERANDO_HABEAS_DATA',
    'ESPERANDO_CEDULA',
    'CONFIRMANDO_DATOS',
    'ESPERANDO_AYUDA_MODIFICAR',
    'ESPERANDO_CORRECCION_DATOS',
})


def datos_registro(body: str) -> dict | None:
    """Dict del Flow de registro, o None si este mensaje es otra cosa.

    La marca [FLOW_GEI] es la misma que arma el canal al recibir un Flow.
    """
    bruto = body or ''
    marca = ''
    if bruto.startswith('[FLOW_GEI]'):
        marca = '[FLOW_GEI]'
    elif bruto.startswith('[FLOW_REGISTRO]'):
        marca = '[FLOW_REGISTRO]'
    if not marca:
        return None
    crudo = bruto[len(marca):]
    try:
        datos = json.loads(crudo.strip() or '{}')
    except json.JSONDecodeError:
        return None
    if not isinstance(datos, dict):
        return None
    if destino_de_token(str(datos.get('flow_token') or '')) is None:
        return None
    return datos


def guardar_registro(telefono: str, datos: dict) -> str:
    """Crea o actualiza la ficha. Devuelve el texto que hay que responder."""
    from core.consentimiento_wa import registrar_optin
    from core.documento_identidad import normalizar_numero_documento
    from core.models import Cliente, Estudiante
    from core.nati import normalizar_telefono_whatsapp
    from core.utils_telefono import estudiante_por_telefono

    if not _acepto(datos.get('habeas')):
        return 'Sin la autorización no queda el registro. Abra el formulario y acepte el tratamiento de sus datos.'
    nombre = ' '.join(str(datos.get('nombre') or '').split())[:100]
    cedula = normalizar_numero_documento(str(datos.get('cedula') or ''))[:32]
    municipio = ' '.join(str(datos.get('municipio') or '').split())[:100]
    if not nombre or not cedula:
        return 'Faltó el nombre o la cédula. Abra de nuevo el formulario y envíelos.'
    destino = destino_de_token(str(datos.get('flow_token') or ''))
    cliente = None
    if destino and destino[0] == 'cliente':
        cliente = Cliente.objects.filter(pk=destino[1], activo=True).first()
    tel = normalizar_telefono_whatsapp(telefono)
    por_tel = estudiante_por_telefono(tel)
    por_cedula = Estudiante.objects.filter(cedula__iexact=cedula).first()
    if por_tel is not None and por_cedula is not None and por_tel.pk != por_cedula.pk:
        return 'Esa cédula ya está en otro registro. No la cambié.'
    if por_tel is None and por_cedula is not None and (por_cedula.telefono or '') != tel:
        return 'Esa cédula ya está en otro registro. No la cambié.'
    est = por_tel or por_cedula
    if est is None:
        est = Estudiante(
            telefono=tel,
            cedula=cedula,
            nombre=nombre,
            acepto_terminos=True,
            fecha_aceptacion_terminos=timezone.now(),
            estado_chat='ACTIVO',
            municipio=municipio,
        )
        if cliente is not None:
            est.cliente = cliente
        try:
            with transaction.atomic():
                est.save()
                registrar_optin(est, 'flow_registro')
        except IntegrityError:
            logger.exception('registro_flow_integridad')
            return 'No pude guardar el registro. Inténtelo de nuevo en un momento.'
        return _texto_listo(est, cliente, asignado=cliente is not None)
    campos = []
    if nombre and est.nombre != nombre:
        est.nombre = nombre
        campos.append('nombre')
    if (est.cedula or '').startswith(('TEMP_', 'GEN')) and est.cedula != cedula:
        est.cedula = cedula
        campos.append('cedula')
    if municipio and est.municipio != municipio:
        est.municipio = municipio
        campos.append('municipio')
    if not est.acepto_terminos:
        est.acepto_terminos = True
        est.fecha_aceptacion_terminos = timezone.now()
        campos.extend(['acepto_terminos', 'fecha_aceptacion_terminos'])
    if (est.estado_chat or '') in _ONBOARDING:
        est.estado_chat = 'ACTIVO'
        campos.append('estado_chat')
    asignado = False
    if cliente is not None and est.cliente_id is None:
        est.cliente = cliente
        campos.append('cliente')
        asignado = True
    if campos:
        est.save(update_fields=campos)
    if not est.wa_optin_fecha and not est.wa_optout_fecha:
        registrar_optin(est, 'flow_registro')
    return _texto_listo(est, cliente, asignado=asignado or (cliente is not None and est.cliente_id == getattr(cliente, 'pk', None)))


def responder_registro(telefono: str, body: str) -> str | None:
    """'handled' si este mensaje era el Flow de registro. None en cualquier otro."""
    datos = datos_registro(body)
    if datos is None:
        return None
    texto = guardar_registro(telefono, datos)
    from django.db import DatabaseError

    from core.sandbox_menu import _get_or_create_sesion, enviar_texto_sandbox, sandbox_number

    try:
        sesion = _get_or_create_sesion(telefono)
        if not getattr(sesion, 'habeas_aceptado', False):
            sesion.habeas_aceptado = True
            sesion.save(update_fields=['habeas_aceptado', 'actualizado_en'])
    except DatabaseError:
        logger.exception('registro_flow_sesion')
    enviar_texto_sandbox(telefono, sandbox_number(), texto, agente='registro_flow')
    return 'handled'


def _acepto(valor) -> bool:
    if isinstance(valor, bool):
        return valor
    return str(valor or '').strip().lower() in ('true', '1', 'si', 'sí', 'yes')


def _texto_listo(est, cliente, asignado: bool) -> str:
    if cliente is not None and est.cliente_id == cliente.pk:
        if asignado:
            return f'Listo. Su registro quedó en {cliente.nombre}.'
        return f'Listo. Su registro sigue en {est.cliente.nombre}.'
    if est.cliente_id:
        return f'Listo. Su registro sigue en {est.cliente.nombre}.'
    return 'Listo. Su registro quedó en eki.'
