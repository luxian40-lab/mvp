from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from core.campana_respuestas import (
    clasificar_respuesta_campana,
    intentar_registrar_respuesta_campana_unica,
    recalcular_estadisticas_campana,
    registrar_respuesta_campana_unica,
)
from core.models import CampanaUnica, Cliente, Estudiante, RespuestaCampanaUnica


class ClasificarRespuestaCampanaTests(TestCase):
    def test_si_variantes(self):
        for t in ('si', 'Sí', 'asistiré', 'asistire', 'ASISTIRE', 'acepto', '1'):
            with self.subTest(t=t):
                self.assertEqual(clasificar_respuesta_campana(t), 'si')

    def test_no_variantes(self):
        for t in ('no', 'No asistiré', 'no_asistire', 'no asisto', '2', 'rechazo'):
            with self.subTest(t=t):
                self.assertEqual(clasificar_respuesta_campana(t), 'no')

    def test_no_es_respuesta_campana(self):
        self.assertIsNone(clasificar_respuesta_campana('listo'))
        self.assertIsNone(clasificar_respuesta_campana('hola'))


class RegistrarRespuestaCampanaTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(nombre='Org Campaña')
        self.est = Estudiante.objects.create(
            cedula='900011',
            nombre='Ana Camp',
            telefono='573001112233',
            cliente=self.cliente,
            activo=True,
        )
        self.campana = CampanaUnica.objects.create(
            cliente=self.cliente,
            nombre='Evento test',
            contenido='¿Asistes?',
            template_twilio_id='HXTEST001',
            estado='enviada',
            fecha_envio=timezone.now(),
            total_enviados=1,
        )

    def test_registra_si_y_actualiza_contadores(self):
        ok = registrar_respuesta_campana_unica(
            campana=self.campana,
            telefono='573001112233',
            respuesta='si',
            estudiante=self.est,
            texto_crudo='Asistiré',
        )
        self.assertTrue(ok)
        self.campana.refresh_from_db()
        self.assertEqual(self.campana.respuestas_si, 1)
        self.assertEqual(self.campana.respuestas_no, 0)
        self.assertEqual(RespuestaCampanaUnica.objects.count(), 1)

    def test_duplicado_no_cuenta_dos_veces(self):
        registrar_respuesta_campana_unica(
            campana=self.campana,
            telefono='573001112233',
            respuesta='si',
            estudiante=self.est,
        )
        ok2 = registrar_respuesta_campana_unica(
            campana=self.campana,
            telefono='573001112233',
            respuesta='no',
            estudiante=self.est,
        )
        self.assertFalse(ok2)
        self.campana.refresh_from_db()
        self.assertEqual(self.campana.respuestas_si, 1)

    def test_intentar_webhook_con_button_payload(self):
        ack = intentar_registrar_respuesta_campana_unica(
            telefono_limpio='573001112233',
            post_data={'ButtonPayload': 'no_asistire'},
            msg_body='',
            estudiante=self.est,
            mensaje_sid='SM123',
        )
        self.assertIn('No', ack)
        self.campana.refresh_from_db()
        self.assertEqual(self.campana.respuestas_no, 1)

    def test_sin_campana_reciente_no_intercepta(self):
        self.campana.fecha_envio = timezone.now() - timedelta(days=5)
        self.campana.save()
        ack = intentar_registrar_respuesta_campana_unica(
            telefono_limpio='573001112233',
            post_data={},
            msg_body='si',
            estudiante=self.est,
        )
        self.assertIsNone(ack)

    def test_recalcular_estadisticas(self):
        RespuestaCampanaUnica.objects.create(
            campana=self.campana,
            estudiante=self.est,
            numero_telefono='573001112233',
            respuesta='si',
        )
        self.campana.respuestas_si = 0
        self.campana.save()
        recalcular_estadisticas_campana(self.campana)
        self.campana.refresh_from_db()
        self.assertEqual(self.campana.respuestas_si, 1)
