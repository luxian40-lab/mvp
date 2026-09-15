"""Tests Fase B: taxonomía + clasificador sombra + persistencia señal."""

from django.test import TestCase, override_settings

from core.clasificador_senales import (
    clasificar_consulta_territorial,
    precision_ejemplos_etiquetados,
)
from core.event_engine import correlacionar_clusters
from core.models import AlertaTerritorial, Cliente, Estudiante, SenalTerritorial
from core.senal_shadow import procesar_senal_shadow_nat
from core.taxonomia_senales import EJEMPLOS_ETIQUETADOS


class ClasificadorSenalesTests(TestCase):
    def test_precision_ejemplos_etiquetados_alta(self):
        rep = precision_ejemplos_etiquetados()
        self.assertGreaterEqual(rep['precision'], 0.9, msg=rep['fallos'])
        self.assertEqual(rep['total'], len(EJEMPLOS_ETIQUETADOS))

    def test_salud_bloqueada(self):
        c = clasificar_consulta_territorial('tengo diarrea desde ayer')
        self.assertIsNone(c.tipo)
        self.assertIn('salud', c.motivo)

    def test_roya(self):
        c = clasificar_consulta_territorial('tengo roya en el cafetal')
        self.assertEqual(c.tipo, 'agro.plaga.roya')
        self.assertGreaterEqual(c.confianza, 0.9)


@override_settings(
    SENAL_CLASIFICADOR_ENABLED=True,
    SENAL_PERSISTIR_SENALES=True,
    DATA_LAKE_ENABLED=False,
    ALERTA_TERRITORIAL_MIN_K=3,
    ALERTA_TERRITORIAL_VENTANA_HORAS=72,
)
class SenalShadowPersistTests(TestCase):
    def setUp(self):
        self.org = Cliente.objects.create(
            nombre='Org Shadow',
            contacto_principal='A',
            email='shadow@test.com',
            telefono='3002220001',
            activo=True,
        )
        self.est = Estudiante.objects.create(
            cliente=self.org,
            nombre='Prod Shadow',
            cedula='sh1',
            telefono='573002220001',
            municipio='Medellín',
            departamento='Antioquia',
            territory_id='05001',
            activo=True,
        )

    def test_shadow_persiste_senal_plaga(self):
        senal = procesar_senal_shadow_nat(
            texto='apareció broca en el café',
            telefono=self.est.telefono,
            cliente=self.org,
            estudiante=self.est,
        )
        self.assertIsNotNone(senal)
        self.assertEqual(senal.tipo, 'agro.plaga.broca')
        self.assertEqual(senal.territory_id, '05001')
        self.assertEqual(senal.fuente, 'shadow_rules_v0')
        self.assertTrue(SenalTerritorial.objects.filter(pk=senal.pk).exists())

    def test_shadow_no_persiste_saludo(self):
        senal = procesar_senal_shadow_nat(
            texto='hola nat',
            telefono=self.est.telefono,
            cliente=self.org,
            estudiante=self.est,
        )
        self.assertIsNone(senal)

    def test_cluster_tras_tres_senales(self):
        for i in range(3):
            procesar_senal_shadow_nat(
                texto='tengo roya en el lote',
                telefono=self.est.telefono,
                cliente=self.org,
                estudiante=self.est,
            )
        alertas = correlacionar_clusters(tipo_prefijo='agro.plaga')
        self.assertTrue(alertas)
        self.assertTrue(
            AlertaTerritorial.objects.filter(
                territory_id='05001',
                familia='agro.plaga',
            ).exists()
        )
