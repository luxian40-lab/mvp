"""Contrato visual Pulso (slices 1–2): jerarquía KPI quiet y gamificación fuera del glance."""
from pathlib import Path

from django.test import SimpleTestCase

TEMPLATE = (
    Path(__file__).resolve().parent / 'templates' / 'admin' / 'dashboard.html'
)


def _pulso_block(html: str) -> str:
    start = html.index('id="tab-resumen"')
    end = html.index('<!-- ===== LEARNING: REPORTES B2B ===== -->', start)
    return html[start:end]


class PulsoVisualSlices12Tests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.html = TEMPLATE.read_text(encoding='utf-8')
        cls.pulso = _pulso_block(cls.html)

    def _kpi_grid(self) -> str:
        return self.pulso.split('pulso-kpi__grid', 1)[1].split('id="pulso-progreso"', 1)[0]

    def test_kpi_strip_tiene_cinco_cards_quiet(self):
        grid = self._kpi_grid()
        self.assertEqual(grid.count('class="m-card"'), 5)
        self.assertNotIn('m-card green', grid)
        self.assertNotIn('m-card orange', grid)
        self.assertNotIn('m-card blue', grid)
        self.assertNotIn('m-card red', grid)

    def test_kpi_tienen_tooltip_de_definicion(self):
        for kpi_id in (
            'kpi-total-estudiantes',
            'kpi-tasa-completacion',
            'kpi-total-certificados',
            'kpi-nps',
            'kpi-total-clientes',
        ):
            self.assertIn(f'id="{kpi_id}"', self.pulso)
        grid = self._kpi_grid()
        self.assertGreaterEqual(grid.count('title="'), 5)

    def test_nps_esta_en_kpi_y_cursos_en_mas_datos(self):
        grid = self._kpi_grid()
        self.assertIn('kpi-nps', grid)
        self.assertNotIn('kpi-total-cursos', grid)
        self.assertIn('kpi-total-cursos', self.pulso)

    def test_leads_b2b_no_esta_en_el_kpi_strip(self):
        grid = self._kpi_grid()
        self.assertNotIn('kpi-total-prospectos', grid)
        self.assertIn('kpi-total-prospectos', self.pulso)

    def test_progreso_por_curso_esta_antes_de_mas_datos(self):
        progreso_at = self.pulso.index('id="pulso-progreso"')
        details_at = self.pulso.index('id="pulso-mas-datos"')
        self.assertLess(progreso_at, details_at)

    def test_gamificacion_vive_dentro_de_details_cerrado(self):
        marker = self.pulso.index('id="pulso-mas-datos"')
        details_open = self.pulso.rfind('<details', 0, marker)
        details_tag_end = self.pulso.index('>', details_open) + 1
        details_tag = self.pulso[details_open:details_tag_end]
        self.assertEqual(details_tag, '<details class="pulso-mas-datos">')
        details_body = self.pulso[marker:]
        self.assertIn('Top 10 Gamificación', details_body)
        self.assertIn('ranking_gamificacion_completo', details_body)

    def test_acento_kpi_usa_token_de_tono(self):
        self.assertIn('--color-primary-600', self.html)
        self.assertIn('.pulso-kpi .m-card', self.html)

    def test_empty_progreso_quiet(self):
        self.assertIn('pulso-empty-cell', self.pulso)
        self.assertIn('Sin datos en el filtro', self.pulso)


class DashboardDefaultTabSlice5TemplateTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.html = TEMPLATE.read_text(encoding='utf-8')

    def test_header_copy_una_linea_sin_duplicar_inicio(self):
        self.assertIn('Profundidad por dominio:', self.html)
        self.assertNotIn('Inicio = pulso del día', self.html)

    def test_js_fallback_tab_es_learning(self):
        self.assertIn("|| 'learning'", self.html)
        self.assertNotIn("|| 'executive'", self.html)
        self.assertIn("tab || 'learning'", self.html)

    def test_learning_es_primera_pestana(self):
        nav = self.html.split('class="tab-nav"', 1)[1].split('id="learning-sub-nav"', 1)[0]
        first_btn = nav.index('data-tab="learning"')
        second_btn = nav.index('data-tab="')
        # learning aparece antes que cualquier otra data-tab distinta
        self.assertEqual(first_btn, second_btn)
        self.assertLess(nav.index('data-tab="learning"'), nav.index('data-tab="executive"'))
