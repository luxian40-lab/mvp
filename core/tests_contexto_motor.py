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


def test_el_cuerpo_real_tiene_las_ramas_del_plan():
    for estado in ('ESPERANDO_CEDULA', 'curso_finalizado', 'esperando_respuesta_modulo'):
        assert rama.analizar(estado)['if_linea'] > 0
