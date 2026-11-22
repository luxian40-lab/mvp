"""
Corte 2 — un solo escritor de producto para ProgresoEstudiante.completado.

docs/PLAN_EXPEDIENTE_APRENDIZAJE_EKI.md. Fixtures/tests/management quedan fuera.
"""
from __future__ import annotations

import ast
from pathlib import Path

from django.conf import settings
from django.test import TestCase
from django.utils import timezone

from core.certificados.certificado_presencial_service import cerrar_curso_si_tramo_final
from core.conversacion.progreso_completado import marcar_progreso_curso_completado
from core.models import Cliente, Curso, Estudiante, Modulo, ProgresoEstudiante
from core.selector_curso import continuar_curso_seleccionado

# Raíz de producto donde no se permite asignar completado=True directo.
_CORE = Path(settings.BASE_DIR) / 'core'

# Único módulo de producto autorizado a asignar la bandera.
_ESCRITOR_OK = (_CORE / 'conversacion' / 'progreso_completado.py').resolve()

_EXCLUIR_DIR = {
    'tests',
    'migrations',
    '__pycache__',
}
_EXCLUIR_NOMBRE = {
    # suites / smokes / fixtures
}
_EXCLUIR_PREFIJO = (
    'tests_',
    'test_',
)


def _es_suite_o_ops(path: Path) -> bool:
    name = path.name
    if name.startswith(_EXCLUIR_PREFIJO) or name in _EXCLUIR_NOMBRE:
        return True
    if 'management' in path.parts and 'commands' in path.parts:
        return True
    return False


def _asignaciones_completado(path: Path) -> list[tuple[int, str]]:
    """Líneas con ``…completado = True`` sobre progreso (AST)."""
    src = path.read_text(encoding='utf-8')
    try:
        tree = ast.parse(src, filename=str(path))
    except SyntaxError:
        return [(0, 'syntax_error')]

    hallados: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not isinstance(node.value, ast.Constant) or node.value.value is not True:
            continue
        for target in node.targets:
            if isinstance(target, ast.Attribute) and target.attr == 'completado':
                hallados.append((node.lineno, ast.unparse(target)))
    return hallados


class ExpedienteUnSoloEscritorScanTests(TestCase):
    def test_ningun_modulo_producto_asigna_completado_fuera_del_helper(self):
        ofensores: list[str] = []
        for path in _CORE.rglob('*.py'):
            if any(part in _EXCLUIR_DIR for part in path.parts):
                continue
            if _es_suite_o_ops(path):
                continue
            if path.resolve() == _ESCRITOR_OK:
                continue
            for linea, expr in _asignaciones_completado(path):
                ofensores.append(f'{path.relative_to(_CORE)}:{linea} {expr}')
        self.assertEqual(
            ofensores,
            [],
            'Hay escritores de producto fuera de progreso_completado:\n'
            + '\n'.join(ofensores),
        )


class ExpedienteSelectorSigueSinFechaTests(TestCase):
    """Mismo signal que corte 1: selector cierra sin fecha_completado."""

    def setUp(self):
        self.cli = Cliente.objects.create(nombre='Sel2', activo=True)
        self.curso = Curso.objects.create(
            nombre='Fin sel2', cliente=self.cli, activo=True, dias_espera_entre_modulos=0,
        )
        self.mod = Modulo.objects.create(
            curso=self.curso, numero=1, titulo='Único', descripcion='d', contenido='texto',
            publicado_wa=True,
        )
        self.est = Estudiante.objects.create(
            cedula='EXP-C2-001', nombre='Luis', telefono='573009991501',
            cliente=self.cli, activo=True,
        )
        self.progreso = ProgresoEstudiante.objects.create(
            estudiante=self.est, curso=self.curso, modulo_actual=self.mod, completado=False,
            paso_actual_modulo=2,
        )

    def test_listo_ultimo_modulo_sin_fecha(self):
        continuar_curso_seleccionado(self.est.id, 1, 'listo')
        self.progreso.refresh_from_db()
        self.assertTrue(self.progreso.completado)
        self.assertIsNone(self.progreso.fecha_completado)


class ExpedientePresencialUsaHelperTests(TestCase):
    def setUp(self):
        self.cli = Cliente.objects.create(nombre='Pre2', activo=True)
        self.curso = Curso.objects.create(nombre='WA2', cliente=self.cli, activo=True)
        self.m1 = Modulo.objects.create(
            curso=self.curso, numero=1, titulo='M1', descripcion='d', contenido='c',
            publicado_wa=True,
        )
        self.m2 = Modulo.objects.create(
            curso=self.curso, numero=2, titulo='M2', descripcion='d', contenido='c',
            publicado_wa=True,
        )
        self.est = Estudiante.objects.create(
            cedula='EXP-C2-002', nombre='Pepe', telefono='573009991502',
            cliente=self.cli, activo=True,
        )
        self.progreso = ProgresoEstudiante.objects.create(
            estudiante=self.est, curso=self.curso, modulo_actual=self.m1, completado=False,
        )

    def test_cerrar_tramo_pone_fecha_via_helper(self):
        antes = timezone.now()
        self.assertEqual(cerrar_curso_si_tramo_final(self.est, self.curso), 'cerrado')
        self.progreso.refresh_from_db()
        self.assertTrue(self.progreso.completado)
        self.assertIsNotNone(self.progreso.fecha_completado)
        self.assertGreaterEqual(self.progreso.fecha_completado, antes)
        self.assertEqual(self.progreso.modulo_actual_id, self.m2.id)


class ExpedienteHelperConFechaTests(TestCase):
    def test_default_escribe_fecha(self):
        curso = Curso.objects.create(nombre='H', activo=True)
        est = Estudiante.objects.create(cedula='EXP-C2-003', nombre='A', telefono='573009991503')
        prog = ProgresoEstudiante.objects.create(estudiante=est, curso=curso, completado=False)
        marcar_progreso_curso_completado(prog)
        prog.refresh_from_db()
        self.assertTrue(prog.completado)
        self.assertIsNotNone(prog.fecha_completado)
