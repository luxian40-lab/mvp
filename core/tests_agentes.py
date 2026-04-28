from core.views import _debe_activar_agentes_reto


def test_curso_6_modulos_activa_en_6():
    assert _debe_activar_agentes_reto(numero_modulo=6, total_modulos=6, usar_agentes_ia_curso=True)


def test_curso_7_modulos_activa_en_6_no_en_7():
    assert _debe_activar_agentes_reto(numero_modulo=6, total_modulos=7, usar_agentes_ia_curso=True)
    assert _debe_activar_agentes_reto(numero_modulo=7, total_modulos=7, usar_agentes_ia_curso=True)


def test_curso_9_modulos_activa_en_6_9():
    assert _debe_activar_agentes_reto(numero_modulo=6, total_modulos=9, usar_agentes_ia_curso=True)
    assert not _debe_activar_agentes_reto(numero_modulo=7, total_modulos=9, usar_agentes_ia_curso=True)
    assert not _debe_activar_agentes_reto(numero_modulo=8, total_modulos=9, usar_agentes_ia_curso=True)
    assert _debe_activar_agentes_reto(numero_modulo=9, total_modulos=9, usar_agentes_ia_curso=True)


def test_curso_5_modulos_no_cambia():
    assert not _debe_activar_agentes_reto(numero_modulo=1, total_modulos=5, usar_agentes_ia_curso=True)
    assert not _debe_activar_agentes_reto(numero_modulo=2, total_modulos=5, usar_agentes_ia_curso=True)
    assert _debe_activar_agentes_reto(numero_modulo=3, total_modulos=5, usar_agentes_ia_curso=True)
    assert _debe_activar_agentes_reto(numero_modulo=5, total_modulos=5, usar_agentes_ia_curso=True)


def test_modulo_3_siempre_activa():
    assert _debe_activar_agentes_reto(numero_modulo=3, total_modulos=10, usar_agentes_ia_curso=True)
