"""Captura respuestas Sí/No (y variantes evento) de Campaña Única vía webhook Twilio."""
from __future__ import annotations

import logging
import re
import unicodedata
from datetime import timedelta
from typing import TYPE_CHECKING, Optional

from django.db.models import Count
from django.utils import timezone

if TYPE_CHECKING:
    from .models import CampanaUnica, Estudiante

logger = logging.getLogger(__name__)

VENTANA_RESPUESTA_HORAS = 72

MENSAJE_ACK_SI = '✅ Gracias. Registramos tu respuesta *Sí*.'
MENSAJE_ACK_NO = 'Gracias. Registramos tu respuesta *No*.'


def _fold(s: str) -> str:
    s = (s or '').strip().lower()
    return ''.join(
        c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn'
    )


def extraer_texto_respuesta(post_data: dict, msg_body: str) -> str:
    for key in ('ButtonPayload', 'ButtonText', 'ListId', 'ListTitle'):
        val = (post_data.get(key) or '').strip()
        if val:
            return val
    return (msg_body or '').strip()


def clasificar_respuesta_campana(texto: str) -> Optional[str]:
    """
    Devuelve 'si' | 'no' | None.
    Cubre quick reply Twilio, texto libre y plantillas evento (asistiré / no asistiré).
    """
    raw = (texto or '').strip()
    if not raw:
        return None
    folded = _fold(raw)

    no_exactos = {
        'no', 'n', '2', 'no asistire', 'noasistire', 'no_asistire', 'rechazo',
        'rechazar', 'no asisto', 'no voy', 'no puedo', 'no podre',
    }
    si_exactos = {
        'si', 'yes', 'y', '1', 'asistire', 'acepto', 'confirmo', 'confirmar',
        'asisto', 'voy', 'ok',
    }
    if folded in no_exactos:
        return 'no'
    if folded in si_exactos:
        return 'si'

    if folded.startswith('no_') or re.match(r'^no\b', folded) or 'no asist' in folded:
        return 'no'
    if 'asistir' in folded or folded.startswith('si ') or folded == 's':
        return 'si'
    if folded in ('sí',):
        return 'si'

    return None


def normalizar_telefono(telefono: str) -> str:
    from .export_estudiantes import limpiar_telefono

    t = limpiar_telefono(telefono)
    if len(t) == 10:
        t = f'57{t}'
    return t


def estudiante_en_audiencia_campana(campana: CampanaUnica, estudiante: Estudiante) -> bool:
    if campana.estudiantes.exists():
        return campana.estudiantes.filter(pk=estudiante.pk).exists()
    return (
        estudiante.cliente_id == campana.cliente_id
        and bool(getattr(estudiante, 'activo', True))
    )


def campana_unica_pendiente_respuesta(
    telefono: str,
    estudiante: Estudiante,
) -> Optional[CampanaUnica]:
    from .models import CampanaUnica, RespuestaCampanaUnica

    since = timezone.now() - timedelta(hours=VENTANA_RESPUESTA_HORAS)
    tel = normalizar_telefono(telefono)
    candidatas = (
        CampanaUnica.objects.filter(
            cliente_id=estudiante.cliente_id,
            estado__in=('enviada', 'completada'),
            fecha_envio__gte=since,
        )
        .order_by('-fecha_envio', '-id')
    )
    for campana in candidatas:
        if not estudiante_en_audiencia_campana(campana, estudiante):
            continue
        if RespuestaCampanaUnica.objects.filter(
            campana=campana, numero_telefono=tel
        ).exists():
            continue
        return campana
    return None


def recalcular_estadisticas_campana(campana: CampanaUnica) -> None:
    from .models import CampanaUnica, RespuestaCampanaUnica

    agg = (
        RespuestaCampanaUnica.objects.filter(campana=campana)
        .values('respuesta')
        .annotate(n=Count('id'))
    )
    si = no = 0
    for row in agg:
        if row['respuesta'] == 'si':
            si = row['n']
        elif row['respuesta'] == 'no':
            no = row['n']
    CampanaUnica.objects.filter(pk=campana.pk).update(
        respuestas_si=si,
        respuestas_no=no,
    )


def registrar_respuesta_campana_unica(
    *,
    campana: CampanaUnica,
    telefono: str,
    respuesta: str,
    estudiante: Optional[Estudiante] = None,
    mensaje_sid: str = '',
    texto_crudo: str = '',
) -> bool:
    from .models import RespuestaCampanaUnica

    tel = normalizar_telefono(telefono)
    if respuesta not in ('si', 'no'):
        return False
    obj, created = RespuestaCampanaUnica.objects.get_or_create(
        campana=campana,
        numero_telefono=tel,
        defaults={
            'estudiante': estudiante,
            'respuesta': respuesta,
            'mensaje_sid': (mensaje_sid or '')[:100],
        },
    )
    if not created:
        logger.info(
            '📣 [campana] respuesta duplicada ignorada | campana=%s tel=%s',
            campana.id,
            tel[-6:],
        )
        return False
    recalcular_estadisticas_campana(campana)
    logger.info(
        '📣 [campana] respuesta registrada | campana=%s id=%s resp=%s est=%s raw=%s',
        campana.id,
        obj.id,
        respuesta,
        getattr(estudiante, 'id', None),
        (texto_crudo or '')[:80],
    )
    return True


def intentar_registrar_respuesta_campana_unica(
    *,
    telefono_limpio: str,
    post_data: dict,
    msg_body: str,
    estudiante: Estudiante,
    mensaje_sid: str = '',
) -> Optional[str]:
    """
    Si el mensaje es respuesta a campaña única reciente, la guarda y devuelve texto de ack.
    Si no aplica, devuelve None.
    """
    texto = extraer_texto_respuesta(post_data, msg_body)
    resp = clasificar_respuesta_campana(texto)
    if not resp:
        return None

    campana = campana_unica_pendiente_respuesta(telefono_limpio, estudiante)
    if not campana:
        return None

    ok = registrar_respuesta_campana_unica(
        campana=campana,
        telefono=telefono_limpio,
        respuesta=resp,
        estudiante=estudiante,
        mensaje_sid=mensaje_sid,
        texto_crudo=texto,
    )
    if not ok:
        return None
    return MENSAJE_ACK_SI if resp == 'si' else MENSAJE_ACK_NO


def destinatarios_efectivos_qs(campana: CampanaUnica):
    from .models import Estudiante

    if campana.estudiantes.exists():
        return campana.estudiantes.filter(activo=True)
    return Estudiante.objects.filter(cliente=campana.cliente, activo=True)
