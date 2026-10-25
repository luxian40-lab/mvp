"""Los contratos de línea con EKI_CONTEXTO_CONSERVA_CLAVES prendido: mismas respuestas, y las claves de la persona quedan."""
from django.test import override_settings

from core import tests_contrato_estados_motor as motor
from core import tests_contrato_linea_principal as principal
from core.models import Estudiante

CLAVES = {
    'ultimo_push_curso_id': 77,
    'distancia_aliado_m': 12.5,
    'ultimo_match_empleabilidad_fecha': '2026-10-25T00:00:00',
}


def _sembrar(est):
    est.refresh_from_db()
    est.contexto_temporal = {**(est.contexto_temporal or {}), **CLAVES}
    est.save(update_fields=['contexto_temporal'])


@override_settings(EKI_CONTEXTO_CONSERVA_CLAVES=True)
class LineaPrincipalConClavesTests(principal.ContratoLineaPrincipalTests):
    def _hasta_menu(self):
        envios = super()._hasta_menu()
        _sembrar(self.est)
        return envios

    def _claves(self):
        ctx = self._refrescar().contexto_temporal or {}
        return {k: ctx.get(k) for k in CLAVES}

    def test_las_claves_llegan_hasta_el_fin_del_curso(self):
        self.salida.llm_responde(principal.RESPUESTA_LLM)
        self._hasta_reto_final()
        self.assertEqual(self._claves(), CLAVES)
        self.tocar(principal.TEL, 'continuemos', 'Continuar')
        self.assertEqual(self._refrescar().estado_onboarding, 'esperando_respuesta_reto')
        self.assertEqual(self._claves(), CLAVES)
        self.escribir(principal.TEL, 'Primero mido la finca y anoto los gastos cada semana')
        self.assertEqual(self._refrescar().estado_onboarding, 'curso_finalizado')
        self.assertEqual(self._claves(), CLAVES)


@override_settings(EKI_CONTEXTO_CONSERVA_CLAVES=True)
class EstadosMotorConClavesTests(motor.ContratoEstadosMotorTests):
    # El cuerpo del webhook atiende la selección de curso antes del despacho y ahí sigue borrando todo.
    SIN_CLAVES = {'esperando_seleccion_curso'}
    # Con la empleabilidad en pausa, salir del código de aliado suelta las claves de empleabilidad.
    SUELTA = {'esperando_codigo_empleabilidad': {'distancia_aliado_m'}}

    def _estudiante_en(self, estado):
        est = super()._estudiante_en(estado)
        _sembrar(est)
        return est

    def _verificar(self, estado):
        super()._verificar(estado)
        if estado in self.SIN_CLAVES:
            return
        esperadas = {k: v for k, v in CLAVES.items() if k not in self.SUELTA.get(estado, set())}
        for est in Estudiante.objects.filter(cliente=self.org):
            with self.subTest(telefono=est.telefono):
                ctx = est.contexto_temporal or {}
                self.assertEqual({k: ctx.get(k) for k in esperadas}, esperadas)
