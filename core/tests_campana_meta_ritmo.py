"""Bucket, pausa y preflight. No llama a Meta."""
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from core.campana_meta_ritmo import anotar_resultado, paso_bucket, pedir_token, resumen_preflight
from core.models import Estudiante
from core.models_campana_meta import CampanaMeta, PlantillaMeta
from core.tests_support.graph_fake import cuerpo_graph


class _Redis:
    def __init__(self):
        self.valores = {}

    def incr(self, clave):
        self.valores[clave] = int(self.valores.get(clave) or 0) + 1
        return self.valores[clave]

    def get(self, clave):
        return self.valores.get(clave)

    def expire(self, clave, segundos):
        return True

    def delete(self, *claves):
        for clave in claves:
            self.valores.pop(clave, None)


class _RedisBucket:
    def __init__(self):
        self.llamadas = []

    def eval(self, _script, _n, clave, rate, capacity, _ahora, _pedir):
        self.llamadas.append((clave, float(rate), float(capacity)))
        return [1, '0']


@override_settings(WA_META_MPS=20, WA_META_BURST=20, WA_META_MPS_POR_LINEA={'111': 80, '222': 5})
class BucketPorLineaTests(TestCase):
    def _pedir(self, *phone_ids):
        falso = _RedisBucket()
        with patch('core.campana_meta_ritmo._redis', return_value=falso):
            for phone_id in phone_ids:
                self.assertEqual(pedir_token(phone_id), (True, 0.0))
        return falso.llamadas

    @override_settings(WA_META_BUCKET_POR_LINEA=False)
    def test_apagado_todas_las_lineas_comparten_el_bucket_de_hoy(self):
        llamadas = self._pedir('111', '222', '')
        self.assertEqual({c[0] for c in llamadas}, {'eki:wa:bucket:meta'})
        self.assertEqual({(c[1], c[2]) for c in llamadas}, {(20.0, 20.0)})

    @override_settings(WA_META_BUCKET_POR_LINEA=True)
    def test_prendido_cada_linea_tiene_su_bucket_y_su_tope(self):
        llamadas = self._pedir('111', '222')
        self.assertEqual(
            llamadas,
            [('eki:wa:bucket:meta:111', 80.0, 20.0), ('eki:wa:bucket:meta:222', 5.0, 5.0)],
        )

    @override_settings(WA_META_BUCKET_POR_LINEA=True)
    def test_linea_sin_tope_propio_usa_el_general(self):
        self.assertEqual(self._pedir('333'), [('eki:wa:bucket:meta:333', 20.0, 20.0)])

    @override_settings(WA_META_BUCKET_POR_LINEA=True)
    def test_sin_phone_id_sigue_en_el_bucket_de_hoy(self):
        self.assertEqual(self._pedir(''), [('eki:wa:bucket:meta', 20.0, 20.0)])


@override_settings(CAMPANA_PAUSA_TASA_FALLO=0.15, WA_META_MPS=20, META_LIMITE_CONTACTOS_24H=1000)
class RitmoTests(TestCase):
    def test_el_bucket_no_pasa_de_la_capacidad(self):
        tokens, ultimo = 2.0, 0.0
        ok = []
        for _ in range(3):
            paso, _espera, tokens, ultimo = paso_bucket(tokens, ultimo, ultimo, 1, 2)
            ok.append(paso)
        self.assertEqual(ok, [True, True, False])

    def test_pausa_al_pasar_de_quince(self):
        plantilla = PlantillaMeta.objects.create(
            nombre_interno='Aviso ritmo', categoria='UTILITY', idioma='es', cuerpo='Hola',
            estado='APPROVED',
        )
        campana = CampanaMeta.objects.create(nombre='Ritmo', plantilla=plantilla)
        falso = _Redis()
        falso.valores[f'eki:campana:{campana.pk}:n'] = 99
        falso.valores[f'eki:campana:{campana.pk}:fallos'] = 16
        with patch('core.campana_meta_ritmo._redis', return_value=falso):
            self.assertTrue(anotar_resultado(campana, fallo=True, nuevo=True))
        campana.refresh_from_db()
        self.assertTrue(campana.pausada)
        self.assertEqual(campana.pausa_motivo, 'tasa_fallos')

    @patch('core.meta_token.token_invalido', return_value=False)
    def test_preflight_cuenta_optin(self, _token):
        plantilla = PlantillaMeta.objects.create(
            nombre_interno='Aviso pre', categoria='UTILITY', idioma='es', cuerpo='Hola',
            estado='APPROVED',
        )
        campana = CampanaMeta.objects.create(nombre='Pre', plantilla=plantilla)
        est = Estudiante.objects.create(nombre='Ana', cedula='992111', telefono='573009992111')
        est.wa_optin_fecha = timezone.now()
        est.save(update_fields=['wa_optin_fecha'])
        campana.destinatarios.add(est)
        texto = '\n'.join(resumen_preflight(campana))
        self.assertIn('plantilla APPROVED', texto)
        self.assertIn('optin 1 de 1', texto)
        self.assertIn('duracion_estimada_s 0.1', texto)

    @override_settings(WA_META_BUCKET_POR_LINEA=True, WA_META_MPS_POR_LINEA={'222': 5})
    @patch('core.meta_token.token_invalido', return_value=False)
    def test_preflight_estima_con_el_tope_de_la_linea(self, _token):
        plantilla = PlantillaMeta.objects.create(
            nombre_interno='Aviso linea', categoria='UTILITY', idioma='es', cuerpo='Hola',
            estado='APPROVED',
        )
        campana = CampanaMeta.objects.create(nombre='Linea', plantilla=plantilla, phone_number_id='222')
        campana.destinatarios.add(Estudiante.objects.create(nombre='Bea', cedula='992112', telefono='573009992112'))
        self.assertIn('duracion_estimada_s 0.2', '\n'.join(resumen_preflight(campana)))

    def test_graph_falso_cubre_los_modos(self):
        self.assertEqual(cuerpo_graph('ok')[0], 200)
        self.assertEqual(cuerpo_graph('131056')[1]['error']['code'], 131056)
        self.assertEqual(cuerpo_graph('131047')[1]['error']['code'], 131047)
        self.assertEqual(cuerpo_graph('190')[0], 401)
        self.assertEqual(cuerpo_graph('timeout')[1]['error']['code'], 'TIMEOUT')
