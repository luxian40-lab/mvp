"""Reexport de fase H2. El código vive en core.curso.bloques_modulo."""
import core.curso.bloques_modulo as _impl
import sys as _sys
_sys.modules[__name__] = _impl
