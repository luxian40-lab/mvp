"""D1: Contexto/Respuesta del motor y el análisis de ramas que guía cada movimiento."""
import importlib.util
from pathlib import Path

from core.conversacion.contexto import CORTAR, Contexto, Respuesta

RAIZ = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location('variables_libres_rama', RAIZ / 'scripts' / 'variables_libres_rama.py')
rama = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rama)

FUENTE = '''
def cuerpo(post_data):
    estudiante = post_data['e']
    msg_body = post_data['b']
    texto_respuesta = 'no entendí'
    if estudiante.estado == 'corta':
        import re
        limpio = re.sub(' ', '', msg_body)
        if limpio == 'x':
            return
        texto_respuesta = limpio
        enviar(texto_respuesta)
        return
    if estudiante.estado == 'A':
        if msg_body:
            texto_respuesta = msg_body.upper()
        total = sum(n for n in range(3))
    elif estudiante.estado == 'B':
        texto_respuesta = 'b'
    enviar(texto_respuesta)
'''


def _analizar(tmp_path, estado):
    archivo = tmp_path / 'cuerpo.py'
    archivo.write_text(FUENTE, encoding='utf-8')
    return rama.analizar(estado, archivo=archivo, funcion='cuerpo')


def test_contexto_y_respuesta():
    ctx = Contexto(estudiante=None, msg_body='hola', msg_from='+57', telefono_limpio='57')
    assert ctx.locales == {} and ctx.texto_respuesta is None
    assert CORTAR.cortar and CORTAR.texto is None
    assert Respuesta(texto='x') == Respuesta(texto='x', cortar=False)


def test_rama_que_corta_no_sigue_de_largo(tmp_path):
    r = _analizar(tmp_path, 'corta')
    assert r['entradas'] == ['msg_body']
    assert not r['sigue_de_largo']
    assert [v for _, v in r['retornos']] == [None, None]


def test_rama_de_cadena_lee_el_texto_previo_y_lo_deja_de_salida(tmp_path):
    r = _analizar(tmp_path, 'A')
    assert r['entradas'] == ['msg_body', 'texto_respuesta']
    assert r['salidas'] == ['texto_respuesta']
    assert r['sigue_de_largo']


def test_rama_que_asigna_sin_condicion_no_pide_el_texto(tmp_path):
    r = _analizar(tmp_path, 'B')
    assert r['entradas'] == []
    assert r['salidas'] == ['texto_respuesta']


BARRERAS_PENDIENTES = ('CONFIRMANDO_DATOS',)
AGENTES_PENDIENTES = (
    'esperando_respuesta_reto',
    'esperando_respuesta_modulo',
    'esperando_seleccion_curso',
)


def _ramas(estado):
    try:
        return rama.analizar(estado)['candidatas']
    except SystemExit:
        return []


def test_lo_despachado_ya_no_tiene_rama_en_el_cuerpo():
    from core.conversacion.estados.despacho import AGENTES, BARRERAS

    lineas = rama.ARCHIVO.read_text(encoding='utf-8').splitlines()
    despacho = next(i for i, texto in enumerate(lineas, 1) if 'agente_de(estudiante.estado_onboarding)' in texto)
    for estado in BARRERAS:
        assert _ramas(estado) == [], estado
    for estado in AGENTES:
        assert all(linea < despacho for linea in _ramas(estado)), estado
    for estado in BARRERAS_PENDIENTES:
        assert estado not in BARRERAS and _ramas(estado), estado
    for estado in AGENTES_PENDIENTES:
        assert estado not in AGENTES, estado
        assert any(linea > despacho for linea in _ramas(estado)), estado


def test_empleabilidad_en_pausa_cae_a_la_rama_por_defecto():
    from unittest.mock import patch

    from core.conversacion.estados import despacho, empleabilidad

    with patch('core.empleabilidad_pausa.empleabilidad_en_pausa', return_value=True):
        assert despacho.agente_de('esperando_codigo_empleabilidad') is None
    with patch('core.empleabilidad_pausa.empleabilidad_en_pausa', return_value=False):
        assert despacho.agente_de('esperando_codigo_empleabilidad') is empleabilidad.manejar
    assert despacho.agente_de('completado') is None
