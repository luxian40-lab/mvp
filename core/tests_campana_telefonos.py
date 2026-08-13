"""Tests validación teléfono internacional + resumen campaña."""
from __future__ import annotations

import pytest

from core.campana_resultados import revisar_audiencia_campana, resumen_envios_campana
from core.models import Campana, Cliente, EnvioLog, Estudiante
from core.utils_telefono import (
    explicar_error_envio_whatsapp,
    normalizar_telefono,
    validar_telefono_whatsapp,
)


pytestmark = pytest.mark.django_db


def test_co_movil_10_digitos():
    v = validar_telefono_whatsapp('3106077609')
    assert v['ok'] is True
    assert v['telefono'] == '573106077609'
    assert v['severity'] == 'ok'


def test_mx_no_fuerza_colombia():
    v = validar_telefono_whatsapp('5215512345678')
    assert v['ok'] is True
    assert v['telefono'].startswith('52')


def test_exterior_sin_prefijo_falla():
    v = validar_telefono_whatsapp('5512345678')  # 10 dígitos: no asumir BR/MX
    assert v['ok'] is False
    assert 'país' in v['mensaje'].lower() or 'codigo' in v['mensaje'].lower() or 'código' in v['mensaje'].lower()


def test_us_nanp():
    v = validar_telefono_whatsapp('+12025550123')
    assert v['ok'] is True
    assert v['telefono'] == '12025550123'


def test_explicar_63049():
    assert 'marketing' in explicar_error_envio_whatsapp('Error 63049', 'FALLIDO').lower()


def test_normalizar_sigue_latam():
    assert normalizar_telefono('3001234567') == '573001234567'
    assert normalizar_telefono('50371234567') == '50371234567'


def test_revisar_audiencia_y_envios():
    org = Cliente.objects.create(
        nombre='Org Camp',
        contacto_principal='A',
        email='c@test.com',
        telefono='573001111111',
        activo=True,
    )
    ok = Estudiante.objects.create(
        nombre='Ana', telefono='573001234567', cedula='900111', cliente=org,
    )
    bad = Estudiante.objects.create(
        nombre='Bad', telefono='318407546', cedula='900222', cliente=org,
    )
    camp = Campana.objects.create(nombre='Test', cliente=org, tipo_audiencia='individual')
    camp.destinatarios.add(ok, bad)
    aud = revisar_audiencia_campana(camp)
    assert aud['n_ok'] >= 1
    assert aud['n_error'] >= 1

    EnvioLog.objects.create(campana=camp, estudiante=ok, estado='ENVIADO', respuesta_api='SID SM1')
    EnvioLog.objects.create(
        campana=camp, estudiante=bad, estado='FALLIDO', respuesta_api='63049 Meta'
    )
    res = resumen_envios_campana(camp)
    assert res['n_ok'] == 1
    assert res['n_fail'] == 1
    assert res['fail_sample']
