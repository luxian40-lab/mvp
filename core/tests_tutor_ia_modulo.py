from core.tutor_ia_modulo import (
    _es_respuesta_sin_contenido_reto,
    evaluar_reto_facilitador,
)


def test_detector_respuesta_sin_contenido_variantes():
    assert _es_respuesta_sin_contenido_reto("no se")
    assert _es_respuesta_sin_contenido_reto("No sé")
    assert _es_respuesta_sin_contenido_reto("ni idea")
    assert _es_respuesta_sin_contenido_reto("   ")
    assert not _es_respuesta_sin_contenido_reto("Aplicaría MIP y monitoreo semanal")


def test_evaluacion_reto_no_inventa_evidencia_cuando_responde_no_se():
    puntaje, feedback = evaluar_reto_facilitador(
        modulos_cubiertos=[],
        respuesta_estudiante="no se",
        reto_original="¿Cómo diagnosticaría y controlaría la plaga?",
        estudiante_nombre="Juliana",
    )

    assert puntaje == 1
    lower = feedback.lower()
    assert "indicó que no sabía" in lower
    assert "hojas amarillas" not in lower
    assert "mip" not in lower
