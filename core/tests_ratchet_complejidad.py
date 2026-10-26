"""El freno de complejidad: el código de producto no empeora respecto al baseline."""
import importlib.util
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    'ratchet_complejidad', RAIZ / 'scripts' / 'ratchet_complejidad.py'
)
ratchet = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ratchet)


def _arbol(tmp_path, archivos):
    for rel, codigo in archivos.items():
        ruta = tmp_path / rel
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(codigo, encoding='utf-8')
    return tmp_path


def _funcion(nombre, lineas):
    cuerpo = ''.join(f'    x{i} = {i}\n' for i in range(lineas - 1))
    return f'def {nombre}():\n{cuerpo}'


def test_el_codigo_no_empeora():
    problemas = ratchet.comparar(ratchet.leer_baseline(), ratchet.medir(RAIZ))
    assert not problemas, '\n'.join(problemas)


def test_funcion_nueva_grande_no_pasa(tmp_path):
    raiz = _arbol(tmp_path, {'core/a.py': _funcion('chica', 10)})
    base = ratchet.medir(raiz)
    _arbol(raiz, {'core/b.py': _funcion('enorme', 200)})
    problemas = ratchet.comparar(base, ratchet.medir(raiz))
    assert any('función nueva' in p and 'core/b.py::enorme' in p for p in problemas)


def test_funcion_grande_existente_no_crece(tmp_path):
    raiz = _arbol(tmp_path, {'core/a.py': _funcion('grande', 200)})
    base = ratchet.medir(raiz)
    _arbol(raiz, {'core/a.py': _funcion('grande', 201)})
    problemas = ratchet.comparar(base, ratchet.medir(raiz))
    assert any('función creció' in p for p in problemas)


def test_movimiento_se_acepta_si_el_total_no_sube(tmp_path):
    raiz = _arbol(tmp_path, {'core/a.py': _funcion('grande', 200)})
    base = ratchet.medir(raiz)
    _arbol(raiz, {'core/a.py': '', 'core/conversacion/b.py': _funcion('grande', 200)})
    actual = ratchet.medir(raiz)
    assert ratchet.comparar(base, actual)
    assert not ratchet.comparar(base, actual, aceptar_movimiento=True)


def test_movimiento_que_duplica_codigo_no_se_acepta(tmp_path):
    raiz = _arbol(tmp_path, {'core/a.py': _funcion('grande', 200)})
    base = ratchet.medir(raiz)
    _arbol(raiz, {'core/conversacion/b.py': _funcion('copia', 200)})
    problemas = ratchet.comparar(base, ratchet.medir(raiz), aceptar_movimiento=True)
    assert any('lineas_en_funciones_grandes subió' in p for p in problemas)


def _handler(rama):
    """def + 2 líneas de encabezado + la rama + return Respuesta: pegamento 4."""
    cuerpo = ''.join(f'    x{i} = {i}\n' for i in range(rama))
    return (
        'def manejar(contexto):\n'
        '    estudiante = contexto.estudiante\n'
        "    previo = contexto.locales['previo']\n"
        f'{cuerpo}'
        '    return Respuesta(texto=None)\n'
    )


def test_pegamento_cuenta_def_encabezado_y_return():
    import ast

    func = ast.parse(_handler(3)).body[0]
    assert ratchet.pegamento(func) == 4
    assert ratchet.pegamento(ast.parse(_funcion('suelta', 5)).body[0]) == 0


def test_estado_movido_puede_sumar_solo_su_pegamento(tmp_path):
    raiz = _arbol(tmp_path, {'core/views/w.py': _funcion('cuerpo', 400)})
    base = ratchet.medir(raiz)
    _arbol(raiz, {'core/views/w.py': _funcion('cuerpo', 200), 'core/conversacion/estados/x.py': _handler(200)})
    assert not ratchet.comparar(base, ratchet.medir(raiz), aceptar_movimiento=True)
    _arbol(raiz, {'core/conversacion/estados/x.py': _handler(201)})
    problemas = ratchet.comparar(base, ratchet.medir(raiz), aceptar_movimiento=True)
    assert any('lineas_en_funciones_grandes subió' in p for p in problemas)


