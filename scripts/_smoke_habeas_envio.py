"""Smoke: pone 3026480629 en ESPERANDO_HABEAS_DATA y envía plantilla habeas (botones).

Uso en prod (EB):
  python scripts/_smoke_habeas_envio.py
"""
from __future__ import annotations

import os
import sys

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings')
django.setup()

from core.models import ConfiguracionGlobal, Estudiante
from core.utils_telefono import normalizar_telefono
from core.whatsapp_service import (
    TWILIO_CONTENT_SIDS,
    _resolver_content_sid_habeas_data,
    enviar_habeas_data,
)

TEL = normalizar_telefono(sys.argv[1] if len(sys.argv) > 1 else '3026480629')


def main() -> int:
    est = Estudiante.objects.filter(telefono=TEL).select_related('cliente').first()
    if not est:
        print('ERROR: estudiante no encontrado', TEL)
        return 1

    sid = _resolver_content_sid_habeas_data(cliente=est.cliente)
    cfg = ConfiguracionGlobal.get_solo()
    print('tel', TEL)
    print('estudiante', est.id, est.nombre)
    print('cliente', getattr(est.cliente, 'id', None), getattr(est.cliente, 'nombre', None))
    print('sid_cliente', (getattr(est.cliente, 'content_sid_habeas_data_twilio', '') or '')[:40])
    print('sid_global', (cfg.content_sid_habeas_data_global or '')[:40])
    print('sid_fallback', TWILIO_CONTENT_SIDS['habeas_data'])
    print('sid_usado', sid)
    print('antes', 'estado=', est.estado_chat, 'acepto=', est.acepto_terminos)

    # Dejar listo para probar botones Acepto / No acepto
    est.acepto_terminos = False
    est.fecha_aceptacion_terminos = None
    est.estado_chat = 'ESPERANDO_HABEAS_DATA'
    # No tocar progreso/curso: solo habeas
    est.save(update_fields=['acepto_terminos', 'fecha_aceptacion_terminos', 'estado_chat'])
    print('despues', 'estado=', est.estado_chat, 'acepto=', est.acepto_terminos)

    result = enviar_habeas_data(TEL, cliente=est.cliente)
    print('envio', result)
    if not result.get('success'):
        return 2
    print('OK: revisa WhatsApp. Toca Acepto o No acepto (o escribe el texto).')
    print('Esperado Acepto → pide cédula. Esperado No acepto → mensaje de rechazo.')
    print('Nota QA: si Body="No acepto", hoy puede matchear substring "acepto" (bug).')
    return 0


if __name__ == '__main__':
    sys.exit(main())
