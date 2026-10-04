"""Regresión: transcripciones no deben disparar continuar_leccion por subcadenas ('si','seguir','ya')."""

from core.intent_detector import detect_intent, mensaje_indica_listo


def test_prosa_larga_con_si_en_medio_no_es_continuar():
    msg = (
        "casi nunca pienso en el avance de mi sistema de ahorro "
        "pero quiero saber cómo garantizo un ahorro en mi casa"
    )
    assert detect_intent(msg) == "desconocido"


def test_prosa_larga_perseguir_no_dispara_seguir_como_token():
    assert detect_intent("me gustaría perseguir mis metas con constancia cada mes") == "desconocido"


def test_listo_explicito_en_frase_larga_si_es_continuar():
    assert detect_intent("ya terminé el material y estoy listo para continuar con lo siguiente") == (
        "continuar_leccion"
    )


def test_audio_corto_si_sigue_siendo_continuar():
    assert detect_intent("si") == "continuar_leccion"
    assert detect_intent("sí") == "continuar_leccion"


def test_casi_asi_y_listo_con_puntuacion():
    assert detect_intent("casi") != "continuar_leccion"
    assert detect_intent("así") != "continuar_leccion"
    assert detect_intent("asi") != "continuar_leccion"
    assert detect_intent("LISTO!") == "continuar_leccion"
    assert detect_intent("listo ✅") == "continuar_leccion"


def test_no_se_si_seguir_es_ambiguo_pero_seguir_cuenta():
    """«no sé si» justo antes de seguir no avanza."""
    assert detect_intent("no se si seguir") == "desconocido"


def test_negaciones_por_proximidad():
    assert detect_intent("no quiero seguir") == "desconocido"
    assert detect_intent("no puedo continuar") == "desconocido"
    assert detect_intent("ya no sigo") == "desconocido"
    assert detect_intent("nunca termino") == "desconocido"
    assert detect_intent("listo, no tengo dudas") == "continuar_leccion"
    assert detect_intent("listo ya termine, no me falto nada") == "continuar_leccion"
    assert detect_intent("seguir") == "continuar_leccion"
    # La coma separa: «listo» queda en su propia cláusula y sí avanza.
    assert detect_intent("no, listo") == "continuar_leccion"


def test_mensaje_indica_listo_solo_explicito_corto():
    assert mensaje_indica_listo("listo") is True
    assert mensaje_indica_listo("*listo*") is True
    assert mensaje_indica_listo("ya listo") is True
    assert mensaje_indica_listo("Listi") is True
    assert (
        mensaje_indica_listo("ya terminé el material y estoy listo para continuar") is False
    )


def test_mensaje_indica_continuar_explicito_corto():
    assert mensaje_indica_listo("continuar") is True
    assert mensaje_indica_listo("*continuar*") is True
    assert mensaje_indica_listo("ok continuar") is True
    assert mensaje_indica_listo("ya quiero continuar") is True
    assert (
        mensaje_indica_listo("ya terminé el material y quiero continuar con el curso") is False
    )
