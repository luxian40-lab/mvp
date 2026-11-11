"""NPS de cierre para Analítica admin (slice 3). No toca portal."""
from django.contrib.auth import get_user_model
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from core.analitica.nps_cierre import nps_nota_cierre, nps_por_curso
from core.models import Cliente, Curso, Estudiante, NotaCierreCurso
from core.models_extras import GrupoEstudiantes


class NpsNotaCierreUnitTests(TestCase):
    def setUp(self):
        self.org = Cliente.objects.create(
            nombre='Org NPS',
            contacto_principal='C',
            email='nps@example.com',
            telefono='573009990001',
        )
        self.otra = Cliente.objects.create(
            nombre='Otra',
            contacto_principal='O',
            email='otra@example.com',
            telefono='573009990002',
        )
        self.curso = Curso.objects.create(nombre='Curso NPS', descripcion='d', cliente=self.org)
        self.ests = []
        for i, tel in enumerate(('573001400001', '573001400002', '573001400003', '573001400004'), start=1):
            self.ests.append(
                Estudiante.objects.create(
                    cedula=f'NPS{i:04d}',
                    nombre=f'E{i}',
                    telefono=tel,
                    cliente=self.org,
                    activo=True,
                )
            )
        self.ajeno = Estudiante.objects.create(
            cedula='NPS9999',
            nombre='Ajeno',
            telefono='573001400099',
            cliente=self.otra,
            activo=True,
        )

    def test_sin_notas_nps_es_none(self):
        out = nps_nota_cierre(cliente_id=self.org.id)
        self.assertEqual(out['n'], 0)
        self.assertIsNone(out['nps'])

    def test_fixture_portal_da_nps_25(self):
        # 10, 9, 8, 6 → promotores 2, detractores 1, base 4 → 25
        for est, nota in zip(self.ests, (10, 9, 8, 6)):
            NotaCierreCurso.objects.create(estudiante=est, curso=self.curso, nota=nota)
        NotaCierreCurso.objects.create(estudiante=self.ajeno, curso=self.curso, nota=1)

        out = nps_nota_cierre(cliente_id=self.org.id)
        self.assertEqual(out['n'], 4)
        self.assertEqual(out['nps'], 25)
        self.assertEqual(out['promotores'], 2)
        self.assertEqual(out['detractores'], 1)
        self.assertEqual(out['pasivos'], 1)

    def test_filtro_curso_cambia_la_base(self):
        otro = Curso.objects.create(nombre='Otro', descripcion='d', cliente=self.org)
        NotaCierreCurso.objects.create(estudiante=self.ests[0], curso=self.curso, nota=10)
        NotaCierreCurso.objects.create(estudiante=self.ests[1], curso=otro, nota=1)
        solo = nps_nota_cierre(cliente_id=self.org.id, curso_id=self.curso.id)
        self.assertEqual(solo['n'], 1)
        self.assertEqual(solo['nps'], 100)

    def test_filtro_grupo_y_desglose_call_center(self):
        grupo = GrupoEstudiantes.objects.create(nombre='Cohorte A', cliente=self.org)
        for est, nota in zip(self.ests, (10, 9, 8, 6)):
            NotaCierreCurso.objects.create(estudiante=est, curso=self.curso, nota=nota)
        grupo.estudiantes.add(self.ests[0], self.ests[3])  # 10 y 6 → NPS 0, n=2
        out = nps_nota_cierre(cliente_id=self.org.id, grupo_id=grupo.id)
        self.assertEqual(out['n'], 2)
        self.assertEqual(out['nps'], 0)
        self.assertEqual(out['promotores'], 1)
        self.assertEqual(out['detractores'], 1)
        self.assertEqual(out['pct_promotores'], 50)
        self.assertEqual(out['pct_detractores'], 50)
        self.assertEqual(out['por_nota'][9]['nota'], 10)
        self.assertEqual(out['por_nota'][9]['n'], 1)

    def test_nps_por_curso_lista(self):
        otro = Curso.objects.create(nombre='Otro', descripcion='d', cliente=self.org)
        NotaCierreCurso.objects.create(estudiante=self.ests[0], curso=self.curso, nota=10)
        NotaCierreCurso.objects.create(estudiante=self.ests[1], curso=self.curso, nota=9)
        NotaCierreCurso.objects.create(estudiante=self.ests[2], curso=otro, nota=1)
        filas = nps_por_curso(cliente_id=self.org.id)
        self.assertEqual(len(filas), 2)
        self.assertEqual(filas[0]['nombre'], 'Curso NPS')
        self.assertEqual(filas[0]['n'], 2)
        self.assertEqual(filas[0]['nps'], 100)


@override_settings(SECURE_SSL_REDIRECT=False)
class NpsEnDashboardPulsoTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.staff = User.objects.create_user('nps-staff', password='x', is_staff=True)
        self.client = Client()
        self.client.force_login(self.staff)
        self.org = Cliente.objects.create(
            nombre='Org Dash NPS',
            contacto_principal='C',
            email='dashnps@example.com',
            telefono='573009990011',
        )
        self.curso = Curso.objects.create(nombre='Curso Dash', descripcion='d', cliente=self.org)
        ests = []
        for i, nota in enumerate((10, 9, 8, 6), start=1):
            e = Estudiante.objects.create(
                cedula=f'DN{i:04d}',
                nombre=f'D{i}',
                telefono=f'57300150000{i}',
                cliente=self.org,
                activo=True,
            )
            NotaCierreCurso.objects.create(estudiante=e, curso=self.curso, nota=nota)
            ests.append(e)

    def test_pulso_muestra_nps_en_kpi_y_payload(self):
        url = reverse('dashboard_unificado') + f'?tab=executive&cliente={self.org.id}'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('id="kpi-nps"', html)
        self.assertIn('id="pulso-kpi"', html)
        self.assertContains(resp, '+25')
        payload = resp.context['resumen_payload_json']
        compact = payload.replace(' ', '')
        self.assertIn('"nps":25', compact)
        self.assertIn('"nps_n":4', compact)
        self.assertIn('id="pulso-nps-detalle"', html)
        self.assertIn('id="kpi-nps-promotores"', html)
        self.assertIn('name="grupo"', html)

    def test_embudo_oculta_carrusel_general(self):
        Curso.objects.create(
            nombre='Vitrina Carrusel',
            descripcion='d',
            cliente=None,
            activo=True,
            catalogo_menu=True,
        )
        propio = Curso.objects.create(
            nombre='Cohorte Real',
            descripcion='d',
            cliente=self.org,
            activo=True,
        )
        url = reverse('dashboard_unificado') + '?tab=learning&section=embudo'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        cursos = list(resp.context['cursos'].values_list('nombre', flat=True))
        self.assertIn('Cohorte Real', cursos)
        self.assertNotIn('Vitrina Carrusel', cursos)
        self.assertIn(propio.id, list(resp.context['cursos'].values_list('id', flat=True)))


class PulsoChartsClaimTemplateTests(SimpleTestCase):
    def test_claims_y_empty_states_en_template(self):
        from pathlib import Path

        html = (
            Path(__file__).resolve().parent / 'templates' / 'admin' / 'dashboard.html'
        ).read_text(encoding='utf-8')
        self.assertIn('Tráfico WA del filtro (7 días)', html)
        self.assertIn('Dónde están los estudiantes del filtro', html)
        self.assertIn('id="chartMensajesEmpty"', html)
        self.assertIn('id="chartUbicacionesEmpty"', html)
        self.assertIn('Sin datos en el filtro', html)
