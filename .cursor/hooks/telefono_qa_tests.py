"""afterFileEdit: en tests, no meter teléfonos de campo; solo QA 3026480629.

Permite el QA canónico 573026480629 y fixtures sintéticos 57300… (contratos).
Cualquier otro 57 + 10 dígitos en un archivo de test pide confirmación.
"""
from __future__ import annotations

import re
from pathlib import Path

from _comun import RAIZ, leer_entrada, responder, ruta_editada

TEL_QA = '573026480629'
TEL_QA_LOCAL = '3026480629'
# Fixtures de contrato / suites viejas (no son números de campo).
_PREFIJO_FIXTURE = re.compile(r'^57300')
_RE_E164_CO = re.compile(r'(?<!\d)(57\d{10})(?!\d)')


def _es_test(rel: str) -> bool:
    nombre = Path(rel).name
    return (
        rel.startswith('core/tests')
        or '/tests/' in rel
        or nombre.startswith('test_')
        or nombre.startswith('tests_')
    )


def _telefonos_prohibidos(texto: str) -> list[str]:
    malos = []
    for tel in _RE_E164_CO.findall(texto or ''):
        if tel == TEL_QA:
            continue
        if _PREFIJO_FIXTURE.match(tel):
            continue
        malos.append(tel)
    return sorted(set(malos))


def main() -> None:
    entrada = leer_entrada()
    rel = ruta_editada(entrada)
    if not rel or not _es_test(rel):
        responder({})
        return
    ruta = RAIZ / rel
    try:
        texto = ruta.read_text(encoding='utf-8')
    except OSError:
        responder({})
        return
    malos = _telefonos_prohibidos(texto)
    if not malos:
        responder({})
        return
    responder({
        'permission': 'ask',
        'user_message': (
            f'{rel} tiene teléfono(s) que no son el QA interno: {", ".join(malos)}. '
            f'Regla eki: en tests usa solo {TEL_QA} (celular {TEL_QA_LOCAL}) '
            'o fixtures 57300…. ¿Confirmas?'
        ),
        'agent_message': (
            f'No uses números de campo en tests. Canónico: {TEL_QA} / {TEL_QA_LOCAL}. '
            'Ver docs/GUIA_PLATAFORMA_EKI.md y .cursor/hooks/telefono_qa_tests.py.'
        ),
    })


if __name__ == '__main__':
    main()
