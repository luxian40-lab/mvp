"""El xfail de CI solo cubre el baseline, no tests vecinos."""
from pathlib import Path

from mvp_project.ci_baseline import (
    REASON,
    baseline_nodeids,
    dotted_to_nodeid,
    parse_baseline_lines,
)

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "scripts" / "baseline_failures_before.txt"


def test_reason_es_el_del_plan():
    assert REASON == "baseline 56929af7"


def test_dotted_funcion_y_clase():
    assert (
        dotted_to_nodeid("core.tests_nati.test_docx_subida_extrae_texto")
        == "core/tests_nati.py::test_docx_subida_extrae_texto"
    )
    assert (
        dotted_to_nodeid(
            "core.tests_module_builder_ui.ModuleBuilderViewTests.test_add_micro_form_accepts_pdf"
        )
        == "core/tests_module_builder_ui.py::ModuleBuilderViewTests::test_add_micro_form_accepts_pdf"
    )


def test_parser_no_inventa_nodeids():
    text = (
        "FAIL: test_x (core.tests_nati.test_docx_subida_extrae_texto)\n"
        "FAILED core/tests_host_isolation.py::AdminNoStudentsTests::test_estudiante_whatsapp_no_es_staff_ni_entra_admin\n"
        "noise sin formato\n"
    )
    got = parse_baseline_lines(text)
    assert got == {
        "core/tests_nati.py::test_docx_subida_extrae_texto",
        "core/tests_host_isolation.py::AdminNoStudentsTests::test_estudiante_whatsapp_no_es_staff_ni_entra_admin",
    }


def test_baseline_real_no_incluye_tests_del_checklist_que_no_fallaban():
    ids = baseline_nodeids(BASELINE)
    assert "core/tests_export_estudiantes.py" not in ids
    assert "portal/tests_branding.py" not in "".join(ids)
    assert any("tests_module_steps.py" in n for n in ids)
    assert all("::" in n and n.endswith(".py") is False for n in ids)
