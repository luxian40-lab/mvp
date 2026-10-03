"""Candado Redis por teléfono. En CI usa el servicio redis:7."""
from __future__ import annotations

import threading
import time

import pytest
from django.conf import settings
from django.test import SimpleTestCase, override_settings


def _redis_disponible() -> bool:
    try:
        from redis import Redis

        cliente = Redis.from_url(getattr(settings, 'CELERY_BROKER_URL', 'redis://localhost:6379/0'))
        ok = bool(cliente.ping())
        cliente.close()
        return ok
    except Exception:
        return False


def _exige_redis(test):
    if not _redis_disponible():
        test.skipTest('hace falta Redis en localhost:6379')


@override_settings(CELERY_BROKER_URL='redis://localhost:6379/0')
class TelefonoLockTests(SimpleTestCase):
    def test_mismo_telefono_se_excluye(self):
        _exige_redis(self)
        from core.locks import telefono_lock

        orden = []
        listo = threading.Event()

        def primero():
            with telefono_lock('573000000001', timeout=5, blocking_timeout=2):
                orden.append('a-in')
                listo.set()
                time.sleep(0.4)
                orden.append('a-out')

        def segundo():
            listo.wait(2)
            with telefono_lock('573000000001', timeout=5, blocking_timeout=2):
                orden.append('b-in')

        hilos = [threading.Thread(target=primero), threading.Thread(target=segundo)]
        for hilo in hilos:
            hilo.start()
        for hilo in hilos:
            hilo.join(timeout=5)
        self.assertEqual(orden, ['a-in', 'a-out', 'b-in'])

    def test_telefonos_distintos_no_se_bloquean(self):
        _exige_redis(self)
        from core.locks import telefono_lock

        barrera = threading.Barrier(2)

        def entrar(telefono):
            with telefono_lock(telefono, timeout=5, blocking_timeout=1):
                barrera.wait(timeout=2)

        hilos = [
            threading.Thread(target=entrar, args=('573000000011',)),
            threading.Thread(target=entrar, args=('573000000022',)),
        ]
        for hilo in hilos:
            hilo.start()
        for hilo in hilos:
            hilo.join(timeout=4)
        self.assertTrue(all(not hilo.is_alive() for hilo in hilos))

    def test_lock_ocupado_se_procesa_en_un_reintento(self):
        _exige_redis(self)
        celery = pytest.importorskip('celery')
        from celery.exceptions import Retry

        from core.locks import telefono_lock
        from core.tasks import procesar_sandbox_meta_async

        inbound = {
            'From': 'whatsapp:+573000000077',
            'MessageSid': 'wamid.lockretry',
            'Body': 'hola',
        }
        procesado = []
        soltar = threading.Event()
        dentro = threading.Event()

        def sostener():
            with telefono_lock('573000000077', timeout=5, blocking_timeout=1):
                dentro.set()
                soltar.wait(3)

        hilo = threading.Thread(target=sostener)
        hilo.start()
        self.assertTrue(dentro.wait(2))
        try:
            with patch_menu(procesado), patch_espera():
                with self.assertRaises(Retry):
                    procesar_sandbox_meta_async.apply(args=[inbound])
            self.assertEqual(procesado, [])
        finally:
            soltar.set()
            hilo.join(timeout=3)

        with patch_menu(procesado), patch_espera():
            procesar_sandbox_meta_async.apply(args=[inbound], throw=True)
        self.assertEqual(procesado, ['wamid.lockretry'])
        del celery


def patch_menu(procesado):
    from unittest.mock import patch

    def _marca(data):
        procesado.append((data or {}).get('MessageSid'))
        return None

    return patch('core.views._aplicar_sandbox_menu', side_effect=_marca)


def patch_espera():
    from unittest.mock import patch

    return patch('core.locks.LOCK_BLOCKING', 0.3)
