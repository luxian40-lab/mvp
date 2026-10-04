"""El clasificador de junit separa fallos nuevos, conocidos y los que ya pasan."""
import importlib.util
from pathlib import Path

_RUTA = Path(__file__).resolve().parents[1] / 'scripts' / 'comparar_baseline.py'
_spec = importlib.util.spec_from_file_location('comparar_baseline', _RUTA)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
clasificar = _mod.clasificar


_XML = """<?xml version="1.0" encoding="utf-8"?>
<testsuite>
  <testcase classname="core.tests_a.A" name="test_conocido" file="core/tests_a.py">
    <failure message="AssertionError: viejo">AssertionError: viejo</failure>
  </testcase>
  <testcase classname="core.tests_a.A" name="test_nuevo" file="core/tests_a.py">
    <failure message="AssertionError: nuevo">AssertionError: nuevo</failure>
  </testcase>
  <testcase classname="core.tests_a.A" name="test_xfail" file="core/tests_a.py">
    <skipped type="pytest.xfail" message="baseline"/>
  </testcase>
  <testcase classname="core.tests_a.A" name="test_xpass" file="core/tests_a.py">
    <skipped message="xfail-marked test passes unexpectedly"/>
  </testcase>
  <testcase classname="core.tests_b" name="test_skip" file="core/tests_b.py">
    <skipped type="pytest.skip" message="ffmpeg/ffprobe no instalados"/>
  </testcase>
  <testcase classname="core.tests_a.A" name="test_ok" file="core/tests_a.py"/>
</testsuite>
"""

_BASE = """
FAILED core/tests_a.py::A::test_conocido
FAILED core/tests_a.py::A::test_xfail
FAILED core/tests_a.py::A::test_xpass
"""


def test_separa_nuevos_conocidos_y_los_que_pasan():
    resultado = clasificar(_XML, _BASE)
    assert [nid for nid, _ in resultado['nuevos']] == ['core/tests_a.py::A::test_nuevo']
    assert resultado['nuevos'][0][1] == 'AssertionError: nuevo'
    conocidos = {nid for nid, _ in resultado['conocidos']}
    assert 'core/tests_a.py::A::test_conocido' in conocidos
    assert 'core/tests_a.py::A::test_xfail' in conocidos
    assert resultado['ahora_pasan'] == ['core/tests_a.py::A::test_xpass']
    assert resultado['saltados'] == [
        ('core/tests_b.py::test_skip', 'ffmpeg/ffprobe no instalados'),
    ]
