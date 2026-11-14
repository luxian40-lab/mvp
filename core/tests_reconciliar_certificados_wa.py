"""C4 dry-run + C5 backfill con guards."""
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone


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
            codigo_verificacion='eki-C4AA-BBBB-CCCC',
        )
        self.log = WhatsappLog.objects.create(
            telefono=self.est.telefono,
            mensaje=(
                '🎓 *¡Tu certificado!*\n'
                'https://eki-produccion.s3.amazonaws.com/certificados/generados/'
                'certificado_eki-C4AA-BBBB-CCCC.png'
            ),
            tipo='SENT',
            estado='delivered',
            mensaje_id='wamid.C4',
            estudiante=self.est,
            agente_usado='diploma_meta',
        )

    def test_dry_run_lista_y_no_escribe(self):
        out = StringIO()
        call_command(
            'reconciliar_certificados_wa',
            '--dias', '30',
            '--cliente-id', str(self.cli.id),
            stdout=out,
        )
        texto = out.getvalue()
        self.assertIn('dry_run=1', texto)
        self.assertIn(f'cert_id={self.cert.id}', texto)
        self.cert.refresh_from_db()
        self.assertFalse(self.cert.enviado_whatsapp)

    def test_sin_log_diploma_no_lista(self):
        from core.models import WhatsappLog

        WhatsappLog.objects.all().delete()
        out = StringIO()
        call_command(
            'reconciliar_certificados_wa',
            '--dias', '30',
            '--cliente-id', str(self.cli.id),
            stdout=out,
        )
        self.assertNotIn(f'cert_id={self.cert.id}', out.getvalue())

    @override_settings(EKI_RECONCILIA_CERT_WA_APLICAR=False)
    def test_aplicar_sin_flag_falla(self):
        with self.assertRaises(CommandError):
            call_command(
                'reconciliar_certificados_wa',
                '--aplicar',
                '--cliente-id', str(self.cli.id),
                '--limite', '5',
            )

    @override_settings(EKI_RECONCILIA_CERT_WA_APLICAR=True)
    def test_aplicar_marca_flag(self):
        out = StringIO()
        call_command(
            'reconciliar_certificados_wa',
            '--aplicar',
            '--cliente-id', str(self.cli.id),
            '--limite', '20',
            '--dias', '30',
            stdout=out,
        )
        self.cert.refresh_from_db()
        self.assertTrue(self.cert.enviado_whatsapp)
        self.assertIn('aplicado', out.getvalue())

    @override_settings(EKI_RECONCILIA_CERT_WA_APLICAR=True)
    def test_131047_no_marca(self):
        self.log.estado = 'failed'
        self.log.mensaje = '🎓 *¡Tu certificado!* 131047'
        self.log.save(update_fields=['estado', 'mensaje'])
        call_command(
            'reconciliar_certificados_wa',
            '--aplicar',
            '--cliente-id', str(self.cli.id),
            '--limite', '20',
            stdout=StringIO(),
        )
        self.cert.refresh_from_db()
        self.assertFalse(self.cert.enviado_whatsapp)

    @override_settings(EKI_RECONCILIA_CERT_WA_APLICAR=True)
    def test_aplicar_sin_cliente_falla(self):
        with self.assertRaises(CommandError):
            call_command(
                'reconciliar_certificados_wa',
                '--aplicar',
                '--limite', '5',
            )