def test_pegamento_solo_para_estados(tmp_path):
    raiz = _arbol(tmp_path, {'core/views/w.py': _funcion('cuerpo', 400)})
    base = ratchet.medir(raiz)
    _arbol(raiz, {'core/views/w.py': _funcion('cuerpo', 200), 'core/otro.py': _handler(200)})
    problemas = ratchet.comparar(base, ratchet.medir(raiz), aceptar_movimiento=True)
    assert any('lineas_en_funciones_grandes subió' in p for p in problemas)


def test_variante_de_linea_solo_se_permite_en_lineas(tmp_path):
    codigo = 'from core.lineas.variante import es_modo_twilio\nes_modo_twilio()\n'
    raiz = _arbol(tmp_path, {'core/lineas/x.py': codigo, 'core/menu.py': codigo})
    medido = ratchet.medir(raiz)
    assert medido['variante_linea'] == {'core/menu.py': 1}


def test_reemplazo_de_atributo_de_modulo_cuenta(tmp_path):
    codigo = 'import twilio.rest as twilio_rest\ntwilio_rest.Client = object\n'
    raiz = _arbol(tmp_path, {'core/canal.py': codigo})
    assert ratchet.medir(raiz)['parches_runtime'] == {'core/canal.py': 1}


def test_except_amplio_cuenta(tmp_path):
    codigo = (
        'try:\n    pass\nexcept Exception:\n    pass\n'
        'try:\n    pass\nexcept:\n    pass\n'
        'try:\n    pass\nexcept ValueError:\n    pass\n'
    )
    raiz = _arbol(tmp_path, {'core/a.py': codigo})
    assert ratchet.medir(raiz)['excepts_amplios'] == {'core/a.py': 2}


def test_marcadores_y_parser_cuentan(tmp_path):
    codigo = "t = '[MULTI_MSG]hola[SEP]chao'\npartes = t.split('[SEP]')\n"
    raiz = _arbol(tmp_path, {'core/a.py': codigo})
    medido = ratchet.medir(raiz)
    assert medido['parser_sep'] == {'core/a.py': 1}
    assert medido['marcadores_texto']['core/a.py'] >= 1


def test_core_no_importa_apps_de_arriba(tmp_path):
    raiz = _arbol(tmp_path, {
        'core/a.py': 'from portal.views import x\nimport aprende.models\n',
        'portal/views.py': 'from core.a import y\n',
    })
    medido = ratchet.medir(raiz)
    assert medido['core_importa_apps_superiores'] == {'core/a.py': 2}


def test_ciclo_mayor(tmp_path):
    raiz = _arbol(tmp_path, {
        'core/__init__.py': '',
        'core/a.py': 'from core import b\n',
        'core/b.py': 'from core import c\n',
        'core/c.py': 'from . import a\n',
        'core/d.py': 'from core import a\n',
    })
    assert ratchet.medir(raiz)['ciclo_mayor'] == 3


_CICLO = {
    'core/__init__.py': '',
    'core/a.py': 'from core import b\n',
    'core/b.py': 'from core import a\n',
}


def test_estado_movido_al_ciclo_se_acepta_solo_como_movimiento(tmp_path):
    raiz = _arbol(tmp_path, _CICLO)
    base = ratchet.medir(raiz)
    _arbol(raiz, {
        'core/a.py': 'from core import b\nfrom core.conversacion.estados import cedula\n',
        'core/conversacion/estados/cedula.py': 'from core import b\n',
    })
    actual = ratchet.medir(raiz)
    assert actual['ciclo_mayor'] == 3
    assert any('ciclo_mayor subió' in p for p in ratchet.comparar(base, actual))
    assert not ratchet.comparar(base, actual, aceptar_movimiento=True)


