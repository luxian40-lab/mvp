"""Reexport de fase H2. El código vive en core.curso.plantillas_ejercicios."""
import core.curso.plantillas_ejercicios as _impl
import sys as _sys
_sys.modules[__name__] = _impl
