"""Tablero de 12 indicadores en Portal → Impacto. No inventa porcentajes."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from core.models import Cliente, Curso, Estudiante, ProgresoEstudiante, WhatsappLog
from core.models_certificados import Certificado
from portal.impacto import MIN_PUBLICACION, corte_edad, impacto_nucleo
from portal.models import PortalUsuario


def _org(nombre='ImpactoOrg'):
    return Cliente.objects.create(
        nombre=nombre,
        contacto_principal='A',
        email=f'{nombre.lower()}@test.com',
        telefono='573009990100',
        activo=True,
        portal_productos='cursos',
    )


def _est(org, nombre, telefono, **extra):
    datos = dict(
        nombre=nombre,
        cedula=telefono[-8:],
        telefono=telefono,
        cliente=org,
        activo=True,
    )
    datos.update(extra)
    return Estudiante.objects.create(**datos)


@override_settings(SECURE_SSL_REDIRECT=False)
class CorteEdadTests(TestCase):
    def test_joven_14_28_y_mayor_50(self):
        self.assertEqual(corte_edad(14), 'joven')
        self.assertEqual(corte_edad(28), 'joven')
        self.assertEqual(corte_edad(29), 'adulto')
        self.assertEqual(corte_edad(50), 'mayor_50')
        self.assertEqual(corte_edad(None), '')
        self.assertEqual(corte_edad(13), '')


@override_settings(SECURE_SSL_REDIRECT=False)
class ImpactoNucleoTests(TestCase):
    def setUp(self):
        self.org = _org()
        self.otra = _org('OtraOrg')
        self.curso = Curso.objects.create(nombre='Curso impacto', cliente=self.org, activo=True)
        self.ahora = timezone.now()

    def _log(self, est, dias=1):
        fila = WhatsappLog.objects.create(
            telefono=est.telefono,
            mensaje='hola',
            tipo='INCOMING',
            estudiante=est,
        )
        WhatsappLog.objects.filter(pk=fila.pk).update(
            fecha=self.ahora - timedelta(days=dias),
        )

    def test_s1_cuenta_unicos_con_interaccion_y_no_mezcla_org(self):
        ana = _est(self.org, 'Ana', '573001200001', genero='F', edad=22)
        beto = _est(self.org, 'Beto', '573001200002', genero='M', edad=55)
        _est(self.org, 'Cero', '573001200003', genero='F', edad=20)
        ajena = _est(self.otra, 'Ajena', '573001200099', genero='F', edad=22)
        self._log(ana)
        self._log(beto)
        self._log(ajena)
        data = impacto_nucleo(self.org)
        s1 = data['por_codigo']['S1']
        self.assertEqual(s1['numerador'], 2)
        self.assertEqual(s1['denominador'], 2)
        self.assertEqual(s1['evidencia'], 'A')
        self.assertIsNone(s1['cortes']['mujeres']['pct'])
        self.assertEqual(s1['cortes']['mujeres']['n'], 1)
        self.assertIn('n <', s1['cortes']['mujeres']['nota'])

    def test_s1_publica_porcentaje_si_hay_al_menos_10(self):
        for i in range(12):
            est = _est(
                self.org,
                f'P{i}',
                f'573001201{i:03d}',
                genero='F' if i < 7 else 'M',
                edad=20 if i < 7 else 60,
            )
            self._log(est)
        s1 = impacto_nucleo(self.org)['por_codigo']['S1']
        self.assertEqual(s1['numerador'], 12)
        self.assertEqual(s1['cortes']['mujeres']['pct'], round(7 * 100 / 12, 1))
        self.assertEqual(s1['cortes']['jovenes']['n'], 7)
        self.assertEqual(s1['cortes']['mayor_50']['n'], 5)

    def test_s2_usa_inscritos_no_solo_quien_empezo(self):
        inscritos = []
        for i in range(10):
            est = _est(self.org, f'I{i}', f'573001202{i:03d}')
            inscritos.append(est)
            ProgresoEstudiante.objects.create(
                estudiante=est,
                curso=self.curso,
                completado=False,
                fecha_ultimo_avance=self.ahora,
            )
        for est in inscritos[:2]:
            Certificado.objects.create(
                estudiante=est,
                curso=self.curso,
                calificacion_final=Decimal('90.00'),
                fecha_inicio=timezone.localdate(),
                emitido=True,
            )
        s2 = impacto_nucleo(self.org)['por_codigo']['S2']
        self.assertEqual(s2['inscritos'], 10)
        self.assertEqual(s2['certificados'], 2)
        self.assertEqual(s2['pct'], 20.0)
        self.assertEqual(s2['evidencia'], 'A')

    def test_s2_retencion_dia_30(self):
        hace_40 = self.ahora - timedelta(days=40)
        est = _est(self.org, 'Ret', '573001203001')
        prog = ProgresoEstudiante.objects.create(
            estudiante=est, curso=self.curso, completado=False,
        )
        ProgresoEstudiante.objects.filter(pk=prog.pk).update(
            fecha_inicio=hace_40,
            fecha_ultimo_avance=self.ahora - timedelta(days=5),
        )
        s2 = impacto_nucleo(self.org)['por_codigo']['S2']
        self.assertEqual(s2['retencion_30']['denominador'], 1)
        self.assertEqual(s2['retencion_30']['numerador'], 1)

    def test_e3_y_a2_dicen_contribucion(self):
        data = impacto_nucleo(self.org)
        self.assertEqual(data['por_codigo']['E3']['rotulo'], 'contribución')
        self.assertEqual(data['por_codigo']['A2']['rotulo'], 'contribución')
        self.assertEqual(data['por_codigo']['S3']['estado'], 'pendiente_captura')
        self.assertIsNone(data['por_codigo']['S3']['pct'])

    def test_g1_no_usa_el_habeas_operativo(self):
        _est(
            self.org, 'Con', '573001204001',
            acepto_terminos=True, consentimiento_impacto=True,
        )
        _est(
            self.org, 'Sin', '573001204002',
            acepto_terminos=True, consentimiento_impacto=False,
        )
        g1 = impacto_nucleo(self.org)['por_codigo']['G1']
        self.assertEqual(g1['numerador'], 1)
        self.assertEqual(g1['denominador'], 2)
        self.assertIsNone(g1['pct'])
        self.assertTrue(g1['numerador'] and not g1['pct'])

    def test_g2_cuenta_solo_los_que_tienen_valor(self):
        g2 = impacto_nucleo(self.org)['por_codigo']['G2']
        self.assertGreaterEqual(g2['denominador'], 1)
        self.assertEqual(g2['evidencia'], 'A')

    def test_min_publicacion_es_10(self):
        self.assertEqual(MIN_PUBLICACION, 10)


@override_settings(SECURE_SSL_REDIRECT=False)
class ImpactoPortalTests(TestCase):
    def setUp(self):
        self.org = _org('PortalImp')
        user = User.objects.create_user('imp_admin', 'i@t.com', 'pass')
        PortalUsuario.objects.create(user=user, organizacion=self.org, rol='admin')
        self.http = Client()
        self.http.post('/portal/login/', {'username': 'imp_admin', 'password': 'pass'})

    def test_impacto_muestra_los_12_y_no_el_dibujo_viejo(self):
        r = self.http.get('/portal/analitica/?s=impacto')
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn('id="ana-impacto"', html)
        self.assertNotIn('id="ana-impacto" hidden', html)
        self.assertIn('S1', html)
        self.assertIn('Alcance inclusivo', html)
        self.assertIn('G1', html)
        self.assertIn('contribución', html)
        self.assertNotIn('Power skills', html)
        for codigo in ('S1', 'S2', 'S3', 'S4', 'E1', 'E2', 'E3', 'A1', 'A2', 'A3', 'G1', 'G2'):
            self.assertIn(codigo, html)
