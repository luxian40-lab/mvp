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


def test_mensaje_indica_listo_solo_explicito_corto():
    assert mensaje_indica_listo("listo") is True
    assert mensaje_indica_listo("*listo*") is True
    assert mensaje_indica_listo("ya listo") is True
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
