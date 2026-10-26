"""WhatsappLog sin estudiante se asocia por teléfono al guardarse."""
from django.test import TestCase

from core.models import Estudiante, WhatsappLog


class WhatsappLogAsociaEstudianteTests(TestCase):
    def setUp(self):
        self.est = Estudiante.objects.create(
            cedula='LOGEST1', nombre='Rosa', telefono='573001112233',
        )

    def test_log_sin_estudiante_toma_el_del_telefono(self):
        log = WhatsappLog.objects.create(telefono='573001112233', mensaje='hola', tipo='INCOMING')
        self.assertEqual(log.estudiante_id, self.est.id)

    def test_variantes_del_mismo_numero_se_asocian(self):
        for tel in ('+573001112233', '3001112233', 'whatsapp:+573001112233'):
            log = WhatsappLog.objects.create(telefono=tel, mensaje='hola', tipo='INCOMING')
            self.assertEqual(log.estudiante_id, self.est.id, tel)

    def test_telefono_desconocido_queda_sin_estudiante(self):
        log = WhatsappLog.objects.create(telefono='573009990000', mensaje='hola', tipo='INCOMING')
        self.assertIsNone(log.estudiante_id)

    def test_estudiante_explicito_no_se_reemplaza(self):
        otro = Estudiante.objects.create(cedula='LOGEST2', nombre='Otro', telefono='573004445566')
        log = WhatsappLog.objects.create(
            telefono='573001112233', mensaje='hola', tipo='OUTGOING', estudiante=otro,
        )
        self.assertEqual(log.estudiante_id, otro.id)

    def test_log_sin_telefono_se_guarda(self):
        log = WhatsappLog.objects.create(telefono='', mensaje='hola', tipo='INCOMING')
        self.assertIsNone(log.estudiante_id)
