"""Sin opt-in no hay plantilla. Opt-out se respeta. El backfill no inventa fechas."""
from django.test import TestCase

from core.consentimiento_wa import es_optout, puede_recibir_plantilla, registrar_optin, registrar_optout
from core.models import Estudiante


class ConsentimientoTests(TestCase):
    def _est(self, tel):
        return Estudiante.objects.create(nombre='Ana', cedula=tel[-6:], telefono=tel)

    def test_sin_optin_no_hay_plantilla(self):
        est = self._est('573009991001')
        self.assertFalse(puede_recibir_plantilla(est))
        self.assertIsNone(est.wa_optin_fecha)

    def test_optout_inmediato(self):
        est = self._est('573009991002')
        registrar_optin(est, 'habeas')
        self.assertTrue(es_optout('quiero darme de baja'))
        registrar_optout(est)
        est.refresh_from_db()
        self.assertIsNotNone(est.wa_optout_fecha)
        self.assertFalse(puede_recibir_plantilla(est))

    def test_aceptar_no_rellena_a_quien_ya_tenia_habeas_viejo(self):
        est = self._est('573009991003')
        est.acepto_terminos = True
        est.save(update_fields=['acepto_terminos'])
        est.refresh_from_db()
        self.assertIsNone(est.wa_optin_fecha)
        self.assertEqual(est.wa_optin_origen, '')