def test_puertas_y_linea_principal_movidas_al_ciclo_se_aceptan_como_movimiento(tmp_path):
    raiz = _arbol(tmp_path, _CICLO)
    base = ratchet.medir(raiz)
    _arbol(raiz, {
        'core/a.py': (
            'from core import b\nfrom core.conversacion import puertas\n'
            'from core.lineas.principal import menu\n'
        ),
        'core/conversacion/puertas.py': 'from core import a\n',
        'core/lineas/principal/menu.py': 'from core import a\n',
    })
    actual = ratchet.medir(raiz)
    assert actual['ciclo_mayor'] == 4
    assert not ratchet.comparar(base, actual, aceptar_movimiento=True)


def test_intents_movidos_al_ciclo_se_aceptan_como_movimiento(tmp_path):
    raiz = _arbol(tmp_path, _CICLO)
    base = ratchet.medir(raiz)
    _arbol(raiz, {
        'core/a.py': 'from core import b\nfrom core.conversacion.intents import saludo\n',
        'core/conversacion/intents/saludo.py': 'from core import a\n',
    })
    actual = ratchet.medir(raiz)
    assert actual['ciclo_mayor'] == 3
    assert any('ciclo_mayor subió' in p for p in ratchet.comparar(base, actual))
    assert not ratchet.comparar(base, actual, aceptar_movimiento=True)


def test_un_nombre_parecido_a_puertas_no_cuenta_como_movimiento(tmp_path):
    raiz = _arbol(tmp_path, _CICLO)
    base = ratchet.medir(raiz)
    _arbol(raiz, {
        'core/a.py': 'from core import b\nfrom core.conversacion import puertas_extra\n',
        'core/conversacion/puertas_extra.py': 'from core import a\n',
    })
    problemas = ratchet.comparar(base, ratchet.medir(raiz), aceptar_movimiento=True)
    assert any('ciclo_mayor subió' in p for p in problemas)


def test_otro_modulo_que_entra_al_ciclo_no_se_acepta(tmp_path):
    raiz = _arbol(tmp_path, _CICLO)
    base = ratchet.medir(raiz)
    _arbol(raiz, {
        'core/a.py': 'from core import b\nfrom core import c\n',
        'core/c.py': 'from core import b\n',
    })
    problemas = ratchet.comparar(base, ratchet.medir(raiz), aceptar_movimiento=True)
    assert any('ciclo_mayor subió' in p for p in problemas)


def test_tests_y_migraciones_no_cuentan(tmp_path):
    raiz = _arbol(tmp_path, {
        'core/tests_algo.py': _funcion('enorme', 300),
        'core/migrations/0001_x.py': _funcion('enorme', 300),
        'core/a.py': _funcion('chica', 5),
    })
    assert ratchet.medir(raiz)['funciones_grandes'] == {}


def test_archivo_roto_nuevo_falla_y_el_conocido_no(tmp_path):
    raiz = _arbol(tmp_path, {'core/viejo.py': 'def x(:\n'})
    base = ratchet.medir(raiz)
    assert base['no_parseables'] == ['core/viejo.py']
    assert not ratchet.comparar(base, ratchet.medir(raiz))
    _arbol(raiz, {'core/nuevo.py': '  sangria_mala = 1\n'})
    problemas = ratchet.comparar(base, ratchet.medir(raiz))
    assert any('core/nuevo.py' in p for p in problemas)


def test_archivo_suelto_para_el_hook(tmp_path):
    raiz = _arbol(tmp_path, {'core/a.py': _funcion('grande', 200)})
    base = ratchet.medir(raiz)
    _arbol(raiz, {'core/a.py': _funcion('grande', 220) + 'try:\n    pass\nexcept Exception:\n    pass\n'})
    problemas = ratchet.comparar_archivo(base, raiz, 'core/a.py')
    assert any('función creció' in p for p in problemas)
    assert any('excepts_amplios' in p for p in problemas)
    assert ratchet.comparar_archivo(base, raiz, 'core/tests_x.py') == []
