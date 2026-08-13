"""Clave propia del estudiante en Aprende (tras *aula* / OTP)."""
from __future__ import annotations

import re
from typing import Optional

from django.db.models import Q

from aprende.models import CredencialAprendeEstudiante
from core.documento_identidad import normalizar_numero_documento
from core.models import Estudiante

SESSION_PENDING_CLAVE = 'aprende_pending_clave_eid'
SESSION_RECUPERAR_CLAVE = 'aprende_recuperar_clave'
MIN_LEN_CLAVE = 6


def tiene_clave(estudiante) -> bool:
    if not estudiante or not getattr(estudiante, 'pk', None):
        return False
    return CredencialAprendeEstudiante.objects.filter(estudiante_id=estudiante.pk).exists()


def guardar_clave(estudiante, raw: str) -> tuple[bool, str]:
    clave = (raw or '').strip()
    if len(clave) < MIN_LEN_CLAVE:
        return False, f'La contraseña debe tener al menos {MIN_LEN_CLAVE} caracteres.'
    if len(clave) > 128:
        return False, 'Contraseña demasiado larga.'
    row, _ = CredencialAprendeEstudiante.objects.get_or_create(estudiante=estudiante)
    row.set_password(clave)
    row.save(update_fields=['password_hash', 'actualizado'])
    return True, ''


def verificar_clave(estudiante, raw: str) -> bool:
    try:
        cred = estudiante.credencial_aprende
    except CredencialAprendeEstudiante.DoesNotExist:
        return False
    return cred.check_password(raw)


def buscar_estudiante_por_documento(documento: str) -> Optional[Estudiante]:
    doc = normalizar_numero_documento(documento or '')
    if not doc:
        return None
    # Match exacto o cédula normalizada
    qs = Estudiante.objects.filter(activo=True).filter(
        Q(cedula__iexact=doc) | Q(cedula__iexact=(documento or '').strip())
    )
    return qs.order_by('-id').first()


def autenticar_documento_clave(documento: str, clave: str) -> tuple[Optional[Estudiante], str]:
    est = buscar_estudiante_por_documento(documento)
    if not est:
        return None, 'No encontramos ese documento. Revisa o pide acceso con *aula* por WhatsApp.'
    if not tiene_clave(est):
        return None, (
            'Aún no tienes contraseña. Escribe *aula* en WhatsApp, entra con el código '
            'y crea tu clave.'
        )
    if not verificar_clave(est, clave):
        return None, 'Documento o contraseña incorrectos.'
    return est, ''


def marcar_pending_clave(request, estudiante_id: int, *, recuperar: bool = False) -> None:
    request.session[SESSION_PENDING_CLAVE] = int(estudiante_id)
    if recuperar:
        request.session[SESSION_RECUPERAR_CLAVE] = True
    else:
        request.session.pop(SESSION_RECUPERAR_CLAVE, None)


def consumir_pending_clave(request) -> Optional[int]:
    eid = request.session.get(SESSION_PENDING_CLAVE)
    if eid is None:
        return None
    try:
        return int(eid)
    except (TypeError, ValueError):
        return None


def limpiar_pending_clave(request) -> None:
    request.session.pop(SESSION_PENDING_CLAVE, None)
    request.session.pop(SESSION_RECUPERAR_CLAVE, None)


def quiere_recuperar(request) -> bool:
    return bool(request.session.get(SESSION_RECUPERAR_CLAVE))
