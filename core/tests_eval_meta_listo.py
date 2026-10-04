"""POST firmado de Meta: listo no salta una evaluación A–D abierta."""
import hashlib
import hmac
import json
from unittest.mock import patch

from django.test import Client, TestCase, override_settings

from core.models import Curso, Estudiante, Modulo, PasoModulo, ProgresoEstudiante, SeccionModulo
from core.module_steps import entregar_paso_indice, reset_progreso_pasos_modulo
from core.sandbox_menu import MODO_CURSOS

SECRET = 'sekreto-test'
TEL = '573009990088'


def _firma(raw: bytes) -> str:
    digest = hmac.new(SECRET.encode(), raw, hashlib.sha256).hexdigest()
    return f'sha256={digest}'


def _payload():
    return {
        'object': 'whatsapp_business_account',
        'entry': [{
            'id': 'WABA',
            'changes': [{
                'field': 'messages',
                'value': {
                    'messaging_product': 'whatsapp',
                    'metadata': {
                        'display_phone_number': '573009998888',
                        'phone_number_id': '111222333',
                    },
                    'messages': [{
                        'from': TEL,
                        'id': 'wamid.eval-listo',
                        'type': 'text',
                        'text': {'body': 'listo'},
                    }],
                },
            }],
        }],
    }


@override_settings(
    SANDBOX_PROVEEDOR='meta',
    SANDBOX_MENU_ENABLED=True,
    BOT_COMERCIAL_SANDBOX_NUMBER='573009998888',
    WHATSAPP_PHONE_ID='111222333',
    SANDBOX_WHATSAPP_PHONE_ID='111222333',
    WHATSAPP_TOKEN='test-token',
    WHATSAPP_APP_SECRET=SECRET,
    WHATSAPP_REQUIRE_SIGNATURE=True,
    TWILIO_VALIDATE_SIGNATURE=False,
    WEBHOOK_CELERY_ASYNC=False,
    SANDBOX_CELERY_ASYNC=False,
    NAT_WEBHOOK_CELERY_ASYNC=False,
    SECURE_SSL_REDIRECT=False,
)
class EvalAbiertaMetaListoTests(TestCase):
    def test_listo_firmado_pide_letra_y_no_avanza(self):
        from core.models import SandboxCanalSesion

        curso = Curso.objects.create(nombre='Curso eval', descripcion='d', dias_espera_entre_modulos=0)
        modulo = Modulo.objects.create(
            curso=curso, numero=1, titulo='M1', descripcion='d', contenido='c',
        )
        seccion = SeccionModulo.objects.create(modulo=modulo, orden=1, titulo='S')
        PasoModulo.objects.create(
            modulo=modulo,
            seccion=seccion,
            orden=1,
            titulo='Quiz',
            tipo=PasoModulo.TIPO_EVAL_OPC,
            contenido='Elige',
            opciones_json={'A': 'Uno', 'B': 'Dos', 'correcta': 'B'},
        )
        est = Estudiante.objects.create(
            cedula='10990088',
            nombre='Ana Eval',
            telefono=TEL,
            estado_chat='ACTIVO',
            contexto_temporal={'curso_activo_id': curso.id},
        )
        prog = ProgresoEstudiante.objects.create(
            estudiante=est, curso=curso, modulo_actual=modulo,
        )
        reset_progreso_pasos_modulo(prog, save=True)
        entregar_paso_indice(prog, modulo, 1)
        prog.refresh_from_db()
        self.assertTrue(prog.esperando_respuesta_evaluacion_paso)
        paso = prog.paso_actual_modulo
        SandboxCanalSesion.objects.create(telefono=TEL, modo=MODO_CURSOS, habeas_aceptado=True)

        raw = json.dumps(_payload()).encode()
        enviados = []

        def _captura(telefono, texto, **kwargs):
            enviados.append(texto)
            return {'success': True, 'mensaje_id': 'wamid.out', 'response': 'ok'}

        with patch('core.sandbox_canal.enviar_meta', side_effect=_captura), \
                patch('core.sandbox_canal.poner_reaccion_espera'):
            resp = Client().post(
                '/webhook/whatsapp/',
                data=raw,
                content_type='application/json',
                secure=True,
                HTTP_HOST='testserver',
                HTTP_X_HUB_SIGNATURE_256=_firma(raw),
            )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(enviados, enviados)
        self.assertIn('letra', enviados[0].lower())
        prog.refresh_from_db()
        self.assertEqual(prog.paso_actual_modulo, paso)
        self.assertTrue(prog.esperando_respuesta_evaluacion_paso)
