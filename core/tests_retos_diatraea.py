from core.management.commands.corregir_retos_diatraea import (
    PREGUNTA_DIAGNOSTICO_RECORTADA,
    _corregir_texto_preguntas,
)


def test_corrige_accion_a_acciona():
    texto, cambios = _corregir_texto_preguntas("OBSERVA, CUANTIFICA Y ACCIÓN")
    assert cambios == 1
    assert texto == "ACCIONA"


def test_recorta_pregunta_a_solo_diagnostico():
    original = (
        "¿Cómo podría usted determinar si el mal estado de sus plantas se debe a la Diatraea "
        "y qué medida de control tomaría?"
    )
    texto, cambios = _corregir_texto_preguntas(original)
    assert cambios == 1
    assert texto.strip() == PREGUNTA_DIAGNOSTICO_RECORTADA
