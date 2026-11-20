"""Cabecera del portal: mismo universo que analítica (flow + sin hooks)."""
from django.test import TestCase, override_settings
from django.utils import timezone

from core.models import Cliente, Curso, Estudiante, ProgresoEstudiante
from core.models_certificados import Certificado
from portal.context_processors import _resumen_header_org


@override_settings(
    EKI_CAMPANA_META_PRUEBA_NUMEROS=['573026480629'],
    EKI_ANALITICA_EXCLUIR_TELEFONOS=[],
)
class HeaderStatsUniversoTests(TestCase):
    def setUp(self):
        self.org = Cliente.objects.create(
            nombre='Header Org',
            contacto_principal='A',
            email='header@test.com',
            telefono='573009990020',
            activo=True,
            portal_productos='cursos',
        )
        self.propio = Curso.objects.create(nombre='Propio', cliente=self.org, activo=True)
        self.general = Curso.objects.create(
            nombre='General eki',
            cliente=None,
            catalogo_menu=True,
            activo=True,
        )

    def _est(self, nombre, telefono, origen='flow_registro'):
        return Estudiante.objects.create(
            nombre=nombre,
            cedula=telefono[-6:],
            telefono=telefono,
            cliente=self.org,
            activo=True,
            wa_optin_origen=origen,
        )

    def test_header_usa_cohorte_flow_y_cursos_con_inscripcion(self):
        a = self._est('Ana', '573001220001')
        b = self._est('Beto', '573001220002')
        hook = self._est('Julian', '573026480629', origen='habeas')
        ProgresoEstudiante.objects.create(
            estudiante=a, curso=self.general, completado=False,
            fecha_ultimo_avance=timezone.now(),
        )
        ProgresoEstudiante.objects.create(
            estudiante=b, curso=self.propio, completado=True,
            fecha_ultimo_avance=timezone.now(),
        )
        ProgresoEstudiante.objects.create(
            estudiante=hook, curso=self.propio, completado=True,
            fecha_ultimo_avance=timezone.now(),
        )
        from decimal import Decimal
        from django.utils import timezone as tz

        Certificado.objects.create(
            estudiante=b,
            curso=self.propio,
            calificacion_final=Decimal('90.00'),
            fecha_inicio=tz.localdate(),
            emitido=True,
        )
        Certificado.objects.create(
            estudiante=hook,
            curso=self.propio,
            calificacion_final=Decimal('90.00'),
            fecha_inicio=tz.localdate(),
            emitido=True,
        )
        data = _resumen_header_org(self.org)
        self.assertEqual(data['participantes'], 2)
        self.assertEqual(data['cursos'], 2)
        self.assertEqual(data['certificados'], 1)
        self.assertEqual(data['avance_pct'], 50)
