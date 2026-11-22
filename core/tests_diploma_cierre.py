"""C3: limbo reto+cert solo con EKI_RETO_SI_CERT_EMITIDO."""
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from django.utils import timezone

from core.conversacion.contexto import Contexto, Respuesta


class DiplomaCierreTests(TestCase):
    def setUp(self):
        from core.models import Cliente, Curso, Estudiante, ProgresoEstudiante
        from core.certificados.models_certificados import Certificado

        self.cli = Cliente.objects.create(
            nombre='Coop C3',
            nit='900333444-1',
            contacto_principal='Ana',
            email='c3@example.com',
            telefono='573009990201',
            activo=True,
        )
        self.est = Estudiante.objects.create(
            nombre='Lu C3',
            telefono='573009990202',
            cedula='9003334442',
            cliente=self.cli,
            estado_chat='ACTIVO',
            estado_onboarding='esperando_respuesta_reto',
            acepto_terminos=True,
            activo=True,
            contexto_temporal={
                'tipo': 'reto_facilitador',
                'progreso_id': None,
                'reto_texto': 'x',
            },
        )
        self.curso = Curso.objects.create(nombre='Curso C3', cliente=self.cli, activo=True)
        self.prog = ProgresoEstudiante.objects.create(
            estudiante=self.est,
            curso=self.curso,
            completado=True,
            fecha_inicio=timezone.now(),
            fecha_completado=timezone.now(),
        )
        self.est.contexto_temporal['progreso_id'] = self.prog.id
        self.est.save(update_fields=['contexto_temporal'])
        hoy = timezone.now().date()
        self.cert = Certificado.objects.create(
            estudiante=self.est,
            curso=self.curso,
            calificacion_final=100,
            fecha_inicio=hoy,
            fecha_completado=hoy,
            emitido=True,
            enviado_whatsapp=True,
        )

    @override_settings(EKI_RETO_SI_CERT_EMITIDO=False)
    def test_flag_off_no_cierra(self):
        from core.lineas.diploma_cierre import cerrar_limbo_reto_si_cert

        self.assertIsNone(cerrar_limbo_reto_si_cert(self.est, self.prog))
        self.est.refresh_from_db()
        self.assertEqual(self.est.estado_onboarding, 'esperando_respuesta_reto')

    @override_settings(EKI_RETO_SI_CERT_EMITIDO=True)
    def test_flag_on_cierra_y_cta(self):
        from core.lineas.diploma_cierre import cerrar_limbo_reto_si_cert

        texto = cerrar_limbo_reto_si_cert(self.est, self.prog)
        self.assertIn('diploma', texto.lower())
        self.est.refresh_from_db()
        self.assertEqual(self.est.estado_onboarding, 'curso_finalizado')
        self.assertNotEqual(
            (self.est.contexto_temporal or {}).get('tipo'),
            'reto_facilitador',
        )

    @override_settings(EKI_RETO_SI_CERT_EMITIDO=True)
    def test_reto_manejar_corta_con_cert(self):
        from core.conversacion.estados import reto as reto_mod

        ctx = Contexto(
            estudiante=self.est,
            msg_body='hola',
            msg_from='whatsapp:+573009990202',
            telefono_limpio='573009990202',
            msg_sid='SM1',
            texto_respuesta='',
            evidencia_imagen_url='',
            evidencia_imagen_type='',
        )
        out = reto_mod.manejar(ctx)
        self.assertIsInstance(out, Respuesta)
        self.assertIn('diploma', (out.texto or '').lower())
