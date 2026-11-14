"""C4: reconcile dry-run lista drift; no escribe."""
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from io import StringIO


class ReconciliarCertificadosWaTests(TestCase):
    def setUp(self):
        from core.models import Cliente, Curso, Estudiante, WhatsappLog
        from core.models_certificados import Certificado

        self.cli = Cliente.objects.create(
            nombre='Coop C4',
            nit='900444555-1',
            contacto_principal='Ana',
            email='c4@example.com',
            telefono='573009990301',
            activo=True,
        )
        self.est = Estudiante.objects.create(
            nombre='Lu C4',
            telefono='573009990302',
            cedula='9004445552',
            cliente=self.cli,
            estado_chat='ACTIVO',
            acepto_terminos=True,
            activo=True,
        )
        self.curso = Curso.objects.create(nombre='Curso C4', cliente=self.cli, activo=True)
        hoy = timezone.now().date()
        self.cert = Certificado.objects.create(
            estudiante=self.est,
            curso=self.curso,
            calificacion_final=100,
            fecha_inicio=hoy,
            fecha_completado=hoy,
            emitido=True,
            enviado_whatsapp=False,
            fecha_emision=timezone.now(),
        )
        WhatsappLog.objects.create(
            telefono=self.est.telefono,
            mensaje='🎓 *¡Tu certificado!* imagen lista',
            tipo='SENT',
            estado='SENT',
            mensaje_id='wamid.C4',
            estudiante=self.est,
        )

    def test_dry_run_lista_y_no_escribe(self):
        out = StringIO()
        call_command('reconciliar_certificados_wa', '--dias', '30', stdout=out)
        texto = out.getvalue()
        self.assertIn('dry_run=1', texto)
        self.assertIn(f'cert_id={self.cert.id}', texto)
        self.cert.refresh_from_db()
        self.assertFalse(self.cert.enviado_whatsapp)

    def test_sin_log_diploma_no_lista(self):
        from core.models import WhatsappLog

        WhatsappLog.objects.all().delete()
        out = StringIO()
        call_command('reconciliar_certificados_wa', '--dias', '30', stdout=out)
        self.assertNotIn(f'cert_id={self.cert.id}', out.getvalue())
