"""Caracterización mínima de activo_menu antes de partir helpers (H4)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.test import TestCase

from core.conversacion.contexto import CORTAR, Contexto
from core.models import Cliente, Estudiante

TEL = '573009997222'
ESTADOS_AGENTE = [
    'esperando_respuesta_asistente',
    'esperando_respuesta_reto',
    'esperando_respuesta_modulo',
    'esperando_respuesta_pregunta_abierta_final',
    'esperando_nota_cierre',
    'esperando_codigo_empleabilidad',
]


class ActivoMenuCaracterizacionTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(nombre='Org activo menu', activo=True)
        self.est = Estudiante.objects.create(
            cedula='am_1',
            nombre='Activo Menu',
            telefono=TEL,
            cliente=self.cliente,
            activo=True,
            estado_chat='ACTIVO',
            estado_onboarding='completado',
            acepto_terminos=True,
        )

    def _ctx(self, body: str, **est_campos) -> Contexto:
        est = self.est
        for k, v in est_campos.items():
            setattr(est, k, v)
        msg_lower = body.lower().strip()
        return Contexto(
            est,
            body,
            f'whatsapp:+{TEL}',
            TEL,
            locales={'estados_agente': ESTADOS_AGENTE, 'msg_lower': msg_lower},
        )

    def test_mensaje_desconocido_retorna_none(self):
        from core.conversacion.estados import activo_menu

        self.assertIsNone(activo_menu.manejar(self._ctx('continuar')))

    def test_mis_puntos_corta_y_llama_gamificacion(self):
        from core.conversacion.estados import activo_menu

        with patch('core.canal.whatsapp_service.enviar_gamificacion_visual') as gami:
            r = activo_menu.manejar(self._ctx('mis puntos'))
        self.assertIs(r, CORTAR)
        gami.assert_called_once_with(f'whatsapp:+{TEL}', self.est)

    def test_pqrs_llama_soporte_y_salida_turno(self):
        from core.conversacion.estados import activo_menu

        with patch(
            'core.conversacion.security_handler.procesar_solicitud_soporte',
            return_value='TICKET_MENU',
        ) as soporte, patch('core.lineas.salida_turno.enviar_respuesta_turno') as turno:
            r = activo_menu.manejar(self._ctx('pqrs'))
        self.assertIs(r, CORTAR)
        soporte.assert_called_once_with(self.est, 'pqrs', 'menu_ayuda')
        turno.assert_called_once_with(
            f'whatsapp:+{TEL}', 'TICKET_MENU', agente='menu_ayuda',
        )

    def test_corregir_datos_inicia_flujo_y_salida_turno(self):
        from core.conversacion.estados import activo_menu

        with patch(
            'core.conversacion.correccion_datos.iniciar_flujo_correccion',
            return_value='FLUJO_CORR',
        ) as iniciar, patch('core.lineas.salida_turno.enviar_respuesta_turno') as turno:
            r = activo_menu.manejar(self._ctx('corregir datos'))
        self.assertIs(r, CORTAR)
        iniciar.assert_called_once_with(self.est)
        turno.assert_called_once_with(
            f'whatsapp:+{TEL}', 'FLUJO_CORR', agente='correccion_datos',
        )

    def test_menu_sin_agente_construye_texto_y_entrega_turno(self):
        from core.conversacion.estados import activo_menu

        with patch.object(activo_menu, '_texto_reenvio_menu', return_value='MENU_CURSO') as texto, \
                patch.object(activo_menu, '_enviar_reenvio_menu') as enviar:
            r = activo_menu.manejar(self._ctx('menú'))
        self.assertIs(r, CORTAR)
        texto.assert_called_once_with(self.est)
        enviar.assert_called_once_with(f'whatsapp:+{TEL}', TEL, 'MENU_CURSO')

    def test_menu_durante_agente_omite_texto_pero_corta(self):
        from core.conversacion.estados import activo_menu

        with patch.object(activo_menu, '_texto_reenvio_menu') as texto, \
                patch.object(activo_menu, '_enviar_reenvio_menu') as enviar:
            r = activo_menu.manejar(
                self._ctx('hola', estado_onboarding='esperando_respuesta_asistente'),
            )
        self.assertIs(r, CORTAR)
        texto.assert_not_called()
        enviar.assert_not_called()

    def test_sin_curso_devuelve_marcador_continuemos(self):
        from core.conversacion.estados import activo_menu

        vacio = MagicMock()
        vacio.first.return_value = None
        vacio.order_by.return_value = vacio
        with patch('core.models.Curso.objects.filter', return_value=vacio), patch(
            'core.models.ProgresoEstudiante.objects.filter',
            return_value=MagicMock(first=MagicMock(return_value=None)),
        ):
            texto = activo_menu._texto_reenvio_menu(self.est)
        self.assertIn('Aún no tienes un curso asignado', texto)
        self.assertIn('continuar', texto.lower())