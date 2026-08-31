# -*- coding: utf-8 -*-
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase, override_settings

from core.course_engine.costs_nav import (
    PublishedCourseEngineCosts,
    _run_id_from_url,
    course_engine_costs_badge,
)


class RunIdParseTests(TestCase):
    def test_video_url(self):
        url = 'https://eki-produccion.s3.us-east-2.amazonaws.com/media/course_engine/videos/365cc54d20ee.mp4'
        self.assertEqual(_run_id_from_url(url), '365cc54d20ee')

    def test_no_match(self):
        self.assertIsNone(_run_id_from_url('https://example.com/foo.png'))


class CourseEngineCostsBadgeTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_sin_publicados(self):
        snap = PublishedCourseEngineCosts(0, 0, 0.0, 0.0, 0.0, 0, 0)
        with patch('core.course_engine.costs_nav._compute', return_value=snap):
            texto, tono, _ = course_engine_costs_badge()
        self.assertEqual(texto, 'IA cursos $0 · 0 mód. IA')
        self.assertEqual(tono, 'info')

    def test_con_costo_medido(self):
        snap = PublishedCourseEngineCosts(
            n_modulos=2,
            n_con_media=2,
            total_usd=0.52,
            medidos_usd=0.52,
            estimados_usd=0.0,
            n_medidos=2,
            n_estimados=0,
        )
        with patch('core.course_engine.costs_nav._compute', return_value=snap):
            texto, tono, _ = course_engine_costs_badge()
        self.assertIn('$0.52', texto)
        self.assertIn('2 mód.', texto)
        self.assertEqual(tono, 'info')


@override_settings(SECURE_SSL_REDIRECT=False)
class CourseEngineCostsNavHeaderTests(TestCase):
    def test_barra_tiene_chip_ia_cursos(self):
        User.objects.create_user('navstaff2', password='x', is_staff=True, is_superuser=True)
        c = Client()
        c.login(username='navstaff2', password='x')
        snap = PublishedCourseEngineCosts(1, 1, 0.24, 0.24, 0.0, 1, 0)
        with patch(
            'core.course_engine.costs_nav.course_engine_costs_badge',
            return_value=('IA cursos $0.24 · 1 mód.', 'info', snap),
        ):
            r = c.get('/admin/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'eki-ce-costs-nav')
        self.assertContains(r, 'IA cursos $0.24')
