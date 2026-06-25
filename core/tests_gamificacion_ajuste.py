"""Tests ajuste manual de gamificación (puntos y notas)."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from core.gamificacion import EvaluacionNotaGamificacion, PerfilGamificacion, TransaccionPuntos
from core.gamificacion_ajuste_service import (
    ajustar_puntos_estudiantes,
    registrar_nota_manual_estudiante,
)
from core.gamificacion_modo import MODO_CALIFICACION, MODO_PUNTOS
from core.models import Cliente, Estudiante

_ADMIN_STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}


class GamificacionAjusteServiceTests(TestCase):
    def setUp(self):
        self.cliente_puntos = Cliente.objects.create(
            nombre='Org Puntos',
            contacto_principal='A',
            email='gp@test.com',
            telefono='573001100001',
            activo=True,
            modo_gamificacion=MODO_PUNTOS,
            usar_gamificacion=True,
        )
        self.cliente_notas = Cliente.objects.create(
            nombre='Org Notas',
            contacto_principal='B',
            email='gn@test.com',
            telefono='573001100002',
            activo=True,
            modo_gamificacion=MODO_CALIFICACION,
            usar_gamificacion=True,
        )
        self.est_p = Estudiante.objects.create(
            cedula='gp1',
            nombre='Est Puntos',
            telefono='573001100011',
            cliente=self.cliente_puntos,
            activo=True,
        )
        self.est_n = Estudiante.objects.create(
            cedula='gn1',
            nombre='Est Notas',
            telefono='573001100022',
            cliente=self.cliente_notas,
            activo=True,
        )
        perfil = PerfilGamificacion.objects.get(estudiante=self.est_p)
        perfil.puntos_totales = 20
        perfil.nivel = 2
        perfil.save(update_fields=['puntos_totales', 'nivel'])

    def test_sumar_puntos_manual(self):
        resultados = ajustar_puntos_estudiantes({self.est_p.pk}, 15, 'Taller presencial', self.cliente_puntos)
        self.assertEqual(len(resultados), 1)
        self.assertEqual(resultados[0]['despues'], 35)
        perfil = PerfilGamificacion.objects.get(estudiante=self.est_p)
        self.assertEqual(perfil.puntos_totales, 35)
        self.assertTrue(
            TransaccionPuntos.objects.filter(perfil=perfil, puntos=15, tipo='BONUS').exists()
        )

    def test_restar_puntos_no_baja_de_cero(self):
        ajustar_puntos_estudiantes({self.est_p.pk}, -100, 'Corrección', self.cliente_puntos)
        perfil = PerfilGamificacion.objects.get(estudiante=self.est_p)
        self.assertEqual(perfil.puntos_totales, 0)
        self.assertTrue(
            TransaccionPuntos.objects.filter(perfil=perfil, puntos=20, tipo='GASTO').exists()
        )

    def test_registrar_nota_manual(self):
        resultado = registrar_nota_manual_estudiante(
            self.est_n.pk,
            '4.5',
            self.cliente_notas,
            detalle='Práctica en campo',
        )
        self.assertEqual(resultado['nota'], 4.5)
        self.assertEqual(EvaluacionNotaGamificacion.objects.filter(estudiante=self.est_n).count(), 1)
        ev = EvaluacionNotaGamificacion.objects.get(estudiante=self.est_n)
        self.assertEqual(ev.tipo, 'manual')
        self.assertEqual(ev.nota, Decimal('4.5'))


class GamificacionAjusteAdminTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            nombre='Org Admin Gamif',
            contacto_principal='A',
            email='ga@test.com',
            telefono='573001100003',
            activo=True,
            modo_gamificacion=MODO_PUNTOS,
            usar_gamificacion=True,
        )
        self.est = Estudiante.objects.create(
            cedula='ga1',
            nombre='Est Admin',
            telefono='573001100033',
            cliente=self.cliente,
            activo=True,
        )
        self.admin = User.objects.create_superuser('gamif_admin', 'ga@test.com', 'pass')
        self.http = Client()

    @override_settings(STORAGES=_ADMIN_STORAGES)
    def test_vista_admin_carga(self):
        self.http.login(username='gamif_admin', password='pass')
        r = self.http.get(f'/admin/gamificacion-ajuste/?cliente={self.cliente.id}')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Sumar o restar puntos')

    @override_settings(STORAGES=_ADMIN_STORAGES)
    def test_post_puntos_desde_admin(self):
        self.http.login(username='gamif_admin', password='pass')
        r = self.http.post('/admin/gamificacion-ajuste/', {
            'cliente': self.cliente.id,
            'action': 'ajustar_puntos',
            'estudiantes': [str(self.est.pk)],
            'delta': '10',
            'motivo': 'Participación taller',
        })
        self.assertEqual(r.status_code, 302)
        perfil = PerfilGamificacion.objects.get(estudiante=self.est)
        self.assertEqual(perfil.puntos_totales, 10)
