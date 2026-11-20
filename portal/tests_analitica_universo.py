"""Universo de analítica: sin hooks y cohorte flow_registro cuando existe."""
from django.test import TestCase, override_settings

from core.models import Cliente, Estudiante
from portal.analitica_universo import estudiantes_analitica, telefonos_excluidos_analitica


class AnaliticaUniversoTests(TestCase):
    def setUp(self):
        self.org = Cliente.objects.create(
            nombre='Org flow',
            contacto_principal='A',
            email='flow@test.com',
            telefono='573009990010',
            activo=True,
        )

    def _est(self, nombre, telefono, origen=''):
        return Estudiante.objects.create(
            nombre=nombre,
            cedula=telefono[-6:],
            telefono=telefono,
            cliente=self.org,
            activo=True,
            wa_optin_origen=origen,
        )

    @override_settings(
        EKI_CAMPANA_META_PRUEBA_NUMEROS=['573026480629'],
        EKI_ANALITICA_EXCLUIR_TELEFONOS=['573001110085'],
    )
    def test_excluye_prueba_y_se_queda_con_flow(self):
        real = self._est('Real', '573001110001', 'flow_registro')
        hook = self._est('Hook', '573026480629', 'habeas')
        andres = self._est('Andres', '573001110085', 'flow_registro')
        viejo = self._est('Viejo', '573001110002', 'habeas')
        ids = set(estudiantes_analitica(self.org).values_list('id', flat=True))
        self.assertEqual(ids, {real.id})
        self.assertNotIn(hook.id, ids)
        self.assertNotIn(andres.id, ids)
        self.assertNotIn(viejo.id, ids)
        self.assertIn('573026480629', telefonos_excluidos_analitica())
        self.assertIn('573001110085', telefonos_excluidos_analitica())

    def test_sin_flow_cuenta_activos_menos_prueba(self):
        a = self._est('A', '573001110001', 'habeas')
        b = self._est('B', '573001110002', '')
        with self.settings(EKI_CAMPANA_META_PRUEBA_NUMEROS=['573026480629']):
            hook = self._est('Hook', '3026480629', 'habeas')
            ids = set(estudiantes_analitica(self.org).values_list('id', flat=True))
        self.assertEqual(ids, {a.id, b.id})
        self.assertNotIn(hook.id, ids)
