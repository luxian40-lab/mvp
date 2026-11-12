"""Corte 1b: el diploma HD no se pinta en el turno del chat."""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from django.conf import settings
from django.test import override_settings
from django.utils import timezone

from core.models import Cliente, Curso, Estudiante, ProgresoEstudiante
from core.models_certificados import Certificado


pytestmark = pytest.mark.django_db


def test_flag_default_no_cambia_el_cierre():
    if os.environ.get('EKI_CERTIFICADO_ASYNC'):
        pytest.skip('EKI_CERTIFICADO_ASYNC definido en el entorno')
    assert settings.EKI_CERTIFICADO_ASYNC is False


def _curso_listo():
    """Progreso completado sin disparar el signal (update, no save)."""
    cliente = Cliente.objects.create(
        nombre='Org Async',
        contacto_principal='Dir',
        email='async@test.com',
        telefono='573001200001',
        activo=True,
    )
    curso = Curso.objects.create(
        nombre='Curso Async', descripcion='d', cliente=cliente, activo=True,
    )
    est = Estudiante.objects.create(
        cedula='async1',
        nombre='Estudiante Async',
        telefono='573001200002',
        cliente=cliente,
        estado_chat='ACTIVO',
        activo=True,
    )
    prog = ProgresoEstudiante.objects.create(
        estudiante=est, curso=curso, completado=False,
    )
    ProgresoEstudiante.objects.filter(pk=prog.pk).update(
        completado=True, fecha_completado=timezone.now(),
    )
    prog.refresh_from_db()
    return est, curso, prog


@patch('core.certificado_service.generar_y_guardar_certificado', return_value=True)
@patch('core.tasks.generar_certificado_async.delay')
def test_flag_apagado_pinta_en_el_turno(mock_delay, mock_gen):
    from core.certificado_service import crear_certificado_automatico

    est, curso, _prog = _curso_listo()
    cert = crear_certificado_automatico(est, curso)
    assert cert is not None
    mock_gen.assert_called_once()
    mock_delay.assert_not_called()


@override_settings(EKI_CERTIFICADO_ASYNC=True, CELERY_TASK_ALWAYS_EAGER=False)
@patch('core.certificado_service.generar_y_guardar_certificado', return_value=True)
@patch('core.tasks.generar_certificado_async.delay')
def test_flag_prendido_no_pinta_en_el_turno(mock_delay, mock_gen):
    from core.certificado_service import crear_certificado_automatico

    est, curso, _prog = _curso_listo()
    cert = crear_certificado_automatico(est, curso)
    assert cert is not None
    cert.refresh_from_db()
    assert not cert.archivo_imagen
    mock_gen.assert_not_called()
    mock_delay.assert_called_once_with(cert.id)


@override_settings(EKI_CERTIFICADO_ASYNC=True, CELERY_TASK_ALWAYS_EAGER=False)
@patch('core.certificado_service.generar_y_guardar_certificado', return_value=True)
@patch('core.tasks.generar_certificado_async.delay')
def test_admin_encolar_false_sigue_pintando(mock_delay, mock_gen):
    from core.certificado_service import crear_certificado_automatico

    est, curso, _prog = _curso_listo()
    cert = crear_certificado_automatico(est, curso, encolar=False)
    assert cert is not None
    mock_gen.assert_called_once()
    mock_delay.assert_not_called()


@override_settings(EKI_CERTIFICADO_ASYNC=True, CELERY_TASK_ALWAYS_EAGER=False)
@patch('core.certificado_service.generar_y_guardar_certificado', return_value=True)
@patch('core.tasks.generar_certificado_async.delay')
def test_existente_sin_archivo_reencola(mock_delay, mock_gen):
    from core.certificado_service import crear_certificado_automatico

    est, curso, _prog = _curso_listo()
    existente = Certificado.objects.create(
        estudiante=est,
        curso=curso,
        calificacion_final=100,
        fecha_inicio='2026-01-01',
        fecha_completado='2026-02-01',
    )
    cert = crear_certificado_automatico(est, curso)
    assert cert.id == existente.id
    mock_gen.assert_not_called()
    mock_delay.assert_called_once_with(existente.id)


@override_settings(EKI_CERTIFICADO_ASYNC=True, CELERY_TASK_ALWAYS_EAGER=False)
@patch('core.certificado_service.generar_y_guardar_certificado', return_value=True)
@patch('core.tasks.generar_certificado_async.delay')
def test_signal_con_flag_no_fuerza_sync(mock_delay, mock_gen):
    est, curso, prog = _curso_listo()
    prog.completado = True
    prog.fecha_completado = timezone.now()
    prog.save()
    mock_gen.assert_not_called()
    assert mock_delay.called


@override_settings(EKI_CERTIFICADO_ASYNC=True)
@patch('core.certificado_service.generar_y_guardar_certificado', return_value=True)
def test_turno_no_fuerza_regeneracion_si_async(mock_gen):
    from core.certificado_service import completar_archivo_certificado_si_falta

    est, curso, _prog = _curso_listo()
    cert = Certificado.objects.create(
        estudiante=est,
        curso=curso,
        calificacion_final=100,
        fecha_inicio='2026-01-01',
        fecha_completado='2026-02-01',
    )
    assert completar_archivo_certificado_si_falta(cert) is False
    mock_gen.assert_not_called()


@patch('core.certificado_service.generar_y_guardar_certificado', return_value=True)
def test_turno_sigue_forzando_si_async_apagado(mock_gen):
    from core.certificado_service import completar_archivo_certificado_si_falta

    est, curso, _prog = _curso_listo()
    cert = Certificado.objects.create(
        estudiante=est,
        curso=curso,
        calificacion_final=100,
        fecha_inicio='2026-01-01',
        fecha_completado='2026-02-01',
    )
    assert completar_archivo_certificado_si_falta(cert) is True
    mock_gen.assert_called_once()


@patch('core.certificado_service.enviar_certificado_whatsapp', return_value=True)
@patch('core.certificado_service.generar_y_guardar_certificado', return_value=True)
def test_tarea_genera_con_pipeline_hd_y_envia(mock_gen, mock_enviar):
    from core.tasks import generar_certificado_async

    est, curso, _prog = _curso_listo()
    cert = Certificado.objects.create(
        estudiante=est,
        curso=curso,
        calificacion_final=100,
        fecha_inicio='2026-01-01',
        fecha_completado='2026-02-01',
    )
    assert generar_certificado_async.run(cert.id) is True
    mock_gen.assert_called_once()
    mock_enviar.assert_called_once()
    assert mock_enviar.call_args.args[0].id == cert.id
