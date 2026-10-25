"""contexto_temporal conserva las claves de la persona al cambiar de estado (EKI_CONTEXTO_CONSERVA_CLAVES)."""
from django.test import SimpleTestCase, override_settings

from core.conversacion.claves_contexto import contexto_limpio

CERT = {'certificado_id': 7, 'curso_id': 3, 'ts': '2026-10-25T00:00:00', 'cerrar_avance': False}
ANTES = {
    'tipo': 'reto_facilitador',
    'progreso_id': 9,
    'reto_texto': 'x',
    'curso_activo_id': 3,
    'cert_envio_pendiente': CERT,
    'radar_empleabilidad_activo': True,
    'conteo_ayuda': 2,
}


class ContextoLimpioTests(SimpleTestCase):
    def test_apagado_es_lo_de_siempre(self):
        self.assertIsNone(contexto_limpio(ANTES))
        nuevo = {'tipo': 'pregunta_modulo', 'progreso_id': 9}
        self.assertIs(contexto_limpio(ANTES, nuevo), nuevo)

    @override_settings(EKI_CONTEXTO_CONSERVA_CLAVES=True)
    def test_al_cerrar_quedan_solo_las_claves_de_la_persona(self):
        self.assertEqual(
            contexto_limpio(ANTES),
            {'curso_activo_id': 3, 'cert_envio_pendiente': CERT, 'radar_empleabilidad_activo': True},
        )

    @override_settings(EKI_CONTEXTO_CONSERVA_CLAVES=True)
    def test_al_abrir_el_estado_nuevo_se_suma_y_gana(self):
        nuevo = {'tipo': 'asistente_dario', 'curso_activo_id': 5, 'progreso_id': 10}
        self.assertEqual(
            contexto_limpio(ANTES, nuevo),
            {
                'tipo': 'asistente_dario', 'curso_activo_id': 5, 'progreso_id': 10,
                'cert_envio_pendiente': CERT, 'radar_empleabilidad_activo': True,
            },
        )

    @override_settings(EKI_CONTEXTO_CONSERVA_CLAVES=True)
    def test_sin_nada_que_conservar_queda_vacio(self):
        self.assertIsNone(contexto_limpio({'tipo': 'pregunta_modulo'}))
        self.assertIsNone(contexto_limpio(None))
        self.assertIsNone(contexto_limpio(['no', 'es', 'dict']))
        self.assertEqual(contexto_limpio(None, {'tipo': 'x'}), {'tipo': 'x'})

    @override_settings(EKI_CONTEXTO_CONSERVA_CLAVES=True)
    def test_no_modifica_el_contexto_de_entrada(self):
        antes = dict(ANTES)
        contexto_limpio(antes, {'tipo': 'y'})
        self.assertEqual(antes, ANTES)
